"""P0.3 quality finding and dataset manifest contracts (engineering, not certification).

The registry is immutable and append-only by construction. It never resolves a
finding automatically. Source: canonical Drive 05 Data Contract, §2 and §4.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .market_data import PriceBasis
from .replay import require_utc


class FindingSeverity(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    BLOCK = "BLOCK"


class ResolutionStatus(str, Enum):
    OPEN = "OPEN"
    VERIFIED_RESOLVED = "VERIFIED_RESOLVED"
    WAIVED_WITH_APPROVAL = "WAIVED_WITH_APPROVAL"


class AdjustmentConsistency(str, Enum):
    UNKNOWN = "UNKNOWN"
    VERIFIED = "VERIFIED"
    CONFLICT = "CONFLICT"


def _nonblank(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(field + " must be nonempty")


def _sha(value: str, field: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(
        c not in "0123456789abcdef" for c in value
    ):
        raise ValueError(field + " must be lowercase SHA-256")


def _string_tuple(values: tuple[str, ...], field: str) -> None:
    if not isinstance(values, tuple) or any(
        not isinstance(v, str) or not v.strip() for v in values
    ):
        raise ValueError(field + " must be a tuple of nonempty strings")


@dataclass(frozen=True)
class QualityFinding:
    code: str
    severity: FindingSeverity
    evidence: str
    affected_range_utc: tuple[datetime, datetime]
    source_record_ids: tuple[str, ...]
    observed: str
    expected: str
    blocking_dependencies: tuple[str, ...]
    first_seen_utc: datetime
    last_seen_utc: datetime
    resolution_status: ResolutionStatus = ResolutionStatus.OPEN
    resolution_reference: str | None = None

    def __post_init__(self) -> None:
        _nonblank(self.code, "code")
        _nonblank(self.evidence, "evidence")
        if not isinstance(self.severity, FindingSeverity):
            raise TypeError("Finding severity must be an enum")
        if not isinstance(self.resolution_status, ResolutionStatus):
            raise TypeError("Finding resolution status must be an enum")
        if (not isinstance(self.affected_range_utc, tuple)
                or len(self.affected_range_utc) != 2):
            raise ValueError("Finding range must have two UTC timestamps")
        start, end = self.affected_range_utc
        for t in (start, end, self.first_seen_utc, self.last_seen_utc):
            require_utc(t)
        if start > end or self.first_seen_utc > self.last_seen_utc:
            raise ValueError("Finding times are inverted")
        _string_tuple(self.source_record_ids, "source_record_ids")
        _string_tuple(self.blocking_dependencies, "blocking_dependencies")
        if not isinstance(self.observed, str) or not isinstance(self.expected, str):
            raise TypeError("Finding observed/expected must be text")
        if self.resolution_status is ResolutionStatus.OPEN:
            if self.resolution_reference is not None:
                raise ValueError("OPEN finding cannot carry a resolution reference")
        else:
            _nonblank(self.resolution_reference, "resolution_reference")

    @property
    def is_open_block(self) -> bool:
        return self.severity is FindingSeverity.BLOCK and self.resolution_status is ResolutionStatus.OPEN


@dataclass(frozen=True)
class QualityFindingRegistry:
    findings: tuple[QualityFinding, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.findings, tuple) or any(
            not isinstance(f, QualityFinding) for f in self.findings
        ):
            raise TypeError("Immutable typed findings required")

    def append(self, finding: QualityFinding) -> "QualityFindingRegistry":
        if not isinstance(finding, QualityFinding):
            raise TypeError("Expected QualityFinding")
        return QualityFindingRegistry(self.findings + (finding,))

    def open_blockers(self) -> tuple[QualityFinding, ...]:
        return tuple(f for f in self.findings if f.is_open_block)


@dataclass(frozen=True)
class DatasetManifestV12:
    """Typed manifest only, not an automatic VERIFIED certificate."""
    dataset_id: str
    source_id: str
    coverage_start_utc: datetime
    coverage_end_utc: datetime
    bar_count: int
    gaps_by_session: tuple[str, ...]
    duplicate_timestamps: int
    out_of_order: int
    raw_adjusted_consistency: AdjustmentConsistency
    corporate_action_revision: str
    calendar_version: str
    price_basis: PriceBasis
    market_context_sources: tuple[str, ...]
    quality_findings: tuple[QualityFinding, ...]
    snapshot_digest_sha256: str
    fetched_at_utc: datetime
    verified_at_utc: datetime | None
    provenance_chain: tuple[str, ...]
    repository_location: str

    def __post_init__(self) -> None:
        for name in ("dataset_id", "source_id", "corporate_action_revision",
                     "calendar_version", "repository_location"):
            _nonblank(getattr(self, name), name)
        for stamp in (self.coverage_start_utc, self.coverage_end_utc, self.fetched_at_utc):
            require_utc(stamp)
        if self.coverage_end_utc < self.coverage_start_utc:
            raise ValueError("Inverted dataset coverage")
        if self.verified_at_utc is not None:
            require_utc(self.verified_at_utc)
            if self.verified_at_utc < self.fetched_at_utc:
                raise ValueError("Verification before retrieval")
        for name in ("bar_count", "duplicate_timestamps", "out_of_order"):
            n = getattr(self, name)
            if type(n) is not int or n < 0:
                raise ValueError(name + " must be nonnegative integer")
        if not isinstance(self.raw_adjusted_consistency, AdjustmentConsistency):
            raise TypeError("Adjustment consistency is unknown")
        if not isinstance(self.price_basis, PriceBasis):
            raise TypeError("Price basis must be a valid enum")
        for name in ("gaps_by_session", "market_context_sources", "provenance_chain"):
            _string_tuple(getattr(self, name), name)
        if not isinstance(self.quality_findings, tuple) or any(
            not isinstance(f, QualityFinding) for f in self.quality_findings
        ):
            raise TypeError("Typed quality findings required")
        _sha(self.snapshot_digest_sha256, "snapshot_digest_sha256")

    def structural_prerequisites(self, as_of_utc: datetime) -> bool:
        """Necessary checks only. No source entitlement or trade authorization."""
        require_utc(as_of_utc)
        return (self.verified_at_utc is not None
                and self.verified_at_utc <= as_of_utc
                and self.fetched_at_utc <= as_of_utc
                and self.bar_count > 0
                and self.duplicate_timestamps == 0 and self.out_of_order == 0
                and not self.gaps_by_session
                and self.raw_adjusted_consistency is AdjustmentConsistency.VERIFIED
                and self.price_basis is not PriceBasis.UNKNOWN
                and not any(f.is_open_block for f in self.quality_findings))
