"""P0.9 causal indicator arithmetic with v1.2 source-lineage guards.

Wilder ATR14 (D1) and RVOL_TF N=20 are *engineering-only numerical features*.
No SSI entitlement, native calendar, historical coverage or trading threshold
is proven by a source flag or a fixture. RVOL_TOD is intentionally not inferred.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from .market_data import Timeframe
from .replay import require_utc
from .source_quality import CoverageState, ResolvedBarSnapshotV12


class IndicatorState(str, Enum):
    BLOCKED = "BLOCKED"
    COMPUTED_UNCALIBRATED = "COMPUTED_UNCALIBRATED"


class VolumeSessionClass(str, Enum):
    DAILY = "DAILY"
    CONTINUOUS = "CONTINUOUS"
    OPENING_AUCTION = "OPENING_AUCTION"
    CLOSING_AUCTION = "CLOSING_AUCTION"
    SHORTENED = "SHORTENED"


@dataclass(frozen=True)
class CausalIndicatorResult:
    indicator_id: str
    as_of_utc: datetime
    state: IndicatorState
    reason: str
    value: Decimal | None
    used_bar_count: int
    rule_version: str
    data_certified: bool = False
    parameter_approved: bool = False
    actionable: bool = False

    def __post_init__(self) -> None:
        require_utc(self.as_of_utc)
        if not self.indicator_id or not self.reason or not self.rule_version:
            raise ValueError("Explicit indicator identity, reason and version required")
        if not isinstance(self.state, IndicatorState):
            raise TypeError("State must be IndicatorState")
        if type(self.used_bar_count) is not int or self.used_bar_count < 0:
            raise ValueError("Used bar count must be nonnegative int")
        if (self.state is IndicatorState.COMPUTED_UNCALIBRATED) != (self.value is not None):
            raise ValueError("Value only allowed for computed uncalibrated features")
        if self.value is not None and (
            not isinstance(self.value, Decimal) or not self.value.is_finite()
            or self.value < 0
        ):
            raise ValueError("Indicator value must be finite nonnegative Decimal")
        if (type(self.data_certified) is not bool
                or type(self.parameter_approved) is not bool
                or type(self.actionable) is not bool
                or self.data_certified or self.parameter_approved or self.actionable):
            raise ValueError("P0.9 results cannot certify data/parameters/trading")


@dataclass(frozen=True)
class VolumeComparisonBar:
    """Explicit classification: it is not inferred from a provider clock."""
    snapshot: ResolvedBarSnapshotV12
    session_class: VolumeSessionClass
    comparison_policy_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot, ResolvedBarSnapshotV12):
            raise TypeError("Expected v1.2 resolved bar")
        if not isinstance(self.session_class, VolumeSessionClass):
            raise TypeError("Explicit session class required")
        if not isinstance(self.comparison_policy_version, str) or not self.comparison_policy_version.strip():
            raise ValueError("Explicit comparison policy version required")


def _source_context(bar):
    key, obs, rev = bar.market_bar_key, bar.observation_key, bar.observation_revision
    return (
        key.instrument_id, key.exchange, key.instrument_class, key.timeframe,
        key.price_basis, key.calendar_version, key.aggregation_policy_version,
        obs.project_id, obs.provider_id, obs.origin, obs.source_stream_id,
        rev.adjustment_revision,
    )


def _qualified(snapshot, as_of_utc, cutoff_utc):
    if not isinstance(snapshot, ResolvedBarSnapshotV12):
        return None
    bar = snapshot.selected
    if (bar is None or not snapshot.confirmation_prerequisites(as_of_utc)
            or bar.coverage_state is not CoverageState.COMPLETE
            or bar.bar_end_utc > cutoff_utc
            or bar.verified_at_utc is None or bar.verified_at_utc > cutoff_utc
            or bar.observation_revision.first_known_time_utc > cutoff_utc):
        return None
    return bar


def _validate_ordered_bars(snapshots, as_of_utc, cutoff_utc, timeframe):
    if not isinstance(snapshots, tuple):
        return None, "INPUT_MUST_BE_IMMUTABLE_TUPLE"
    if any(not isinstance(item, ResolvedBarSnapshotV12) for item in snapshots):
        return None, "INVALID_RESOLVED_BAR_TYPE"
    rows = []
    context = None
    previous_end = None
    seen_keys = set()
    for item in snapshots:
        row = _qualified(item, as_of_utc, cutoff_utc)
        if row is None:
            return None, "BAR_NOT_QUALIFIED_AT_CUTOFF"
        key = row.market_bar_key
        if key.timeframe is not timeframe:
            return None, "TIMEFRAME_MISMATCH"
        now_context = _source_context(row)
        if context is not None and context != now_context:
            return None, "SOURCE_BASIS_OR_POLICY_MISMATCH"
        if key in seen_keys or (previous_end is not None and
                                key.bar_start_utc < previous_end):
            return None, "DUPLICATE_OVERLAPPING_OR_UNSORTED_BARS"
        seen_keys.add(key)
        previous_end = row.bar_end_utc
        context = now_context
        rows.append(row)
    return rows, ""


def calculate_wilder_atr14(
    history: tuple[ResolvedBarSnapshotV12, ...],
    *,
    as_of_utc: datetime,
    known_before_utc: datetime | None = None,
) -> CausalIndicatorResult:
    """Seed mean of 14 true ranges using 15 CLOSED D1 bars; then Wilder smooth.

    A separate source-qualified prehistory/coverage attestation is still OPEN:
    this function cannot prove that missing trading days were not silently
    omitted, even if every *supplied* snapshot is internally consistent.
    """
    require_utc(as_of_utc)
    if known_before_utc is not None:
        require_utc(known_before_utc)
    cutoff = min(as_of_utc, known_before_utc) if known_before_utc else as_of_utc

    def finish(state, reason, value=None, count=0):
        return CausalIndicatorResult("ATR14_D1", as_of_utc, state, reason,
                                     value, count, "WILDER_ATR14_SEED14_TR_V0_1")

    bars, reason = _validate_ordered_bars(history, as_of_utc, cutoff, Timeframe.D1)
    if bars is None:
        return finish(IndicatorState.BLOCKED, reason)
    if len(bars) < 15:
        return finish(IndicatorState.BLOCKED, "REQUIRE_15_D1_BARS_FOR_14_TRUE_RANGES")
    tr = []
    for idx in range(1, len(bars)):
        previous_close = bars[idx - 1].close
        current = bars[idx]
        tr.append(max(
            current.high - current.low,
            abs(current.high - previous_close),
            abs(current.low - previous_close),
        ))
    period = Decimal(14)
    atr = sum(tr[:14], Decimal(0)) / period
    for observation in tr[14:]:
        atr = (Decimal(13) * atr + observation) / period
    if atr <= 0:
        return finish(IndicatorState.BLOCKED, "NONPOSITIVE_ATR14_CANNOT_NORMALIZE")
    return finish(IndicatorState.COMPUTED_UNCALIBRATED,
                  "CLOSED_D1_MATH_ONLY_NO_EXTERNAL_HISTORY_CERTIFICATION",
                  atr, len(bars))


def calculate_rvol_tf20(
    target: VolumeComparisonBar,
    prior: tuple[VolumeComparisonBar, ...],
    *,
    as_of_utc: datetime,
) -> CausalIndicatorResult:
    """N20 RVOL_TF target volume / mean(20 prior SAME-TF comparable bars).

    For session-time normalized RVOL_TOD, do NOT use this function:
    same intraday slot over 20 separate sessions and provider-native
    cumulative volumes demand a different, independently verified contract.
    """
    require_utc(as_of_utc)

    def finish(state, reason, value=None, count=0):
        return CausalIndicatorResult("RVOL_TF20", as_of_utc, state, reason,
                                     value, count, "RVOL_TF_N20_CANDIDATE_V0_1")

    if not isinstance(target, VolumeComparisonBar):
        return finish(IndicatorState.BLOCKED, "INVALID_TARGET")
    if not isinstance(prior, tuple) or any(not isinstance(x, VolumeComparisonBar) for x in prior):
        return finish(IndicatorState.BLOCKED, "INVALID_COMPARATOR_TUPLE")
    if len(prior) != 20:
        return finish(IndicatorState.BLOCKED, "REQUIRE_EXACTLY_20_PRIOR_COMPARABLE_BARS")
    target_bar = _qualified(target.snapshot, as_of_utc, as_of_utc)
    if target_bar is None:
        return finish(IndicatorState.BLOCKED, "TARGET_NOT_QUALIFIED")
    target_key = target_bar.market_bar_key
    if target_key.timeframe is Timeframe.D1:
        if target.session_class is not VolumeSessionClass.DAILY:
            return finish(IndicatorState.BLOCKED, "D1_REQUIRES_DAILY_SESSION_CLASS")
    elif target.session_class is VolumeSessionClass.DAILY:
        return finish(IndicatorState.BLOCKED, "INTRADAY_CANNOT_USE_DAILY_SESSION_CLASS")
    series = tuple(item.snapshot for item in prior)
    bars, reason = _validate_ordered_bars(series, as_of_utc, as_of_utc, target_key.timeframe)
    if bars is None:
        return finish(IndicatorState.BLOCKED, reason)
    target_context = _source_context(target_bar)
    if any(_source_context(row) != target_context for row in bars):
        return finish(IndicatorState.BLOCKED, "TARGET_AND_HISTORY_SOURCE_MISMATCH")
    if any(row.bar_end_utc > target_key.bar_start_utc for row in bars):
        return finish(IndicatorState.BLOCKED, "COMPARATOR_KNOWN_AFTER_TARGET_START")
    if any(row.verified_at_utc > target_key.bar_start_utc or
           row.observation_revision.first_known_time_utc > target_key.bar_start_utc
           for row in bars):
        return finish(IndicatorState.BLOCKED, "COMPARATOR_NOT_KNOWN_BEFORE_TARGET_START")
    if any(item.session_class is not target.session_class or
           item.comparison_policy_version != target.comparison_policy_version
           for item in prior):
        return finish(IndicatorState.BLOCKED, "SESSION_CLASS_OR_COMPARISON_POLICY_MISMATCH")
    if any(row.market_bar_key == target_key for row in bars):
        return finish(IndicatorState.BLOCKED, "TARGET_LEAKED_INTO_HISTORY")
    volume_total = sum(row.volume for row in bars)
    if volume_total <= 0:
        return finish(IndicatorState.BLOCKED, "ZERO_VOLUME_DENOMINATOR")
    value = Decimal(target_bar.volume) * Decimal(20) / Decimal(volume_total)
    return finish(IndicatorState.COMPUTED_UNCALIBRATED,
                  "SAME_TF_RVOL_MATH_ONLY_NO_TOD_OR_ACTION_APPROVAL", value, 21)
