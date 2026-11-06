"""P0.20 synthetic FD path-swap and public-key signature negative tests."""
import base64
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from swing_trading.reference_checkpoint_signature import (
    DetachedJournalSignature, signature_payload, verify_detached_journal_signature,
    verify_signed_journal_backup, restore_signed_journal_backup,
    verify_signed_journal_prefix,
)
from swing_trading.reference_pinned_fd import pin_reference_sqlite_files
from swing_trading.reference_journal import ReferenceJournal, ReferenceJournalCorrupt, ZERO
from swing_trading.reference_storage_preflight import UnsafeReferenceStorage
from swing_trading.reference_journal_recovery import create_candidate_journal_checkpoint
from test_d1_mcp_transport_bridge import bridge
from test_dnse_d1_reference_fallback import request, NOW


class PinnedFdFixtureTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "private"
        self.root.mkdir(mode=0o700)
        self.db = self.root / "ssi_dnse.sqlite"
        ReferenceJournal(self.db).initialize()
        os.chmod(self.db, 0o600)

    def test_pinned_db_is_readonly_valid_and_no_production_approval(self):
        with pin_reference_sqlite_files(self.root, self.db) as snap:
            self.assertTrue(snap.verify_path_names())
            self.assertTrue(snap.local_permissions_pass)
            self.assertFalse(snap.production_authorized)
            self.assertEqual(os.pread(snap.database_fd, 16, 0), b"SQLite format 3\x00")
            self.assertEqual(snap.sidecar_fds, ())

    def test_named_file_swapped_after_open_rejected(self):
        with pin_reference_sqlite_files(self.root, self.db) as snap:
            self.db.rename(self.root / "moved.sqlite")
            self.db.write_bytes(b"SQLite format 3\x00" + b"X" * 100)
            os.chmod(self.db, 0o600)
            self.assertEqual(os.pread(snap.database_fd, 16, 0), b"SQLite format 3\x00")
            with self.assertRaises(UnsafeReferenceStorage):
                snap.verify_path_names()

    def test_pinned_directory_swap_detected(self):
        with pin_reference_sqlite_files(self.root, self.db) as snap:
            moved = self.root.with_name("original-private")
            self.root.rename(moved)
            self.root.mkdir(mode=0o700)
            with self.assertRaises(UnsafeReferenceStorage):
                snap.verify_path_names()

    def test_symlink_and_hardlink_refused_before_pinning(self):
        link = self.root / "ref.sqlite"
        link.symlink_to(self.db)
        with self.assertRaises(UnsafeReferenceStorage):
            with pin_reference_sqlite_files(self.root, link):
                pass
        link.unlink()
        os.link(self.db, link)
        with self.assertRaises(UnsafeReferenceStorage):
            with pin_reference_sqlite_files(self.root, self.db):
                pass

    def test_private_mode_root_and_db_mandatory(self):
        os.chmod(self.db, 0o644)
        with self.assertRaises(UnsafeReferenceStorage):
            with pin_reference_sqlite_files(self.root, self.db):
                pass
        os.chmod(self.db, 0o600)
        os.chmod(self.root, 0o755)
        with self.assertRaises(UnsafeReferenceStorage):
            with pin_reference_sqlite_files(self.root, self.db):
                pass

    def test_new_sidecar_since_pin_refused(self):
        with pin_reference_sqlite_files(self.root, self.db) as snap:
            wal = Path(str(self.db) + "-wal")
            wal.write_bytes(b"test-sidecar")
            os.chmod(wal, 0o600)
            with self.assertRaises(UnsafeReferenceStorage):
                snap.verify_path_names()

    def test_existing_sidecar_is_pinned_and_swap_denied(self):
        wal = Path(str(self.db) + "-wal")
        wal.write_bytes(b"test-sidecar")
        os.chmod(wal, 0o600)
        with pin_reference_sqlite_files(self.root, self.db) as snap:
            self.assertIn("-wal", [suffix for suffix, _ in snap.sidecar_fds])
            wal.rename(Path(str(self.db) + "-wal-old"))
            with self.assertRaises(UnsafeReferenceStorage):
                snap.verify_path_names()

    def test_root_gitrepo_and_escape_rejected(self):
        (self.root / ".git").mkdir()
        with self.assertRaises(UnsafeReferenceStorage):
            with pin_reference_sqlite_files(self.root, self.db):
                pass
        with self.assertRaises(ValueError):
            with pin_reference_sqlite_files(self.root, self.root / "../outside.sqlite"):
                pass
        with self.assertRaises(ValueError):
            with pin_reference_sqlite_files("relative", self.db):
                pass

    def test_inode_header_mandatory(self):
        self.db.write_bytes(b"not sqlite")
        os.chmod(self.db, 0o600)
        with self.assertRaises(UnsafeReferenceStorage):
            with pin_reference_sqlite_files(self.root, self.db):
                pass

    def test_wrong_uid_rejected(self):
        with self.assertRaises(UnsafeReferenceStorage):
            with pin_reference_sqlite_files(
                self.root, self.db, expected_uid=os.getuid() + 1
            ):
                pass


class Ed25519CustodyContractTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.store = ReferenceJournal(self.root / "live.sqlite")
        self.store.initialize()
        self.req = request()
        self.store.append("row1", self.req, bridge()[0].run(self.req), expected_tip=ZERO)
        self.backup = self.root / "backup.sqlite"
        self.cp = create_candidate_journal_checkpoint(
            self.store, self.backup, "cp-ed-1", "store-A", NOW
        )
        # A fixed, synthetic seed is used ONLY in tests, not user/production.
        self.private = Ed25519PrivateKey.from_private_bytes(b"\x13" * 32)
        self.public = self.private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        self.fingerprint = sha256(self.public).hexdigest()
        self.signed_at = NOW + timedelta(seconds=1)
        self.seal = self.sign(self.cp)

    def sign(self, cp, *, at=None):
        signed = at or self.signed_at
        payload = signature_payload(cp, key_id="external-key-v1",
                                    signed_at_utc=signed)
        value = base64.b64encode(self.private.sign(payload)).decode("ascii")
        return DetachedJournalSignature(cp.checkpoint_id, cp.store_id,
                                        "external-key-v1", signed, value)

    def check(self, cp=None, seal=None, *, public=None, fingerprint=None,
              key_id="external-key-v1", store_id="store-A"):
        return verify_detached_journal_signature(
            cp or self.cp, seal or self.seal,
            public_key_raw=self.public if public is None else public,
            expected_key_id=key_id,
            expected_store_id=store_id,
            expected_public_key_sha256=(
                self.fingerprint if fingerprint is None else fingerprint
            ),
        )

    def test_valid_detached_signature_and_backup(self):
        roundtrip = DetachedJournalSignature.parse_json(self.seal.canonical_json())
        self.assertEqual(roundtrip, self.seal)
        self.assertEqual(self.check(seal=roundtrip), self.cp)
        self.assertEqual(
            verify_signed_journal_backup(
                self.backup, self.cp, roundtrip,
                public_key_raw=self.public, expected_key_id="external-key-v1",
                expected_store_id="store-A",
                expected_public_key_sha256=self.fingerprint,
            ),
            self.store.verify(),
        )

    def test_signed_restore_and_no_overwrite(self):
        dest = self.root / "restored.sqlite"
        kwargs = dict(public_key_raw=self.public, expected_key_id="external-key-v1",
                      expected_store_id="store-A",
                      expected_public_key_sha256=self.fingerprint)
        restored = restore_signed_journal_backup(
            self.backup, dest, self.cp, self.seal, **kwargs
        )
        self.assertEqual(restored.verify(), self.store.verify())
        self.assertEqual(
            verify_signed_journal_prefix(restored, self.cp, self.seal, **kwargs),
            self.store.verify(),
        )
        with self.assertRaises(FileExistsError):
            restore_signed_journal_backup(
                self.backup, dest, self.cp, self.seal, **kwargs
            )

    def test_wrong_public_key_and_fingerprint_fails_closed(self):
        outsider = Ed25519PrivateKey.from_private_bytes(b"\x14" * 32)
        outsider_pub = outsider.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        with self.assertRaises(ReferenceJournalCorrupt):
            self.check(public=outsider_pub)
        with self.assertRaises(ReferenceJournalCorrupt):
            self.check(public=outsider_pub, fingerprint=sha256(outsider_pub).hexdigest())
        with self.assertRaises(ValueError):
            self.check(public=b"short")
        with self.assertRaises(ReferenceJournalCorrupt):
            self.check(fingerprint="f" * 64)

    def test_reject_changed_full_checkpoint_even_if_file_chain_valid(self):
        for attr, value in (
            ("backup_sha256", "f" * 64),
            ("omitted_cache_rows", self.cp.omitted_cache_rows + 1),
            ("record_count", self.cp.record_count + 1),
            ("checkpoint_id", "cp-replacement"),
        ):
            with self.subTest(attr=attr), self.assertRaises(ReferenceJournalCorrupt):
                self.check(cp=replace(self.cp, **{attr: value}))

    def test_store_key_id_and_clock_binding(self):
        with self.assertRaises(ReferenceJournalCorrupt):
            self.check(store_id="store-B")
        with self.assertRaises(ReferenceJournalCorrupt):
            self.check(key_id="external-key-v2")
        with self.assertRaises(ReferenceJournalCorrupt):
            self.check(seal=replace(self.seal, signed_at_utc=NOW + timedelta(days=1)))
        with self.assertRaises(ValueError):
            signature_payload(self.cp, key_id="external-key-v1",
                              signed_at_utc=NOW - timedelta(seconds=1))

    def test_signature_tamper_and_schema_mismatch(self):
        invalid = base64.b64encode(bytes(64)).decode("ascii")
        with self.assertRaises(ReferenceJournalCorrupt):
            self.check(seal=replace(self.seal, signature_base64=invalid))
        with self.assertRaises(ValueError):
            replace(self.seal, algorithm="RSA")
        with self.assertRaises(ValueError):
            replace(self.seal, signature_base64="not base64")
        with self.assertRaises(ValueError):
            replace(self.seal, schema_version=2)
        with self.assertRaises(ValueError):
            replace(self.seal, key_id="../bad")
        data = json.loads(self.seal.canonical_json())
        data["extra"] = "not approved"
        with self.assertRaises(ValueError):
            DetachedJournalSignature.parse_json(json.dumps(data))
        with self.assertRaises(TypeError):
            DetachedJournalSignature.parse_json(None)

    def test_backup_byte_tamper_rejected_despite_valid_signature(self):
        with self.backup.open("r+b") as f:
            f.seek(40)
            b = f.read(1)
            f.seek(40)
            f.write(bytes([b[0] ^ 0xff]))
        dest = self.root / "not-restored.sqlite"
        with self.assertRaises(ReferenceJournalCorrupt):
            restore_signed_journal_backup(
                self.backup, dest, self.cp, self.seal,
                public_key_raw=self.public, expected_key_id="external-key-v1",
                expected_store_id="store-A",
                expected_public_key_sha256=self.fingerprint,
            )
        self.assertFalse(dest.exists())

    def test_a_public_key_is_not_an_approval_flag(self):
        # Even cryptographic success cannot infer real custodian/entitlement.
        self.assertEqual(self.check(), self.cp)
        self.assertEqual(self.cp.snapshot_kind, "METADATA_ONLY")
        self.assertEqual(self.cp.omitted_cache_rows, 0)


if __name__ == "__main__":
    unittest.main()
