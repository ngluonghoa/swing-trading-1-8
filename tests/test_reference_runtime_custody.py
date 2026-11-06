"""P0.19 synthetic POSIX-permissions and detached custody-MAC negative tests."""
from dataclasses import replace
from datetime import timedelta
import json
import os
from pathlib import Path
import sqlite3
import stat
from tempfile import TemporaryDirectory
import unittest

from swing_trading.reference_storage_preflight import (
    inspect_reference_storage, require_reference_storage, UnsafeReferenceStorage,
)
from swing_trading.reference_checkpoint_mac import (
    DetachedJournalMac, create_candidate_detached_mac,
    verify_detached_journal_mac, verify_authenticated_journal_backup,
    restore_authenticated_journal_backup, verify_authenticated_journal_prefix,
)
from swing_trading.reference_journal import ReferenceJournal, ReferenceJournalCorrupt, ZERO
from swing_trading.reference_journal_recovery import (
    create_candidate_journal_checkpoint,
)
from test_d1_mcp_transport_bridge import bridge
from test_dnse_d1_reference_fallback import request, NOW

KEY = b"SYNTHETIC-NOT-A-PRODUCTION-SECRET-KEY-" + b"Z" * 16
OTHER_KEY = b"UNRELATED-TEST-VERIFICATION-KEY-XX" + b"Y" * 16


class StorageBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name)
        self.root = self.parent / "private"
        self.root.mkdir(mode=0o700)
        self.db = self.root / "ssi_dnse.sqlite"
        self.store = ReferenceJournal(self.db)
        self.store.initialize()
        os.chmod(self.db, 0o600)

    def test_local_private_store_pass_is_not_production_approval(self):
        report = require_reference_storage(self.root, self.db)
        self.assertTrue(report.local_permissions_pass)
        self.assertFalse(report.host_volume_approved)
        self.assertFalse(report.provider_retention_approved)
        self.assertFalse(report.production_authorized)
        self.assertEqual(report.issues, ())

    def test_world_readable_db_fails(self):
        os.chmod(self.db, 0o644)
        report = inspect_reference_storage(self.root, self.db)
        self.assertTrue(any("MODE_FILE:" in issue for issue in report.issues))
        with self.assertRaises(UnsafeReferenceStorage):
            report.require_local_permissions()

    def test_broad_directory_fails(self):
        os.chmod(self.root, 0o755)
        with self.assertRaises(UnsafeReferenceStorage):
            require_reference_storage(self.root, self.db)

    def test_symlink_db_denied(self):
        link = self.root / "alias.sqlite"
        link.symlink_to(self.db)
        result = inspect_reference_storage(self.root, link)
        self.assertTrue(any(x.startswith("SYMLINK_FILE:") for x in result.issues))

    def test_symlink_intermediate_directory_denied(self):
        alias = self.parent / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        result = inspect_reference_storage(alias, alias / "ssi_dnse.sqlite")
        self.assertTrue(any(x.startswith("SYMLINK_DIRECTORY:") for x in result.issues))

    def test_hardlink_database_denied(self):
        os.link(self.db, self.root / "other.sqlite")
        result = inspect_reference_storage(self.root, self.db)
        self.assertTrue(any(x.startswith("HARDLINK_FILE:") for x in result.issues))

    def test_parent_and_missing_db_denied(self):
        with self.assertRaises(ValueError):
            inspect_reference_storage(self.root, self.parent / "outside.sqlite")
        with self.assertRaises(ValueError):
            inspect_reference_storage("relative/path", self.db)
        with self.assertRaises(ValueError):
            inspect_reference_storage(self.root, self.root / "../private/ssi_dnse.sqlite")
        report = inspect_reference_storage(self.root, self.root / "missing.sqlite")
        self.assertTrue(any(x.startswith("MISSING_FILE:") for x in report.issues))

    def test_git_tree_denied(self):
        (self.root / ".git").mkdir()
        result = inspect_reference_storage(self.root, self.db)
        self.assertTrue(any(x.startswith("INSIDE_GIT_TREE:") for x in result.issues))

    def test_sidecar_permissions_and_symlink_denied(self):
        wal = Path(str(self.db) + "-wal")
        wal.write_bytes(b"SYNTHETIC-ONLY")
        os.chmod(wal, 0o644)
        result = inspect_reference_storage(self.root, self.db)
        self.assertTrue(any(x.startswith("MODE_FILE:") for x in result.issues))
        wal.unlink()
        wal.symlink_to(self.db)
        result = inspect_reference_storage(self.root, self.db)
        self.assertTrue(any(x.startswith("SYMLINK_FILE:") for x in result.issues))

    def test_wrong_uid_not_false_positive(self):
        wrong = os.getuid() + 1
        r = inspect_reference_storage(self.root, self.db, expected_uid=wrong)
        self.assertTrue(any("OWNER_DIRECTORY:" in x for x in r.issues))
        self.assertTrue(any("OWNER_FILE:" in x for x in r.issues))


class DetachedCustodyFixtureTests(unittest.TestCase):
    def setUp(self):
        t = TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.folder = Path(t.name)
        self.path = self.folder / "live.sqlite"
        self.store = ReferenceJournal(self.path)
        self.store.initialize()
        self.req = request()
        self.store.append("run1", self.req, bridge()[0].run(self.req), expected_tip=ZERO)
        self.backup = self.folder / "backup.sqlite"
        self.checkpoint = create_candidate_journal_checkpoint(
            self.store, self.backup, "cp-1", "store-A", NOW
        )
        self.seal = create_candidate_detached_mac(
            self.checkpoint, signing_key=KEY, key_id="custodian-v1",
            sealed_at_utc=NOW + timedelta(seconds=1),
        )

    def verify(self, cp=None, seal=None, key=KEY, store_id="store-A", key_id="custodian-v1"):
        return verify_detached_journal_mac(
            cp or self.checkpoint, seal or self.seal, verification_key=key,
            expected_key_id=key_id, expected_store_id=store_id
        )

    def test_detached_manifest_roundtrip_and_verified_backup(self):
        copy = DetachedJournalMac.parse_json(self.seal.canonical_json())
        self.assertEqual(copy, self.seal)
        self.assertEqual(self.verify(seal=copy), self.checkpoint)
        result = verify_authenticated_journal_backup(
            self.backup, self.checkpoint, copy, verification_key=KEY,
            expected_key_id="custodian-v1", expected_store_id="store-A",
        )
        self.assertEqual(result, (1, self.checkpoint.chain_tip_sha256))

    def test_authenticated_restore_is_metadata_only_and_no_overwrite(self):
        target = self.folder / "restored.sqlite"
        restored = restore_authenticated_journal_backup(
            self.backup, target, self.checkpoint, self.seal,
            verification_key=KEY, expected_key_id="custodian-v1",
            expected_store_id="store-A",
        )
        self.assertEqual(restored.verify(), self.store.verify())
        self.assertEqual(
            verify_authenticated_journal_prefix(
                restored, self.checkpoint, self.seal,
                verification_key=KEY, expected_key_id="custodian-v1",
                expected_store_id="store-A",
            ),
            self.store.verify(),
        )
        with self.assertRaises(FileExistsError):
            restore_authenticated_journal_backup(
                self.backup, target, self.checkpoint, self.seal,
                verification_key=KEY, expected_key_id="custodian-v1",
                expected_store_id="store-A",
            )

    def test_missing_or_wrong_secret_fails_before_restore(self):
        with self.assertRaises(ValueError):
            self.verify(key=b"short")
        with self.assertRaises(ReferenceJournalCorrupt):
            self.verify(key=OTHER_KEY)
        target = self.folder / "never-restored.sqlite"
        with self.assertRaises(ReferenceJournalCorrupt):
            restore_authenticated_journal_backup(
                self.backup, target, self.checkpoint, self.seal,
                verification_key=OTHER_KEY, expected_key_id="custodian-v1",
                expected_store_id="store-A",
            )
        self.assertFalse(target.exists())

    def test_digest_is_bound_to_entire_checkpoint(self):
        for field, value in (
            ("backup_sha256", "f" * 64),
            ("omitted_cache_rows", self.checkpoint.omitted_cache_rows + 1),
            ("record_count", self.checkpoint.record_count + 1),
            ("created_at_utc", NOW - timedelta(seconds=1)),
        ):
            with self.subTest(field=field), self.assertRaises(ReferenceJournalCorrupt):
                self.verify(cp=replace(self.checkpoint, **{field: value}))

    def test_cross_store_key_identity_and_replay_denied(self):
        with self.assertRaises(ReferenceJournalCorrupt):
            self.verify(store_id="store-B")
        with self.assertRaises(ReferenceJournalCorrupt):
            self.verify(key_id="wrong-key")
        with self.assertRaises(ReferenceJournalCorrupt):
            self.verify(seal=replace(self.seal, checkpoint_id="cp-2"))
        with self.assertRaises(ReferenceJournalCorrupt):
            self.verify(seal=replace(self.seal, store_id="store-B"))

    def test_modified_seal_or_wrong_time_fails(self):
        with self.assertRaises(ReferenceJournalCorrupt):
            self.verify(seal=replace(self.seal, mac_sha256="f" * 64))
        with self.assertRaises(ReferenceJournalCorrupt):
            self.verify(seal=replace(
                self.seal, sealed_at_utc=NOW + timedelta(minutes=1)))
        with self.assertRaises(ValueError):
            create_candidate_detached_mac(
                self.checkpoint, signing_key=KEY, key_id="custodian-v1",
                sealed_at_utc=NOW - timedelta(seconds=1),
            )

    def test_exact_schema_and_strict_id_guards(self):
        d = json.loads(self.seal.canonical_json())
        d["extra"] = 1
        with self.assertRaises(ValueError):
            DetachedJournalMac.parse_json(json.dumps(d))
        with self.assertRaises(TypeError):
            DetachedJournalMac.parse_json(None)
        with self.assertRaises(ValueError):
            replace(self.seal, key_id="../unsafe")
        with self.assertRaises(ValueError):
            replace(self.seal, schema_version=True)
        with self.assertRaises(TypeError):
            verify_detached_journal_mac(
                self.checkpoint, None, verification_key=KEY,
                expected_key_id="custodian-v1", expected_store_id="store-A"
            )

    def test_checksum_altered_backup_refused_even_if_seal_valid(self):
        with self.backup.open("r+b") as file:
            file.seek(40)
            b = file.read(1)
            file.seek(40)
            file.write(bytes([b[0] ^ 0xff]))
        with self.assertRaises(ReferenceJournalCorrupt):
            verify_authenticated_journal_backup(
                self.backup, self.checkpoint, self.seal, verification_key=KEY,
                expected_key_id="custodian-v1", expected_store_id="store-A"
            )


if __name__ == "__main__":
    unittest.main()
