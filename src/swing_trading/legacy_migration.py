"""P0.3 controlled legacy staging adapter, never a data-certification path.

Every accepted conversion is downgraded to UNVERIFIED/UNKNOWN. Quarantined
inputs are retained in memory with their original object for investigation.
Nothing is saved or pushed to an external source by this module.
"""
from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from .market_data import BarClosure, CanonicalCandle as LegacyCandle
from .quality_audit import FindingSeverity, QualityFinding, QualityFindingRegistry
from .replay import require_utc
from .source_quality import (
    CanonicalCandleV12, CoverageState, LifecycleState, ObservationOrigin,
    ObservationRevisionV12, ProviderObservationKeyV12, QualityState,
    SourceEvidence,
)


def _filled(x: object) -> bool:
    return isinstance(x, str) and bool(x.strip())


def _hash(x: object) -> bool:
    return isinstance(x, str) and len(x) == 64 and all(
        c in "0123456789abcdef" for c in x
    )


@dataclass(frozen=True)
class LegacyMigrationEnvelope:
    """Explicit per-record mapping, NOT proof that the mappings are correct."""
    row_reference: str
    legacy: object
    project_id: str
    source_snapshot_id: str
    source_stream_id: str
    origin: ObservationOrigin
    adjustment_revision: str
    ingestion_revision: str
    normalized_digest_sha256: str | None


@dataclass(frozen=True)
class QuarantinedRow:
    row_reference: str
    reason_code: str
    raw_digest_sha256: str | None
    original: object

    def __post_init__(self) -> None:
        if not _filled(self.row_reference) or not _filled(self.reason_code):
            raise ValueError("Quarantine row requires reference and reason")


@dataclass(frozen=True)
class MigrationBatchResult:
    migrated: tuple[CanonicalCandleV12, ...]
    quarantined: tuple[QuarantinedRow, ...]
    finding_registry: QualityFindingRegistry
    attempted_count: int

    def __post_init__(self) -> None:
        if self.attempted_count != len(self.migrated) + len(self.quarantined):
            raise ValueError("Every input must have exactly one migration outcome")
        if any(c.quality_state is not QualityState.UNVERIFIED for c in self.migrated):
            raise ValueError("Legacy migration may never promote source quality")

    @property
    def counts(self) -> dict[str, int]:
        return {
            "attempted": self.attempted_count,
            "staged_unverified": len(self.migrated),
            "quarantined": len(self.quarantined),
            "open_blockers": len(self.finding_registry.open_blockers()),
        }


def _legacy_id(row: LegacyMigrationEnvelope) -> tuple[object, ...] | None:
    c = row.legacy
    if not isinstance(c, LegacyCandle):
        return None
    return (c.market_bar_key, c.observation_key.provider_id,
            c.observation_key.endpoint, c.observation_key.source_record_id,
            c.revision.revision_id)


def _finding(row: LegacyMigrationEnvelope, code: str, as_of_utc: datetime) -> QualityFinding:
    c = row.legacy
    if isinstance(c, LegacyCandle):
        period = (c.market_bar_key.bar_start_utc, c.bar_end_utc)
        source_ids = (c.observation_key.source_record_id,)
    else:
        period, source_ids = (as_of_utc, as_of_utc), (row.row_reference,)
    return QualityFinding(
        code=code, severity=FindingSeverity.BLOCK,
        evidence="Controlled legacy migration requires separate provider and session verification",
        affected_range_utc=period,
        source_record_ids=source_ids,
        observed=code,
        expected="Typed v1.2 identity and independently verified source quality",
        blocking_dependencies=("SOURCE_RESOLUTION", "CONFIRMED_SIGNALS", "HISTORICAL_BACKTEST"),
        first_seen_utc=as_of_utc, last_seen_utc=as_of_utc,
    )


def migrate_batch(
    envelopes: tuple[LegacyMigrationEnvelope, ...], as_of_utc: datetime
) -> MigrationBatchResult:
    """Quarantine uncertain records; preserve original ordering and identities.

    Duplicate same-provider/same-revision observations are quarantined in full.
    Different legitimate revisions remain separate and must be resolved later.
    """
    require_utc(as_of_utc)
    if not isinstance(envelopes, tuple) or any(
        not isinstance(r, LegacyMigrationEnvelope) for r in envelopes
    ):
        raise TypeError("Expected tuple[LegacyMigrationEnvelope]")

    identities = [_legacy_id(r) for r in envelopes]
    duplicate_counts = Counter(k for k in identities if k is not None)
    reference_counts = Counter(r.row_reference for r in envelopes)
    migrated: list[CanonicalCandleV12] = []
    quarantined: list[QuarantinedRow] = []
    registry = QualityFindingRegistry()

    for row, identity in zip(envelopes, identities):
        c = row.legacy
        code: str | None = None
        if not _filled(row.row_reference):
            raise ValueError("Every input must have a nonempty row_reference")
        if reference_counts[row.row_reference] > 1:
            code = "DUPLICATE_ROW_REFERENCE"
        elif not isinstance(c, LegacyCandle):
            code = "INVALID_LEGACY_RECORD"
        elif identity is not None and duplicate_counts[identity] > 1:
            code = "DUPLICATE_OBSERVATION_REVISION"
        elif c.closure not in (BarClosure.OPEN, BarClosure.CLOSED):
            code = "UNKNOWN_LEGACY_LIFECYCLE"
        elif not all(_filled(v) for v in (
            row.project_id, row.source_snapshot_id, row.source_stream_id,
            row.adjustment_revision, row.ingestion_revision,
        )) or not isinstance(row.origin, ObservationOrigin):
            code = "PROVENANCE_MISSING"
        elif not _hash(row.normalized_digest_sha256):
            code = "NORMALIZED_DIGEST_MISSING"
        elif (c.revision.retrieved_at_utc > as_of_utc
              or c.revision.first_known_time_utc > as_of_utc):
            code = "REVISION_NOT_YET_AVAILABLE"

        if code is None:
            try:
                observation = ProviderObservationKeyV12(
                    row.project_id, c.market_bar_key, c.observation_key.provider_id,
                    row.origin, row.source_stream_id,
                )
                revision = ObservationRevisionV12(
                    observation, c.revision.revision_id, row.adjustment_revision,
                    row.ingestion_revision, c.revision.first_known_time_utc,
                    c.revision.retrieved_at_utc,
                )
                evidence = SourceEvidence(
                    c.observation_key.endpoint, row.source_snapshot_id,
                    c.observation_key.source_record_id,
                    False, False, False, False, False,
                )
                flags = {"LEGACY_EVIDENCE_UNVERIFIED"}
                if c.volume is None:
                    flags.add("VOLUME_MISSING")
                if (c.observed_minutes is not None and c.expected_minutes is not None
                        and c.observed_minutes < c.expected_minutes):
                    flags.add("SPARSE_MINUTES_UNVERIFIED")
                staged = CanonicalCandleV12(
                    market_bar_key=c.market_bar_key, observation_key=observation,
                    observation_revision=revision, bar_end_utc=c.bar_end_utc,
                    open=c.open, high=c.high, low=c.low, close=c.close,
                    volume=c.volume, matched_value=c.matched_value,
                    observed_minutes=c.observed_minutes, expected_minutes=c.expected_minutes,
                    source_event_ids=(), raw_digest_sha256=c.revision.raw_digest_sha256,
                    normalized_digest_sha256=row.normalized_digest_sha256,
                    retrieved_at_utc=c.revision.retrieved_at_utc,
                    verified_at_utc=None,
                    lifecycle_state=(LifecycleState.CLOSED if c.closure is BarClosure.CLOSED
                                     else LifecycleState.OPEN),
                    coverage_state=CoverageState.UNKNOWN,
                    quality_state=QualityState.UNVERIFIED,
                    calendar_cutoff_verified=False,
                    quality_flags=frozenset(flags), provenance=evidence,
                )
            except (TypeError, ValueError):
                code = "MIGRATION_VALIDATION_FAILED"
            else:
                migrated.append(staged)
                registry = registry.append(_finding(row, "LEGACY_EVIDENCE_UNVERIFIED", as_of_utc))
                continue

        raw = c.revision.raw_digest_sha256 if isinstance(c, LegacyCandle) else None
        quarantined.append(QuarantinedRow(row.row_reference, code, raw, c))
        registry = registry.append(_finding(row, code, as_of_utc))

    return MigrationBatchResult(
        tuple(migrated), tuple(quarantined), registry, len(envelopes),
    )
