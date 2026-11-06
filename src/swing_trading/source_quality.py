"""P0.2 normative-shaped v1.2 source lineage and 3-axis candle quality.

Engineering contracts ONLY. These objects cannot certify external sources, calendar
cutoffs, permissions, corrected history, or a trade. Legacy market_data dataclasses
remain for compatibility until a separately reviewed migration.
Canonical source: Google Drive 05 Data Contract, sections 2–4 and 17–18.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from .market_data import MarketBarKey, PriceBasis
from .replay import require_utc


def _nonblank(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label + " is required")


def _sha256(value: str, label: str) -> None:
    if (not isinstance(value, str) or len(value) != 64
            or any(c not in "0123456789abcdef" for c in value)):
        raise ValueError(label + " must be lowercase SHA-256")


class ObservationOrigin(str, Enum):
    NATIVE = "NATIVE"
    DERIVED = "DERIVED"
    IMPORT = "IMPORT"


class LifecycleState(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class CoverageState(str, Enum):
    COMPLETE = "COMPLETE"
    SESSION_PARTIAL = "SESSION_PARTIAL"
    RANGE_PARTIAL = "RANGE_PARTIAL"
    SPARSE_UNVERIFIED = "SPARSE_UNVERIFIED"
    UNKNOWN = "UNKNOWN"
    INVALID = "INVALID"


class QualityState(str, Enum):
    VERIFIED = "VERIFIED"
    WARN = "WARN"
    UNVERIFIED = "UNVERIFIED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class ProviderObservationKeyV12:
    project_id: str
    market_bar_key: MarketBarKey
    provider_id: str
    origin: ObservationOrigin
    source_stream_id: str

    def __post_init__(self) -> None:
        for name in ("project_id", "provider_id", "source_stream_id"):
            _nonblank(getattr(self, name), name)
        if not isinstance(self.market_bar_key, MarketBarKey):
            raise TypeError("Observation must refer to a MarketBarKey")
        if not isinstance(self.origin, ObservationOrigin):
            raise TypeError("Unknown observation origin")


@dataclass(frozen=True)
class ObservationRevisionV12:
    observation_key: ProviderObservationKeyV12
    source_revision_or_payload_digest: str
    adjustment_revision: str
    ingestion_revision: str
    first_known_time_utc: datetime
    retrieved_at_utc: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.observation_key, ProviderObservationKeyV12):
            raise TypeError("Revision must reference an observation key")
        for name in ("source_revision_or_payload_digest", "adjustment_revision",
                     "ingestion_revision"):
            _nonblank(getattr(self, name), name)
        require_utc(self.first_known_time_utc)
        require_utc(self.retrieved_at_utc)
        if self.first_known_time_utc > self.retrieved_at_utc:
            raise ValueError("Revision cannot be known after it was retrieved")


@dataclass(frozen=True)
class SourceEvidence:
    """Claims are inputs that MUST be checked against source records externally."""
    endpoint: str
    source_snapshot_id: str
    source_record_id: str
    entitlement_verified: bool
    timestamp_semantics_verified: bool
    price_basis_verified: bool
    coverage_policy_verified: bool
    session_partial_policy_verified: bool = False

    def __post_init__(self) -> None:
        for name in ("endpoint", "source_snapshot_id", "source_record_id"):
            _nonblank(getattr(self, name), name)
        for name in ("entitlement_verified", "timestamp_semantics_verified",
                     "price_basis_verified", "coverage_policy_verified",
                     "session_partial_policy_verified"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(name + " must be explicit bool")


@dataclass(frozen=True)
class CanonicalCandleV12:
    market_bar_key: MarketBarKey
    observation_key: ProviderObservationKeyV12
    observation_revision: ObservationRevisionV12
    bar_end_utc: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int | None
    matched_value: Decimal | None
    observed_minutes: int | None
    expected_minutes: int | None
    source_event_ids: tuple[str, ...]
    raw_digest_sha256: str
    normalized_digest_sha256: str
    retrieved_at_utc: datetime
    verified_at_utc: datetime | None
    lifecycle_state: LifecycleState
    coverage_state: CoverageState
    quality_state: QualityState
    calendar_cutoff_verified: bool
    quality_flags: frozenset[str]
    provenance: SourceEvidence

    def __post_init__(self) -> None:
        if not isinstance(self.market_bar_key, MarketBarKey):
            raise TypeError("Expected MarketBarKey")
        if (not isinstance(self.observation_key, ProviderObservationKeyV12)
                or self.observation_key.market_bar_key != self.market_bar_key):
            raise ValueError("Observation identity does not match market bar")
        if (not isinstance(self.observation_revision, ObservationRevisionV12)
                or self.observation_revision.observation_key != self.observation_key):
            raise ValueError("Revision lineage does not match observation")
        require_utc(self.bar_end_utc)
        require_utc(self.retrieved_at_utc)
        if self.verified_at_utc is not None:
            require_utc(self.verified_at_utc)
            if self.verified_at_utc < self.retrieved_at_utc:
                raise ValueError("Verification cannot predate data retrieval")
        if self.retrieved_at_utc != self.observation_revision.retrieved_at_utc:
            raise ValueError("Candle retrieval timestamp must match revision")
        if self.bar_end_utc <= self.market_bar_key.bar_start_utc:
            raise ValueError("Bar end must be later than bar start")
        prices = (self.open, self.high, self.low, self.close)
        if any(not isinstance(p, Decimal) for p in prices):
            raise TypeError("OHLC requires Decimal, not float")
        if any(not p.is_finite() for p in prices):
            raise ValueError("OHLC must be finite")
        if self.low < 0 or self.low > min(self.open, self.close) or self.high < max(self.open, self.close):
            raise ValueError("Invalid OHLC order")
        if self.volume is not None and (type(self.volume) is not int or self.volume < 0):
            raise ValueError("Volume must be nonnegative integer or explicitly unknown")
        if self.matched_value is not None and (
            not isinstance(self.matched_value, Decimal) or not self.matched_value.is_finite()
            or self.matched_value < 0
        ):
            raise ValueError("Matched value must be finite Decimal or unknown")
        for name in ("observed_minutes", "expected_minutes"):
            v = getattr(self, name)
            if v is not None and (type(v) is not int or v < 0):
                raise ValueError(name + " must be nonnegative integer or unknown")
        if self.observed_minutes is not None and self.expected_minutes is not None:
            if self.observed_minutes > self.expected_minutes:
                raise ValueError("More observed minutes than expected")
        if not isinstance(self.source_event_ids, tuple) or any(
            not isinstance(e, str) or not e for e in self.source_event_ids
        ):
            raise ValueError("Source event IDs must be immutable nonempty strings")
        _sha256(self.raw_digest_sha256, "Raw digest")
        _sha256(self.normalized_digest_sha256, "Normalized digest")
        for name, enum in (("lifecycle_state", LifecycleState),
                           ("coverage_state", CoverageState), ("quality_state", QualityState)):
            if not isinstance(getattr(self, name), enum):
                raise TypeError(name + " must be an explicit enum")
        if type(self.calendar_cutoff_verified) is not bool:
            raise TypeError("Calendar cutoff verification must be explicit")
        if not isinstance(self.quality_flags, frozenset) or any(
            not isinstance(f, str) or not f.strip() for f in self.quality_flags
        ):
            raise ValueError("quality_flags must be frozenset of nonempty codes")
        if not isinstance(self.provenance, SourceEvidence):
            raise TypeError("SourceEvidence is required")

    def confirmation_prerequisites(self, as_of_utc: datetime) -> bool:
        """Only conservative data prerequisites; NEVER a trade/action authorization."""
        require_utc(as_of_utc)
        evidence = self.provenance
        coverage_ok = self.coverage_state is CoverageState.COMPLETE or (
            self.coverage_state is CoverageState.SESSION_PARTIAL
            and evidence.session_partial_policy_verified
        )
        minutes_ok = (self.observed_minutes is None or self.expected_minutes is None
                      or self.observed_minutes == self.expected_minutes
                      or (self.coverage_state is CoverageState.SESSION_PARTIAL
                          and evidence.session_partial_policy_verified))
        return (
            self.lifecycle_state is LifecycleState.CLOSED
            and self.quality_state is QualityState.VERIFIED
            and coverage_ok and minutes_ok
            and self.market_bar_key.price_basis is not PriceBasis.UNKNOWN
            and self.calendar_cutoff_verified
            and not self.quality_flags
            and self.volume is not None
            and self.verified_at_utc is not None
            and self.verified_at_utc <= as_of_utc
            and self.bar_end_utc <= as_of_utc
            and self.observation_revision.first_known_time_utc <= as_of_utc
            and evidence.entitlement_verified
            and evidence.timestamp_semantics_verified
            and evidence.price_basis_verified
            and evidence.coverage_policy_verified
        )


@dataclass(frozen=True)
class ResolvedBarSnapshotV12:
    """No implicit preferred provider or revision: conflicts remain unresolved."""
    market_bar_key: MarketBarKey
    selected: CanonicalCandleV12 | None
    visible_candidate_count: int
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.market_bar_key, MarketBarKey):
            raise TypeError("Resolved snapshot requires MarketBarKey")
        if type(self.visible_candidate_count) is not int or self.visible_candidate_count < 0:
            raise ValueError("Candidate count must be nonnegative integer")
        allowed = {"NO_VISIBLE_REVISION", "SINGLE_VISIBLE_REVISION", "SOURCE_OR_REVISION_CONFLICT"}
        if self.reason not in allowed:
            raise ValueError("Unknown resolution status")
        if self.selected is not None:
            if not isinstance(self.selected, CanonicalCandleV12):
                raise TypeError("Selected snapshot must be CanonicalCandleV12")
            if self.selected.market_bar_key != self.market_bar_key:
                raise ValueError("Selected snapshot market identity mismatch")
            if self.visible_candidate_count != 1 or self.reason != "SINGLE_VISIBLE_REVISION":
                raise ValueError("Selected revision requires a single visible candidate")
        elif self.reason == "SINGLE_VISIBLE_REVISION":
            raise ValueError("Selected revision required for single-candidate status")
        elif self.reason == "NO_VISIBLE_REVISION" and self.visible_candidate_count != 0:
            raise ValueError("Empty status contradicts candidate count")
        elif self.reason == "SOURCE_OR_REVISION_CONFLICT" and self.visible_candidate_count < 2:
            raise ValueError("Conflict requires multiple visible revisions")

    def confirmation_prerequisites(self, as_of_utc: datetime) -> bool:
        return (
            self.selected is not None
            and self.visible_candidate_count == 1
            and self.reason == "SINGLE_VISIBLE_REVISION"
            and self.selected.confirmation_prerequisites(as_of_utc)
        )


def resolve_as_known(
    market_bar_key: MarketBarKey,
    candidates: tuple[CanonicalCandleV12, ...],
    as_of_utc: datetime,
) -> ResolvedBarSnapshotV12:
    """Causal, fail-closed selection, NOT a full approved source resolution policy.

    Future corrections are hidden until first known. Multiple visible source
    observations/revisions are CONFLICT rather than silently choosing latest.
    """
    if not isinstance(market_bar_key, MarketBarKey):
        raise TypeError("Expected MarketBarKey")
    require_utc(as_of_utc)
    if not isinstance(candidates, tuple):
        raise TypeError("Immutable candidate tuple required")
    for candle in candidates:
        if not isinstance(candle, CanonicalCandleV12):
            raise TypeError("Expected CanonicalCandleV12 candidate")
        if candle.market_bar_key != market_bar_key:
            raise ValueError("Mixed market bar keys")
    visible = tuple(c for c in candidates
                    if c.observation_revision.first_known_time_utc <= as_of_utc)
    if len(visible) == 0:
        return ResolvedBarSnapshotV12(market_bar_key, None, 0, "NO_VISIBLE_REVISION")
    if len(visible) != 1:
        return ResolvedBarSnapshotV12(market_bar_key, None, len(visible), "SOURCE_OR_REVISION_CONFLICT")
    return ResolvedBarSnapshotV12(market_bar_key, visible[0], 1, "SINGLE_VISIBLE_REVISION")
