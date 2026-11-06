"""GĐ4/P0.21 synthetic signed offline SQLite metadata archive acceptance tests."""
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
import base64
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from swing_trading.reference_offline_verified_archive import (
    verify_offline_signed_metadata_archive,
)
from swing_trading.reference_checkpoint_signature import (
    DetachedJournalSignature, signature_payload,
)
from swing_trading.reference_journal import (
    ReferenceJournal, ReferenceJournalCorrupt, ZERO,
)
from swing_trading.reference_journal_recovery import (
    JournalCheckpoint, create_candidate_journal_checkpoint,
)
from swing_trading.reference_storage_preflight import UnsafeReferenceStorage
from test_d1_mcp_transport_bridge import bridge
from test_dnse_d1_reference_fallback import request, NOW
from test_reference_journal import _approved


class OfflineSignedArchiveTests(unittest.TestCase):
    def setUp(self):
        t = TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name) / "private"
        self.root.mkdir(mode=0o700)
        self.live = ReferenceJournal(self.root / "source.sqlite")
        self.live.initialize()
        os.chmod(self.live.path, 0o600)
        self.req = request()
        self.live.append(
            "ssi-run", self.req, bridge()[0].run(self.req),
            expected_tip=ZERO, retention=_approved()
        )
        self.archive = self.root / "metadata.sqlite"
        self.cp = create_candidate_journal_checkpoint(
            self.live, self.archive, "cp1", "store1", NOW
        )
        self.key = Ed25519PrivateKey.from_private_bytes(b"\x23" * 32)
        self.public = self.key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        self.fingerprint = sha256(self.public).hexdigest()
        self.seal = self.make_seal(self.cp)

    def make_seal(self, cp):
        when = NOW + timedelta(seconds=1)
        message = signature_payload(cp, key_id="key1", signed_at_utc=when)
        return DetachedJournalSignature(
            cp.checkpoint_id, cp.store_id, "key1", when,
            base64.b64encode(self.key.sign(message)).decode("ascii")
        )

    def check(self, **overrides):
        kwargs = dict(
            root=self.root, archive=self.archive,
            checkpoint=self.cp, signature=self.seal,
            public_key_raw=self.public,
            expected_public_key_sha256=self.fingerprint,
            expected_key_id="key1", expected_store_id="store1"
        )
        kwargs.update(overrides)
        return verify_offline_signed_metadata_archive(**kwargs)

    def test_signed_metadata_archive_read_from_fd_without_live_quotes(self):
        out = self.check()
        self.assertEqual(out.journal_records, 1)
        self.assertEqual(out.chain_tip_sha256, self.cp.chain_tip_sha256)
        self.assertEqual(out.archive_sha256, self.cp.backup_sha256)
        self.assertTrue(out.signed_manifest_checked)
        self.assertTrue(out.metadata_only)
        self.assertFalse(out.production_authorized)
        self.assertFalse(out.market_data_certified)
        self.assertFalse(out.actionable)
        self.assertFalse(out.historical_backtest_qualified)
        self.assertEqual(self.live.verify()[0], 1)
        with sqlite3.connect(self.archive) as c:
            self.assertEqual(c.execute("SELECT count(*) FROM cache").fetchone()[0], 0)
        self.assertNotIn(b"vnd_ohlc", self.archive.read_bytes())

    def test_two_provider_history_preserved_in_one_metadata_archive(self):
        self.live.append(
            "dnse-run", self.req,
            bridge(ssi_response={
                "status": "error", "error": "DOWNSTREAM_UNAVAILABLE"
            })[0].run(self.req),
            expected_tip=self.live.verify()[1], retention=_approved()
        )
        second = self.root / "two.sqlite"
        cp = create_candidate_journal_checkpoint(
            self.live, second, "cp2", "store1", NOW
        )
        out = self.check(archive=second, checkpoint=cp, signature=self.make_seal(cp))
        self.assertEqual(out.journal_records, 2)
        self.assertEqual(cp.omitted_cache_rows, 2)
        with sqlite3.connect(second) as c:
            self.assertEqual(c.execute("SELECT count(*) FROM cache").fetchone()[0], 0)

    def test_invalid_key_or_fingerprint_refuses_before_file_open(self):
        missing = self.root / "not-present.sqlite"
        with self.assertRaises(ReferenceJournalCorrupt):
            self.check(archive=missing, expected_public_key_sha256="f" * 64)
        other = Ed25519PrivateKey.from_private_bytes(b"\x24" * 32)
        other_pub = other.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        with self.assertRaises(ReferenceJournalCorrupt):
            self.check(archive=missing, public_key_raw=other_pub,
                       expected_public_key_sha256=sha256(other_pub).hexdigest())
        with self.assertRaises(ReferenceJournalCorrupt):
            self.check(archive=missing, expected_store_id="other")

    def test_wrong_signed_checkpoint_fails_before_disk_read(self):
        with self.assertRaises(ReferenceJournalCorrupt):
            self.check(archive=self.root / "none.sqlite",
                       checkpoint=replace(self.cp, record_count=2))

    def test_tampered_archive_is_rejected(self):
        with self.archive.open("r+b") as f:
            f.seek(123)
            before = f.read(1)
            f.seek(123)
            f.write(bytes([before[0] ^ 0xFF]))
        with self.assertRaises(ReferenceJournalCorrupt):
            self.check()

    def test_present_wal_or_shm_refused(self):
        for suffix in ("-wal", "-shm", "-journal"):
            sidecar = Path(str(self.archive) + suffix)
            sidecar.write_bytes(b"fixture only")
            os.chmod(sidecar, 0o600)
            with self.subTest(suffix=suffix), self.assertRaises(UnsafeReferenceStorage):
                self.check()
            sidecar.unlink()

    def test_missing_unsafe_permission_and_hardlink_refused(self):
        os.chmod(self.archive, 0o644)
        with self.assertRaises(UnsafeReferenceStorage):
            self.check()
        os.chmod(self.archive, 0o600)
        other = self.root / "hardlink.sqlite"
        os.link(self.archive, other)
        with self.assertRaises(UnsafeReferenceStorage):
            self.check()
        other.unlink()
        self.archive.rename(self.root / "gone.sqlite")
        with self.assertRaises(UnsafeReferenceStorage):
            self.check()

    def test_oversized_bounded_archive_refused(self):
        with self.assertRaises(UnsafeReferenceStorage):
            self.check(max_archive_bytes=4096)
        with self.assertRaises(ValueError):
            self.check(max_archive_bytes=2**30)
        with self.assertRaises(ValueError):
            self.check(max_archive_bytes=True)

    def test_validly_signed_quote_bearing_sqlite_archive_is_still_forbidden(self):
        # The signing key deliberately signs a prohibited fixture! Authentic
        # signature alone cannot approve storing SSI/DNSE quote-cache bytes.
        full = self.root / "contains-quotes.sqlite"
        with sqlite3.connect(self.live.path) as src:
            with sqlite3.connect(full) as dest:
                src.backup(dest)
        os.chmod(full, 0o600)
        count, tip = self.live.verify()
        cp = JournalCheckpoint(
            "cache-not-permitted", "store1", NOW,
            count, tip, sha256(full.read_bytes()).hexdigest(), 0
        )
        with self.assertRaises(ReferenceJournalCorrupt):
            self.check(archive=full, checkpoint=cp, signature=self.make_seal(cp))

    def test_wrong_inode_type_symlink_refused(self):
        alias = self.root / "alias.sqlite"
        alias.symlink_to(self.archive)
        with self.assertRaises(UnsafeReferenceStorage):
            self.check(archive=alias)

    def test_original_live_database_wal_not_used_as_metadata_archive(self):
        # Even if a caller signs live SQLite, its cache rows or WAL cannot
        # be silently relabeled as an independently vetted metadata snapshot.
        count, tip = self.live.verify()
        with sqlite3.connect(self.live.path) as c:
            c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        cp = JournalCheckpoint(
            "live", "store1", NOW,
            count, tip, sha256(self.live.path.read_bytes()).hexdigest(), 0
        )
        with self.assertRaises((ReferenceJournalCorrupt, UnsafeReferenceStorage)):
            self.check(archive=self.live.path, checkpoint=cp,
                       signature=self.make_seal(cp))


if __name__ == "__main__":
    unittest.main()
