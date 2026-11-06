"""P0.4 recovery smoke tests use synthetic input only."""
import tempfile
import unittest
from pathlib import Path

from swing_trading.durable_evidence import EvidenceStore
from swing_trading.evidence_recovery import backup_verified, restore_verified


class RecoverySmoke(unittest.TestCase):
    def test_empty_store_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = EvidenceStore(root / "one.sqlite")
            store.initialize()
            before = store.verify()
            backup_verified(store, root / "two.sqlite")
            restored = restore_verified(root / "two.sqlite", root / "three.sqlite")
            self.assertEqual(before, restored.verify())


    def test_nonempty_binary_backup_and_copy_no_clobber(self):
        from datetime import datetime, timezone
        from hashlib import sha256
        from swing_trading.durable_evidence import EvidenceItem, State
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = EvidenceStore(root / "source.sqlite")
            source.initialize()
            raw = b"fixture:\x00\xff"
            entry = EvidenceItem("row-1", "fixture-record", raw,
                                 sha256(raw).hexdigest(), State.QUARANTINED,
                                 "SOURCE_TIME_AMBIGUOUS")
            expected = source.append_batch(
                "batch1", (entry,), datetime(2026, 11, 6, tzinfo=timezone.utc))
            backup_path = root / "backup.sqlite"
            self.assertEqual(backup_verified(source, backup_path), expected)
            dest = root / "recovered.sqlite"
            self.assertEqual(restore_verified(backup_path, dest).verify(), expected)
            self.assertEqual(EvidenceStore(dest).read_verified_bytes("batch1", "row-1"), raw)
            with self.assertRaises(FileExistsError):
                restore_verified(backup_path, dest)
            with self.assertRaises(FileExistsError):
                backup_verified(source, backup_path)


if __name__ == "__main__":
    unittest.main()
