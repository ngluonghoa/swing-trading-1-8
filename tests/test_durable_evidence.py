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


    def test_checksum_state_and_duplicate_guards(self):
        from swing_trading.durable_evidence import EvidenceCorrupt, ZERO
        raw = b"synthetic-invalid"
        with self.assertRaises(EvidenceCorrupt):
            EvidenceItem("bad", "source", raw, "0" * 64, State.QUARANTINED, "INVALID")
        with self.assertRaises(TypeError):
            EvidenceItem("bad", "source", raw, sha256(raw).hexdigest(), "VERIFIED", "INVALID")
        ok = EvidenceItem("same", "source", raw, sha256(raw).hexdigest(),
                          State.STAGED_UNVERIFIED, "LEGACY_UNVERIFIED")
        with self.assertRaises(ValueError):
            self.store.append_batch("duplicate", (ok, ok), T)
        self.assertEqual(self.store.verify(), (0, ZERO))
        self.store.append_batch("once", (ok,), T)
        with self.assertRaises(Exception):
            self.store.append_batch("once", (ok,), T)
        self.assertEqual(self.store.verify()[0], 1)

    def test_stale_chain_tip_does_not_append(self):
        from swing_trading.durable_evidence import EvidenceCorrupt, ZERO
        raw = b"fixture"
        e = EvidenceItem("row", "source", raw, sha256(raw).hexdigest(),
                         State.QUARANTINED, "SOURCE_UNVERIFIED")
        first = self.store.append_batch("batchA", (e,), T)
        self.assertNotEqual(first[1], ZERO)
        with self.assertRaises(EvidenceCorrupt):
            self.store.append_batch("batchB", (e,), T, expected_tip_sha256=ZERO)
        self.assertEqual(self.store.verify(), first)


if __name__ == "__main__":
    unittest.main()
