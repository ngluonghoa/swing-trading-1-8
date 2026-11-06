"""P0.3 migration fixtures: never grant VERIFIED from legacy."""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from swing_trading.legacy_migration import LegacyMigrationEnvelope, migrate_batch
from swing_trading.market_data import (
    BarClosure, CanonicalCandle, InstrumentClass, MarketBarKey, ObservationRevision,
    PriceBasis, ProviderObservationKey, Quality, Timeframe,
)
from swing_trading.source_quality import (
    CoverageState, LifecycleState, ObservationOrigin, QualityState, resolve_as_known,
)

T = datetime(2026, 11, 6, 2, tzinfo=timezone.utc)
at = lambda m: T + timedelta(minutes=m)


def legacy(*, closure=BarClosure.CLOSED, quality=Quality.VERIFIED,
           volume=0, observed=15, revision="r1"):
    key = MarketBarKey(
        "HOSE:ABC:fixture", "HOSE", InstrumentClass.STOCK, Timeframe.M15,
        "fixture-session", T, PriceBasis.RAW, "fixture-calendar", "fixture-aggregation",
    )
    return CanonicalCandle(
        key, ProviderObservationKey("FIXTURE", "synthetic://bars", "row-1"),
        ObservationRevision(revision, "a" * 64, at(15), at(20)),
        at(15), Decimal("10"), Decimal("12"), Decimal("9"), Decimal("11"),
        volume, quality, closure, observed, 15, None,
    )


def row(c=None, **kw):
    values = dict(
        row_reference="batch-1:row-1", legacy=legacy() if c is None else c,
        project_id="SWING_1_8", source_snapshot_id="fixture-snapshot",
        source_stream_id="fixture-M15", origin=ObservationOrigin.NATIVE,
        adjustment_revision="UNKNOWN_LEGACY", ingestion_revision="adapter-v1",
        normalized_digest_sha256="b" * 64,
    )
    values.update(kw)
    return LegacyMigrationEnvelope(**values)


class MigrationTests(unittest.TestCase):
    def test_legacy_verified_never_upgrades_and_zero_volume_kept(self):
        result = migrate_batch((row(),), at(30))
        self.assertEqual(result.counts["staged_unverified"], 1)
        self.assertEqual(result.counts["quarantined"], 0)
        c = result.migrated[0]
        self.assertEqual(c.market_bar_key, legacy().market_bar_key)
        self.assertEqual(c.lifecycle_state, LifecycleState.CLOSED)
        self.assertEqual(c.coverage_state, CoverageState.UNKNOWN)
        self.assertEqual(c.quality_state, QualityState.UNVERIFIED)
        self.assertFalse(c.calendar_cutoff_verified)
        self.assertIsNone(c.verified_at_utc)
        self.assertEqual(c.volume, 0)
        self.assertEqual(c.observation_revision.adjustment_revision, "UNKNOWN_LEGACY")
        self.assertEqual(c.observation_revision.ingestion_revision, "adapter-v1")
        self.assertEqual(c.raw_digest_sha256, "a" * 64)
        self.assertEqual(c.normalized_digest_sha256, "b" * 64)
        self.assertEqual(c.source_event_ids, ())
        self.assertFalse(c.provenance.entitlement_verified)
        self.assertFalse(c.provenance.timestamp_semantics_verified)
        self.assertFalse(c.confirmation_prerequisites(at(60)))
        self.assertEqual(result.counts["open_blockers"], 1)

    def test_legacy_open_remains_open_and_no_confirmation(self):
        result = migrate_batch((row(legacy(closure=BarClosure.OPEN)),), at(30))
        self.assertEqual(result.migrated[0].lifecycle_state, LifecycleState.OPEN)
        self.assertFalse(result.migrated[0].confirmation_prerequisites(at(40)))

    def test_missing_volume_and_sparse_input_preserved_without_zero_fill(self):
        result = migrate_batch((row(legacy(volume=None, observed=7)),), at(30))
        c = result.migrated[0]
        self.assertIsNone(c.volume)
        self.assertEqual(c.observed_minutes, 7)
        self.assertEqual(c.expected_minutes, 15)
        self.assertIn("VOLUME_MISSING", c.quality_flags)
        self.assertIn("SPARSE_MINUTES_UNVERIFIED", c.quality_flags)
        self.assertFalse(c.confirmation_prerequisites(at(50)))

    def test_unknown_lifecycle_is_quarantined_not_assumed_closed(self):
        original = legacy(closure=BarClosure.UNKNOWN)
        result = migrate_batch((row(original),), at(30))
        self.assertFalse(result.migrated)
        self.assertIs(result.quarantined[0].original, original)
        self.assertEqual(result.quarantined[0].reason_code, "UNKNOWN_LEGACY_LIFECYCLE")

    def test_mapping_or_normalized_digest_missing_is_quarantined(self):
        variants = (
            row(source_stream_id=""),
            row(project_id=""),
            row(adjustment_revision=""),
            row(source_snapshot_id=""),
            row(origin="NATIVE"),
            row(normalized_digest_sha256=None),
            row(normalized_digest_sha256="not-a-sha"),
        )
        for variant in variants:
            with self.subTest(variant=variant):
                x = migrate_batch((variant,), at(30))
                self.assertFalse(x.migrated)
                self.assertEqual(len(x.quarantined), 1)
                self.assertEqual(len(x.finding_registry.open_blockers()), 1)

    def test_future_revision_is_quarantined(self):
        c = legacy()
        later = replace(c, revision=replace(c.revision,
                          first_known_time_utc=at(40), retrieved_at_utc=at(41)))
        x = migrate_batch((row(later),), at(30))
        self.assertEqual(x.quarantined[0].reason_code, "REVISION_NOT_YET_AVAILABLE")

    def test_duplicate_revision_quarantines_both_rows_not_first_wins(self):
        c = legacy()
        a = row(c, row_reference="record-a")
        b = row(c, row_reference="record-b")
        x = migrate_batch((a, b), at(30))
        self.assertEqual(x.counts["attempted"], 2)
        self.assertEqual(x.counts["quarantined"], 2)
        self.assertFalse(x.migrated)
        self.assertEqual({r.reason_code for r in x.quarantined},
                         {"DUPLICATE_OBSERVATION_REVISION"})
        self.assertIs(x.quarantined[0].original, c)
        self.assertIs(x.quarantined[1].original, c)

    def test_same_audit_row_reference_with_distinct_revisions_quarantines_both(self):
        x = migrate_batch((
            row(legacy(revision="r1"), row_reference="same-row"),
            row(legacy(revision="r2"), row_reference="same-row"),
        ), at(30))
        self.assertFalse(x.migrated)
        self.assertEqual(len(x.quarantined), 2)
        self.assertEqual({q.reason_code for q in x.quarantined},
                         {"DUPLICATE_ROW_REFERENCE"})

    def test_distinct_corrections_remain_separate_and_conflict(self):
        a = legacy(revision="r1")
        b = legacy(revision="r2")
        x = migrate_batch((row(a, row_reference="a"), row(b, row_reference="b")), at(30))
        self.assertEqual(x.counts["staged_unverified"], 2)
        decision = resolve_as_known(a.market_bar_key, x.migrated, at(30))
        self.assertEqual(decision.reason, "SOURCE_OR_REVISION_CONFLICT")
        self.assertIsNone(decision.selected)
        self.assertFalse(decision.confirmation_prerequisites(at(30)))

    def test_invalid_type_quarantined_and_original_preserved(self):
        original = {"untrusted": "raw"}
        x = migrate_batch((row(original),), at(30))
        self.assertEqual(x.quarantined[0].reason_code, "INVALID_LEGACY_RECORD")
        self.assertIs(x.quarantined[0].original, original)
        self.assertEqual(x.quarantined[0].raw_digest_sha256, None)

    def test_asof_utc_required_and_wrong_envelope_type_rejected(self):
        with self.assertRaises(ValueError):
            migrate_batch((row(),), T.replace(tzinfo=None))
        with self.assertRaises(TypeError):
            migrate_batch([row()], at(30))
        with self.assertRaises(TypeError):
            migrate_batch(("bad",), at(30))

    def test_empty_batch_and_counts(self):
        x = migrate_batch((), at(30))
        self.assertEqual(x.counts, dict(attempted=0, staged_unverified=0,
                                        quarantined=0, open_blockers=0))

    def test_missing_row_reference_cannot_be_lost(self):
        with self.assertRaises(ValueError):
            migrate_batch((row(row_reference=""),), at(30))


if __name__ == "__main__":
    unittest.main()
