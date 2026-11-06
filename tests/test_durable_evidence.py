"""Synthetic integrity tests for the P0.4 local evidence store."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from swing_trading.durable_evidence import EvidenceItem, EvidenceStore, State

T = datetime(2026, 11, 6, tzinfo=timezone.utc)


class EvidenceSmoke(unittest.TestCase):
    def test_store_and_restore_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            s = EvidenceStore(Path(folder) / "records.sqlite")
            s.initialize()
            raw = b"fixture-only"
            e = EvidenceItem("row1", "fixture-source", raw, sha256(raw).hexdigest(),
                             State.QUARANTINED, "SOURCE_UNVERIFIED")
            result = s.append_batch("batch1", (e,), T)
            self.assertEqual(result[0], 1)
            self.assertEqual(s.verify(), result)
            self.assertEqual(s.read_verified_bytes("batch1", "row1"), raw)


if __name__ == "__main__":
    unittest.main()
