"""Transaction rollback smoke using controlled test callback."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from swing_trading.durable_evidence import EvidenceItem, EvidenceStore, State, ZERO


class AtomicityTest(TestCase):
    def test_failed_second_receipt_preserves_empty_store(self):
        with TemporaryDirectory() as root:
            store = EvidenceStore(Path(root) / "audit.sqlite")
            store.initialize()
            rows = tuple(EvidenceItem(str(i), "fixture", b"fixture",
                         sha256(b"fixture").hexdigest(), State.QUARANTINED,
                         "SOURCE_UNKNOWN") for i in (1, 2))
            with patch("swing_trading.durable_evidence.link") as check:
                check.side_effect = ["a" * 64, ValueError("test stop")]
                with self.assertRaises(ValueError):
                    store.append_batch("batch1", rows, datetime(2026, 11, 6, tzinfo=timezone.utc))
            self.assertEqual(store.verify(), (0, ZERO))
