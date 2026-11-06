"""P0.8 B5 causal *geometry* only — no predicates, calibration or trade authority.

SHORT and SWING share raw arithmetic, but have independent parameter slots.
No threshold is assigned, no Boolean phase is evaluated and no backtest runs.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from .b5_feature_pack import PriorPivot
from .b5_phase_contract import (
    B5Ingredient, B5PhaseReadiness, B5_VARIANTS, inspect_b5_phase_receipts,
    B5PhaseReceipt,
)
from .contracts import Strategy
from .market_data import Timeframe
from .replay import require_utc
from .source_quality import ResolvedBarSnapshotV12


class B5GeometryState(str, Enum):
    BASE_BLOCKED = "BASE_BLOCKED"
    ANCHOR_BLOCKED = "ANCHOR_BLOCKED"
    RAW_GEOMETRY_UNCALIBRATED = "RAW_GEOMETRY_UNCALIBRATED"


@dataclass(frozen=True)
class B5StrategyFormulaDraft:
    """Distinct strategy-slot registry; every unapproved threshold stays None."""
    strategy: Strategy
    rule_version: str
    rc_window_sessions: int | None = None
    rc_tolerance_atr: Decimal | None = None
    re_reclaim_buffer_atr: Decimal | None = None
    rf_support_buffer_atr: Decimal | None = None
    rf_micro_break_buffer_atr: Decimal | None = None
    rf_min_rvol: Decimal | None = None
    risk_policy_approved: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.strategy, Strategy):
            raise TypeError("Strategy must be explicit SHORT or SWING")
        expected = "B5/" + self.strategy.value + "/FORMULA_DRAFT_0_1"
        if self.rule_version != expected:
            raise ValueError("Only named uncalibrated B5 strategy drafts exist")
        for field in ("rc_window_sessions", "rc_tolerance_atr",
                      "re_reclaim_buffer_atr", "rf_support_buffer_atr",
                      "rf_micro_break_buffer_atr", "rf_min_rvol"):
            if getattr(self, field) is not None:
                raise ValueError("No approved numeric parameter is available")
        if type(self.risk_policy_approved) is not bool or self.risk_policy_approved:
            raise ValueError("B5 risk policy not approved")


def draft_for(strategy: Strategy) -> B5StrategyFormulaDraft:
    if not isinstance(strategy, Strategy):
        raise TypeError("Strategy must be explicit SHORT or SWING")
    return B5StrategyFormulaDraft(strategy, "B5/" + strategy.value + "/FORMULA_DRAFT_0_1")


@dataclass(frozen=True)
class B5RawGeometry:
    """Signed distances, not true/false phase verdicts.

    Caller-supplied ATR is merely the P0.7 receipt's proposed number, NOT
    recomputed or validated Wilder ATR14. Session counts and historical RVOL
    are purposely absent until the underlying market source is qualified.
    """
    breakout_close_above_pivot_atr: Decimal
    retest_low_minus_pivot_atr: Decimal
    retest_close_minus_pivot_atr: Decimal
    retest_recovery_from_low_atr: Decimal
    followup_support_close_minus_pivot_atr: Decimal
    followup_close_minus_micro_high_atr: Decimal
    followup_volume_observed: int
    retest_elapsed_seconds_from_breakout: Decimal
    failed_break_close_minus_pivot_atr: Decimal | None
    pivot_event_id: str
    micro_high_source_revision: str


@dataclass(frozen=True)
class B5GeometryAssessment:
    strategy: Strategy
    variant_id: str
    as_of_utc: datetime
    state: B5GeometryState
    reason: str
    formula_version: str
    geometry: B5RawGeometry | None
    detector_approved: bool = False
    actionable: bool = False

    def __post_init__(self) -> None:
        require_utc(self.as_of_utc)
        if not isinstance(self.strategy, Strategy) or self.variant_id not in B5_VARIANTS:
            raise ValueError("Explicit strategy and B5 variant required")
        if not isinstance(self.state, B5GeometryState) or not self.reason:
            raise ValueError("Typed state and reason required")
        if (self.geometry is None) == (self.state is B5GeometryState.RAW_GEOMETRY_UNCALIBRATED):
            raise ValueError("Geometry allowed only in uncalibrated state")
        if self.formula_version != draft_for(self.strategy).rule_version:
            raise ValueError("Unknown B5 formula draft version")
        if self.detector_approved or self.actionable:
            raise ValueError("No trading signal/action authority")


def _causal_anchor(
    anchor: ResolvedBarSnapshotV12 | None,
    reference: ResolvedBarSnapshotV12,
    *,
    as_of_utc: datetime,
    must_be_known_by_utc: datetime,
) -> bool:
    if not isinstance(anchor, ResolvedBarSnapshotV12) or anchor.selected is None:
        return False
    bar = anchor.selected
    ref = reference.selected
    if ref is None or not anchor.confirmation_prerequisites(as_of_utc):
        return False
    key, base = bar.market_bar_key, ref.market_bar_key
    if (key.timeframe is not Timeframe.M15
            or key.instrument_id != base.instrument_id
            or key.exchange != base.exchange
            or key.instrument_class != base.instrument_class
            or key.price_basis != base.price_basis
            or key.calendar_version != base.calendar_version):
        return False
    return (bar.bar_end_utc <= must_be_known_by_utc
            and bar.verified_at_utc is not None
            and bar.verified_at_utc <= must_be_known_by_utc
            and bar.observation_revision.first_known_time_utc <= must_be_known_by_utc)


def calculate_b5_raw_geometry(
    pivot: PriorPivot | None,
    breakout: ResolvedBarSnapshotV12 | None,
    retest: ResolvedBarSnapshotV12 | None,
    receipts: tuple[B5PhaseReceipt, ...],
    *,
    strategy: Strategy,
    variant_id: str,
    as_of_utc: datetime,
    micro_high_anchor: ResolvedBarSnapshotV12 | None,
    failed_break_anchor: ResolvedBarSnapshotV12 | None = None,
) -> B5GeometryAssessment:
    """Read validated receipt manifest and produce only descriptive Decimal math."""
    require_utc(as_of_utc)
    draft = draft_for(strategy)
    if variant_id not in B5_VARIANTS:
        raise ValueError("Explicit canonical B5 E variant required")

    def finish(state: B5GeometryState, reason: str,
               raw: B5RawGeometry | None = None) -> B5GeometryAssessment:
        return B5GeometryAssessment(strategy, variant_id, as_of_utc, state,
                                    reason, draft.rule_version, raw)

    review = inspect_b5_phase_receipts(
        pivot, breakout, retest, receipts,
        strategy=strategy, variant_id=variant_id, as_of_utc=as_of_utc,
    )
    if review.state is not B5PhaseReadiness.PRESENT_UNCALIBRATED:
        return finish(B5GeometryState.BASE_BLOCKED, "PHASE_RECEIPT_" + review.reason)
    assert pivot is not None and breakout is not None and retest is not None
    assert breakout.selected is not None and retest.selected is not None
    a, b = breakout.selected, retest.selected
    records = {r.ingredient: r for r in receipts}
    atr = records[B5Ingredient.RC_PRIOR_ATR].observed_value
    if atr is None or atr <= 0:
        return finish(B5GeometryState.BASE_BLOCKED, "ATR_RECEIPT_NOT_POSITIVE")
    support = records[B5Ingredient.RF_SUPPORT_H1_D1].bar
    follow = records[B5Ingredient.RF_MICRO_HIGH_BREAK].bar
    volume = records[B5Ingredient.RF_VOLUME].bar
    assert support is not None and follow is not None and volume is not None
    assert support.selected is not None and follow.selected is not None
    assert volume.selected is not None

    f = follow.selected
    if (not _causal_anchor(micro_high_anchor, retest, as_of_utc=as_of_utc,
                           must_be_known_by_utc=f.market_bar_key.bar_start_utc)
            or micro_high_anchor.selected.bar_end_utc < b.bar_end_utc):
        return finish(B5GeometryState.ANCHOR_BLOCKED, "NO_CAUSAL_MICRO_HIGH_ANCHOR")

    failed_value = None
    if variant_id == "B5/E_FAILED_BREAK":
        if not _causal_anchor(failed_break_anchor, retest, as_of_utc=as_of_utc,
                              must_be_known_by_utc=b.market_bar_key.bar_start_utc):
            return finish(B5GeometryState.ANCHOR_BLOCKED, "NO_PRIOR_CLOSED_FAILED_BREAK_BAR")
        assert failed_break_anchor is not None and failed_break_anchor.selected is not None
        failed = failed_break_anchor.selected
        if failed.bar_end_utc <= a.bar_end_utc or failed.close >= pivot.price:
            return finish(B5GeometryState.ANCHOR_BLOCKED, "FAILED_BREAK_BAR_NOT_BELOW_PIVOT_AFTER_BREAKOUT")
        failed_value = (failed.close - pivot.price) / atr

    gap = Decimal(str((b.bar_end_utc - a.bar_end_utc).total_seconds()))
    raw = B5RawGeometry(
        breakout_close_above_pivot_atr=(a.close - pivot.price) / atr,
        retest_low_minus_pivot_atr=(b.low - pivot.price) / atr,
        retest_close_minus_pivot_atr=(b.close - pivot.price) / atr,
        retest_recovery_from_low_atr=(b.close - b.low) / atr,
        followup_support_close_minus_pivot_atr=(support.selected.close - pivot.price) / atr,
        followup_close_minus_micro_high_atr=(f.close - micro_high_anchor.selected.high) / atr,
        followup_volume_observed=volume.selected.volume,
        retest_elapsed_seconds_from_breakout=gap,
        failed_break_close_minus_pivot_atr=failed_value,
        pivot_event_id=pivot.event_id,
        micro_high_source_revision=micro_high_anchor.selected.observation_revision.source_revision_or_payload_digest,
    )
    return finish(B5GeometryState.RAW_GEOMETRY_UNCALIBRATED,
                  "R_C_R_E_R_F_THRESHOLDS_AND_SOURCE_VALIDATION_PENDING", raw)
