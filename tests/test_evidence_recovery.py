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


if __name__ == "__main__":
    unittest.main()
