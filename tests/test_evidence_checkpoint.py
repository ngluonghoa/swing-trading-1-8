"""Synthetic tests for independent checkpoint/pinned restore P0.4C."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from swing_trading.durable_evidence import EvidenceCorrupt, EvidenceItem, EvidenceStore, State, ZERO
from swing_trading.evidence_checkpoint import (
    EvidenceCheckpoint, create_candidate_checkpoint, file_sha256,
    restore_from_pinned, verify_backup_against_pinned, verify_history_prefix,
)

T = datetime(2026, 11, 6, 4, tzinfo=timezone.utc)


def fixture(ref="row-1", raw=b"synthetic-original-byte-source"):
    return EvidenceItem(
        ref, "SYNTHETIC-SOURCE", raw, sha256(raw).hexdigest(),
        State.QUARANTINED, "SOURCE_NOT_AUTHENTICATED",
    )


class CheckpointContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = EvidenceStore(self.root / "evidence.sqlite")
        self.store.initialize()

    def checkpoint(self):
        return create_candidate_checkpoint(
            self.store, self.root / "snapshot.sqlite",
            "cp-0001", "store-A", T
        )

    def test_empty_store_checkpoint_and_restore_from_independent_copy(self):
        cp = self.checkpoint()
        self.assertEqual(cp.record_count, 0)
        self.assertEqual(cp.chain_tip_sha256, ZERO)
        # Simulate independent custody by transferring the exact JSON,
        # not by reading a checkpoint back out of the same SQLite database.
        pinned = EvidenceCheckpoint.parse_json(cp.canonical_json())
        self.assertEqual(cp, pinned)
        self.assertEqual(
            verify_backup_against_pinned(self.root / "snapshot.sqlite",
                                         pinned, expected_store_id="store-A"),
            (0, ZERO),
        )
        restored = restore_from_pinned(
            self.root / "snapshot.sqlite", self.root / "restored.sqlite",
            pinned, expected_store_id="store-A",
        )
        self.assertEqual(restored.verify(), (0, ZERO))

    def test_binary_original_bytes_roundtrip_and_checkpoint(self):
        payload = b"fixture:\x00\xff" + b"data" * 1024
        first = self.store.append_batch("batch-A", (fixture(raw=payload),), T)
        cp = self.checkpoint()
        self.assertEqual((cp.record_count, cp.chain_tip_sha256), first)
        self.assertEqual(cp.backup_sha256,
                         file_sha256(self.root / "snapshot.sqlite"))
        pinned = EvidenceCheckpoint.parse_json(cp.canonical_json())
        r = restore_from_pinned(
            self.root / "snapshot.sqlite", self.root / "restored.sqlite",
            pinned, expected_store_id="store-A",
        )
        self.assertEqual(r.read_verified_bytes("batch-A", "row-1"), payload)
        with self.assertRaises(FileExistsError):
            restore_from_pinned(self.root / "snapshot.sqlite",
                                self.root / "restored.sqlite",
                                pinned, expected_store_id="store-A")

    def test_prefix_unchanged_after_appending_second_batch(self):
        self.store.append_batch("batch-A", (fixture(),), T)
        checkpoint = self.checkpoint()
        self.store.append_batch(
            "batch-B", (fixture(ref="row-2", raw=b"other"),),
            T + timedelta(minutes=1),
            expected_tip_sha256=checkpoint.chain_tip_sha256
        )
        count, new_tip = verify_history_prefix(
            self.store, checkpoint, expected_store_id="store-A"
        )
        self.assertEqual(count, 2)
        self.assertNotEqual(new_tip, checkpoint.chain_tip_sha256)
        # The previously pinned backup is still valid, though it has one row.
        self.assertEqual(
            verify_backup_against_pinned(self.root / "snapshot.sqlite",
                                         checkpoint, expected_store_id="store-A")[0],
            1,
        )

    def test_backup_byte_corruption_cannot_be_restored(self):
        self.store.append_batch("batch-A", (fixture(),), T)
        pinned = self.checkpoint()
        backup = self.root / "snapshot.sqlite"
        with backup.open("r+b") as f:
            f.seek(17)
            original_byte = f.read(1)
            f.seek(17)
            f.write(bytes([original_byte[0] ^ 0xff]))
        with self.assertRaises(EvidenceCorrupt):
            verify_backup_against_pinned(backup, pinned, expected_store_id="store-A")
        dest = self.root / "restored.sqlite"
        with self.assertRaises(EvidenceCorrupt):
            restore_from_pinned(backup, dest, pinned, expected_store_id="store-A")
        self.assertFalse(dest.exists())

    def test_wrong_store_id_hash_or_tip_rejected_before_restore(self):
        self.store.append_batch("batch-A", (fixture(),), T)
        cp = self.checkpoint()
        path = self.root / "snapshot.sqlite"
        with self.assertRaises(EvidenceCorrupt):
            verify_backup_against_pinned(path, cp, expected_store_id="other-store")
        with self.assertRaises(EvidenceCorrupt):
            verify_backup_against_pinned(
                path, replace(cp, backup_sha256="f" * 64),
                expected_store_id="store-A"
            )
        with self.assertRaises(EvidenceCorrupt):
            verify_backup_against_pinned(
                path, replace(cp, chain_tip_sha256="f" * 64),
                expected_store_id="store-A"
            )

    def test_current_store_truncation_or_rewritten_history_fails_pinned_tip(self):
        self.store.append_batch("batch-A", (fixture(),), T)
        cp = self.checkpoint()
        another = EvidenceStore(self.root / "other.sqlite")
        another.initialize()
        with self.assertRaises(EvidenceCorrupt):
            verify_history_prefix(another, cp, expected_store_id="store-A")
        another.append_batch("batch-A", (fixture(raw=b"tampered"),), T)
        with self.assertRaises(EvidenceCorrupt):
            verify_history_prefix(another, cp, expected_store_id="store-A")
        with self.assertRaises(EvidenceCorrupt):
            verify_history_prefix(self.store, cp, expected_store_id="different")

    def test_schema_and_utc_validation(self):
        self.store.append_batch("batch-A", (fixture(),), T)
        cp = self.checkpoint()
        with self.assertRaises(ValueError):
            EvidenceCheckpoint.parse_json(cp.canonical_json().replace(
                '"schema_version":1', '"schema_version":2'
            ))
        with self.assertRaises(ValueError):
            EvidenceCheckpoint.parse_json(cp.canonical_json()[:-1] + ',"extra":1}')
        with self.assertRaises(ValueError):
            replace(cp, created_at_utc=T.replace(tzinfo=None))
        with self.assertRaises(ValueError):
            replace(cp, record_count=True)
        with self.assertRaises(ValueError):
            replace(cp, checkpoint_id="../escape")
        with self.assertRaises(ValueError):
            replace(cp, chain_tip_sha256="wrong")
        with self.assertRaises(TypeError):
            EvidenceCheckpoint.parse_json(None)

    def test_checkpoint_backup_path_does_not_overwrite(self):
        cp = self.checkpoint()
        with self.assertRaises(FileExistsError):
            self.checkpoint()
        self.assertEqual(cp.backup_sha256,
                         file_sha256(self.root / "snapshot.sqlite"))
        with self.assertRaises(ValueError):
            create_candidate_checkpoint(
                self.store, self.root / "another.sqlite", "cp2",
                "store-A", T.replace(tzinfo=None)
            )
        self.assertFalse((self.root / "another.sqlite").exists())


if __name__ == "__main__":
    unittest.main()
