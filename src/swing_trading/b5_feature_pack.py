"""B5 (retest-after-breakout) causal feature extractor, NOT an executable detector.

Master Spec 01 §24.4: B5 R0 prior D1/H1 breakout/pivot, R_C exact
pivot retest, R_E verified M15 reclaim/failed-break, R_F support/volume/risk.
P01–P17 calibration and executable phase predicates remain SPEC_PENDING.
Feature extraction NEVER returns DETECTED, trade, entry/SL/TP or backtest P&L.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from .contracts import Strategy
from .market_data import PriceBasis, Timeframe
from .replay import require_utc
from .source_quality import ResolvedBarSnapshotV12


class B5FeatureState(str, Enum):
    INPUT_BLOCKED = "INPUT_BLOCKED"
    DATA_UNVERIFIED = "DATA_UNVERIFIED"
    PRECONDITION_NOT_MET = "PRECONDITION_NOT_MET"
    EXTRACTED_UNCALIBRATED = "EXTRACTED_UNCALIBRATED"


@dataclass(frozen=True)
class PriorPivot:
    """A prior source event; owner must externally validate event provenance."""
    instrument_id: str
    event_id: str
    event_time_utc: datetime
    first_known_time_utc: datetime
    price: Decimal
    source_revision: str
    source_verified: bool

    def __post_init__(self):
        for name in ("instrument_id", "event_id", "source_revision"):
            s = getattr(self, name)
            if not isinstance(s, str) or not s.strip():
                raise ValueError(name + " is required")
        require_utc(self.event_time_utc)
        require_utc(self.first_known_time_utc)
        if self.first_known_time_utc < self.event_time_utc:
            raise ValueError("Pivot cannot be known before event time")
        if not isinstance(self.price, Decimal) or not self.price.is_finite() or self.price <= 0:
            raise ValueError("Pivot must be positive finite Decimal")
        if type(self.source_verified) is not bool:
            raise TypeError("Source verification claim must be explicit bool")


@dataclass(frozen=True)
class B5Features:
    breakout_above_pivot: Decimal
    retest_close_to_pivot: Decimal
    retest_low_to_pivot: Decimal
    retest_intrabar_change: Decimal
    prior_pivot_event_id: str
    breakout_revision: str
    retest_revision: str


@dataclass(frozen=True)
class B5FeatureAssessment:
    zone_id: str
    strategy: Strategy
    as_of_utc: datetime
    state: B5FeatureState
    reason: str
    features: B5Features | None
    detector_approved: bool = False
    actionable: bool = False

    def __post_init__(self):
        require_utc(self.as_of_utc)
        if self.zone_id != "B5" or not isinstance(self.strategy, Strategy):
            raise ValueError("Only B5 with a supported strategy")
        if not isinstance(self.state, B5FeatureState) or not self.reason:
            raise ValueError("Explicit reason and state required")
        if (self.features is None) == (self.state is B5FeatureState.EXTRACTED_UNCALIBRATED):
            raise ValueError("Features only belong to extracted state")
        if self.detector_approved or self.actionable:
            raise ValueError("No detector approval or action path in this module")


def extract_b5_features(
    pivot: PriorPivot | None,
    breakout: ResolvedBarSnapshotV12 | None,
    retest: ResolvedBarSnapshotV12 | None,
    *,
    strategy: Strategy,
    as_of_utc: datetime,
) -> B5FeatureAssessment:
    """Shared domain extractor callable by future Signal AND Backtest engines.

    Does not infer source permission from booleans. All source verification
    claims used here are synthetic in current tests; no approved SSI adapter.
    """
    require_utc(as_of_utc)
    if not isinstance(strategy, Strategy):
        raise TypeError("Strategy must be SHORT or SWING")
    if pivot is not None and not isinstance(pivot, PriorPivot):
        raise TypeError("Expected PriorPivot")
    for bar in (breakout, retest):
        if bar is not None and not isinstance(bar, ResolvedBarSnapshotV12):
            raise TypeError("Expected ResolvedBarSnapshotV12")

    def finish(state, reason, features=None):
        return B5FeatureAssessment("B5", strategy, as_of_utc, state, reason, features)

    if pivot is None or breakout is None or retest is None:
        return finish(B5FeatureState.INPUT_BLOCKED, "MISSING_REQUIRED_R0_RC_RE_EVIDENCE")
    a, b = breakout.selected, retest.selected
    if a is None or b is None:
        return finish(B5FeatureState.DATA_UNVERIFIED, "NO_SINGLE_VISIBLE_REVISION")
    key_a, key_b = a.market_bar_key, b.market_bar_key
    if (pivot.instrument_id != key_a.instrument_id
            or key_a.instrument_id != key_b.instrument_id):
        return finish(B5FeatureState.INPUT_BLOCKED, "MIXED_INSTRUMENT_IDENTITY")
    if key_a.timeframe not in (Timeframe.D1, Timeframe.H1) or key_b.timeframe is not Timeframe.M15:
        return finish(B5FeatureState.INPUT_BLOCKED, "B5_R0_D1_H1_AND_RE_M15_REQUIRED")
    if (key_a.price_basis is PriceBasis.UNKNOWN
            or key_a.price_basis != key_b.price_basis
            or key_a.calendar_version != key_b.calendar_version):
        return finish(B5FeatureState.INPUT_BLOCKED, "BASIS_OR_CALENDAR_VERSION_MISMATCH")
    if (pivot.event_time_utc > a.bar_end_utc
            or a.bar_end_utc > key_b.bar_start_utc):
        return finish(B5FeatureState.INPUT_BLOCKED, "EVENT_ORDER_INVALID")
    if (pivot.first_known_time_utc > as_of_utc
            or pivot.first_known_time_utc > a.bar_end_utc
            or a.observation_revision.first_known_time_utc > key_b.bar_start_utc):
        return finish(B5FeatureState.DATA_UNVERIFIED, "LATE_PIVOT_OR_BREAKOUT_KNOWLEDGE")
    if (not pivot.source_verified
            or not breakout.confirmation_prerequisites(as_of_utc)
            or not retest.confirmation_prerequisites(as_of_utc)):
        return finish(B5FeatureState.DATA_UNVERIFIED, "SOURCE_OR_ASOF_NOT_VERIFIED")
    if a.close <= pivot.price:
        return finish(B5FeatureState.PRECONDITION_NOT_MET, "NO_PRIOR_CLOSE_ABOVE_PIVOT")
    features = B5Features(
        breakout_above_pivot=a.close - pivot.price,
        retest_close_to_pivot=b.close - pivot.price,
        retest_low_to_pivot=b.low - pivot.price,
        retest_intrabar_change=b.close - b.open,
        prior_pivot_event_id=pivot.event_id,
        breakout_revision=a.observation_revision.source_revision_or_payload_digest,
        retest_revision=b.observation_revision.source_revision_or_payload_digest,
    )
    return finish(B5FeatureState.EXTRACTED_UNCALIBRATED,
                  "SPEC_PENDING_B5_RC_RE_RF_P01_P17", features)
