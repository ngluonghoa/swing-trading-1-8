"""P0.3 quality registry and manifest contract checks, synthetic-only."""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from swing_trading.market_data import PriceBasis
from swing_trading.quality_audit import (
    AdjustmentConsistency, DatasetManifestV12, FindingSeverity,
    QualityFinding, QualityFindingRegistry, ResolutionStatus,
)

T = datetime(2026, 11, 6, 2, tzinfo=timezone.utc)
at = lambda m: T + timedelta(minutes=m)


def finding(**kwargs):
    data = dict(
        code="SOURCE_TIME_AMBIGUOUS",
        severity=FindingSeverity.BLOCK,
        evidence="SYNTHETIC: timestamp not confirmed",
        affected_range_utc=(T, at(15)),
        source_record_ids=("test-row-1",),
        observed="Unknown", expected="Versioned endpoint parser",
        blocking_dependencies=("M15_TRIGGER",),
        first_seen_utc=at(20), last_seen_utc=at(20),
    )
    data.update(kwargs)
    return QualityFinding(**data)


def manifest(**kwargs):
    data = dict(
        dataset_id="FIXTURE-DATASET", source_id="FIXTURE",
        coverage_start_utc=T, coverage_end_utc=at(60),
        bar_count=4, gaps_by_session=(),
        duplicate_timestamps=0, out_of_order=0,
        raw_adjusted_consistency=AdjustmentConsistency.VERIFIED,
        corporate_action_revision="FIXTURE-CA", calendar_version="FIXTURE-CAL",
        price_basis=PriceBasis.RAW, market_context_sources=(),
        quality_findings=(), snapshot_digest_sha256="f" * 64,
        fetched_at_utc=at(80), verified_at_utc=at(90),
        provenance_chain=("synthetic://test",), repository_location="fixture://only",
    )
    data.update(kwargs)
    return DatasetManifestV12(**data)


class QualityAuditTests(unittest.TestCase):
    def test_append_only_registry_cannot_erase_original(self):
        base = QualityFindingRegistry()
        f = finding()
        next_reg = base.append(f)
        self.assertEqual(base.findings, ())
        self.assertEqual(next_reg.open_blockers(), (f,))
        self.assertEqual(len(next_reg.findings), 1)
        with self.assertRaises(TypeError):
            next_reg.append("fake")

    def test_warn_does_not_clear_open_block_or_modify_it(self):
        a = finding()
        b = finding(code="SOURCE_LAG", severity=FindingSeverity.WARN)
        registry = QualityFindingRegistry((a, b))
        self.assertEqual(registry.open_blockers(), (a,))
        self.assertEqual(registry.findings[1], b)

    def test_resolution_requires_explicit_reference(self):
        with self.assertRaises(ValueError):
            finding(resolution_status=ResolutionStatus.VERIFIED_RESOLVED)
        with self.assertRaises(ValueError):
            finding(resolution_status=ResolutionStatus.WAIVED_WITH_APPROVAL)
        with self.assertRaises(ValueError):
            finding(resolution_reference="silent", resolution_status=ResolutionStatus.OPEN)
        documented = finding(resolution_status=ResolutionStatus.WAIVED_WITH_APPROVAL,
                             resolution_reference="fixture-approval-ref")
        self.assertFalse(documented.is_open_block)
        self.assertEqual(documented.resolution_reference, "fixture-approval-ref")

    def test_finding_time_range_and_schema_validation(self):
        with self.assertRaises(ValueError):
            finding(affected_range_utc=(at(15), T))
        with self.assertRaises(ValueError):
            finding(first_seen_utc=at(30), last_seen_utc=at(20))
        with self.assertRaises(ValueError):
            finding(first_seen_utc=T.replace(tzinfo=None))
        with self.assertRaises(TypeError):
            finding(severity="BLOCK")
        with self.assertRaises(ValueError):
            finding(source_record_ids=("ok", ""))
        with self.assertRaises(ValueError):
            finding(code="")

    def test_fixture_manifest_only_structural_not_entitlement(self):
        m = manifest()
        self.assertTrue(m.structural_prerequisites(at(120)))
        self.assertFalse(m.structural_prerequisites(at(89)))
        self.assertFalse(replace(m, verified_at_utc=None).structural_prerequisites(at(120)))
        self.assertFalse(replace(m, bar_count=0).structural_prerequisites(at(120)))
        self.assertFalse(replace(m, price_basis=PriceBasis.UNKNOWN).structural_prerequisites(at(120)))
        self.assertFalse(replace(m, raw_adjusted_consistency=AdjustmentConsistency.UNKNOWN)
                         .structural_prerequisites(at(120)))

    def test_missing_gaps_duplicate_order_and_open_blocks_fail(self):
        m = manifest()
        self.assertFalse(replace(m, gaps_by_session=("fixture-gap",))
                         .structural_prerequisites(at(120)))
        self.assertFalse(replace(m, duplicate_timestamps=1).structural_prerequisites(at(120)))
        self.assertFalse(replace(m, out_of_order=1).structural_prerequisites(at(120)))
        self.assertFalse(replace(m, quality_findings=(finding(),))
                         .structural_prerequisites(at(120)))
        warning = finding(severity=FindingSeverity.WARN)
        self.assertTrue(replace(m, quality_findings=(warning,))
                        .structural_prerequisites(at(120)))

    def test_dataset_bad_digest_dates_or_type_rejected(self):
        with self.assertRaises(ValueError):
            manifest(snapshot_digest_sha256="bad")
        with self.assertRaises(ValueError):
            manifest(coverage_start_utc=at(61))
        with self.assertRaises(ValueError):
            manifest(verified_at_utc=at(79))
        with self.assertRaises(ValueError):
            manifest(coverage_start_utc=T.replace(tzinfo=None))
        with self.assertRaises(ValueError):
            manifest(bar_count=True)
        with self.assertRaises(TypeError):
            manifest(price_basis="RAW")
        with self.assertRaises(TypeError):
            manifest(raw_adjusted_consistency="VERIFIED")
        with self.assertRaises(TypeError):
            manifest(quality_findings=("bad",))
        with self.assertRaises(ValueError):
            manifest(provenance_chain=("",))

    def test_manifest_guard_rejects_naive_asof(self):
        with self.assertRaises(ValueError):
            manifest().structural_prerequisites(T.replace(tzinfo=None))


if __name__ == "__main__":
    unittest.main()
