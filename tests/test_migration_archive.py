"""P0.4B synthetic raw-byte lineage tests. Never uses live SSI data."""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest

from swing_trading.durable_evidence import EvidenceCorrupt, EvidenceStore, State, ZERO
from swing_trading.evidence_recovery import backup_verified, restore_verified
from swing_trading.market_data import BarClosure
from swing_trading.migration_archive import RawSourceBinding, archive_migration_batch
from swing_trading.source_quality import QualityState
from test_legacy_migration import at, legacy, row


def sample(raw=b"fixture-raw-byte-source", *, revision="r1",
           closure=BarClosure.CLOSED, ref="row-1"):
    c = legacy(closure=closure, revision=revision)
    c = replace(c, revision=replace(c.revision, raw_digest_sha256=sha256(raw).hexdigest()))
    e = row(c, row_reference=ref)
    b = RawSourceBinding(ref, c.observation_key.source_record_id,
                         e.source_snapshot_id, raw, sha256(raw).hexdigest())
    return e, b


class MigrationArchiveTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.store = EvidenceStore(self.root / "original.sqlite")
        self.store.initialize()

    def self_empty(self):
        self.assertEqual(self.store.verify(), (0, ZERO))

    def test_staging_keeps_original_bytes_and_never_verifies(self):
        e, b = sample(b"\x00synthetic\xff")
        result = archive_migration_batch(self.store, "batch-1", (e,), (b,), at(30),
                                         expected_tip_sha256=ZERO)
        self.assertEqual(result.record_count, 1)
        self.assertEqual(result.receipts[0].state, State.STAGED_UNVERIFIED)
        self.assertEqual(result.receipts[0].raw_sha256, b.declared_sha256)
        self.assertEqual(result.migration.migrated[0].quality_state, QualityState.UNVERIFIED)
        self.assertFalse(result.migration.migrated[0].confirmation_prerequisites(at(50)))
        self.assertEqual(self.store.read_verified_bytes("batch-1", b.row_reference), b.raw_bytes)
        self.assertEqual(self.store.verify(), (1, result.chain_tip_sha256))

    def test_unknown_lifecycle_quarantine_persists_same_raw_bytes(self):
        e, b = sample(closure=BarClosure.UNKNOWN)
        x = archive_migration_batch(self.store, "batch-1", (e,), (b,), at(30))
        self.assertEqual(x.receipts[0].state, State.QUARANTINED)
        self.assertEqual(x.receipts[0].reason_code, "UNKNOWN_LEGACY_LIFECYCLE")
        self.assertEqual(x.migration.counts["staged_unverified"], 0)
        self.assertEqual(self.store.read_verified_bytes("batch-1", "row-1"), b.raw_bytes)

    def test_mixed_outcomes_and_backup_restore_roundtrip(self):
        a, raw_a = sample(b"raw-a", ref="a")
        b, raw_b = sample(b"raw-b", ref="b", revision="r2",
                          closure=BarClosure.UNKNOWN)
        x = archive_migration_batch(self.store, "batch-mixed",
                                    (a, b), (raw_a, raw_b), at(30))
        self.assertEqual((x.migration.counts["staged_unverified"],
                          x.migration.counts["quarantined"]), (1, 1))
        self.assertEqual([r.state for r in x.receipts],
                         [State.STAGED_UNVERIFIED, State.QUARANTINED])
        self.assertEqual(backup_verified(self.store, self.root / "backup.sqlite"),
                         (2, x.chain_tip_sha256))
        recovered = restore_verified(self.root / "backup.sqlite",
                                     self.root / "recovered.sqlite")
        self.assertEqual(recovered.verify(), (2, x.chain_tip_sha256))
        for raw in (raw_a, raw_b):
            self.assertEqual(recovered.read_verified_bytes("batch-mixed", raw.row_reference),
                             raw.raw_bytes)

    def test_future_revision_quarantined_as_of(self):
        e, b = sample()
        later = replace(e.legacy, revision=replace(
            e.legacy.revision, first_known_time_utc=at(40), retrieved_at_utc=at(41)))
        e = replace(e, legacy=later)
        x = archive_migration_batch(self.store, "future", (e,), (b,), at(30))
        self.assertEqual(x.receipts[0].state, State.QUARANTINED)
        self.assertEqual(x.receipts[0].reason_code, "REVISION_NOT_YET_AVAILABLE")

    def test_raw_digest_mismatch_never_stored(self):
        e, raw = sample()
        with self.assertRaises(ValueError):
            RawSourceBinding(raw.row_reference, raw.source_record_id,
                             raw.source_snapshot_id, b"not original", raw.declared_sha256)
        altered = replace(e.legacy, revision=replace(
            e.legacy.revision, raw_digest_sha256="a" * 64))
        with self.assertRaises(ValueError):
            archive_migration_batch(self.store, "bad", (replace(e, legacy=altered),),
                                    (raw,), at(30))
        self.self_empty()

    def test_source_record_and_snapshot_mismatch_fail_closed(self):
        e, b = sample()
        for variant in (replace(b, source_record_id="wrong"),
                        replace(b, source_snapshot_id="wrong"),
                        replace(b, row_reference="wrong")):
            with self.subTest(variant=variant):
                with self.assertRaises(ValueError):
                    archive_migration_batch(self.store, "bad", (e,), (variant,), at(30))
        self.self_empty()

    def test_no_silent_row_pairing_or_partial_missing_input(self):
        e1, b1 = sample(b"raw-one", ref="one")
        e2, b2 = sample(b"raw-two", ref="two", revision="r2")
        with self.assertRaises(ValueError):
            archive_migration_batch(self.store, "missing", (e1, e2), (b1,), at(30))
        with self.assertRaises(ValueError):
            archive_migration_batch(self.store, "swapped", (e1, e2), (b2, b1), at(30))
        with self.assertRaises(ValueError):
            archive_migration_batch(self.store, "duplicates", (e1, replace(e2, row_reference="one")),
                                    (b1, b2), at(30))
        self.self_empty()

    def test_duplicate_batch_id_and_stale_tip_do_not_write(self):
        e, b = sample()
        one = archive_migration_batch(self.store, "batch-1", (e,), (b,), at(30))
        with self.assertRaises(sqlite3.IntegrityError):
            archive_migration_batch(self.store, "batch-1", (e,), (b,), at(30))
        with self.assertRaises(EvidenceCorrupt):
            archive_migration_batch(self.store, "batch-2", (e,), (b,), at(30),
                                    expected_tip_sha256=ZERO)
        self.assertEqual(self.store.verify(), (1, one.chain_tip_sha256))

    def test_invalid_raw_record_is_still_quarantined_with_explicit_binding(self):
        e = row({"unparsed": "synthetic"}, row_reference="invalid")
        raw = b"some-invalid-fixture"
        b = RawSourceBinding("invalid", "explicit-fixture-record", e.source_snapshot_id,
                             raw, sha256(raw).hexdigest())
        x = archive_migration_batch(self.store, "invalid", (e,), (b,), at(30))
        self.assertEqual(x.receipts[0].state, State.QUARANTINED)
        self.assertEqual(x.receipts[0].reason_code, "INVALID_LEGACY_RECORD")
        self.assertEqual(self.store.read_verified_bytes("invalid", "invalid"), raw)

    def test_invalid_input_schema_and_naive_clock_fail_before_write(self):
        e, b = sample()
        with self.assertRaises(ValueError):
            archive_migration_batch(self.store, "x", (), (), at(30))
        with self.assertRaises(ValueError):
            archive_migration_batch(self.store, "x", (e,), (b,),
                                    at(30).replace(tzinfo=None))
        with self.assertRaises(TypeError):
            archive_migration_batch(self.store, "x", [e], (b,), at(30))
        self.self_empty()


if __name__ == "__main__":
    unittest.main()
