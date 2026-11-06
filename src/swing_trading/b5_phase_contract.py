"""GĐ4/P0.7 — B5 phase evidence receipts, NOT executable phase predicates.

The B5 manifest in Master Spec §24.4 requires R0, R_C, R_E and R_F.
This module prepares source-qualified, causal receipts for R_C/R_E/R_F
without making up candidate thresholds, policy approvals, Boolean predicate
results, trade entries/exits, or real historical performance.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from .b5_feature_pack import B5FeatureState, PriorPivot, extract_b5_features
from .contracts import Strategy
from .market_data import PriceBasis, Timeframe
from .replay import require_utc
from .source_quality import ResolvedBarSnapshotV12


class B5Ingredient(str, Enum):
    RC_PIVOT_RETEST = "RC_PIVOT_RETEST"
    RC_PRIOR_ATR = "RC_PRIOR_ATR"
    RC_WINDOW_POLICY = "RC_WINDOW_POLICY"
    RE_M15_TRIGGER = "RE_M15_TRIGGER"
    RF_SUPPORT_H1_D1 = "RF_SUPPORT_H1_D1"
    RF_MICRO_HIGH_BREAK = "RF_MICRO_HIGH_BREAK"
    RF_VOLUME = "RF_VOLUME"
    RF_RISK_POLICY = "RF_RISK_POLICY"


class B5PhaseReadiness(str, Enum):
    BASE_UNVERIFIED = "BASE_UNVERIFIED"
    RECEIPTS_MISSING = "RECEIPTS_MISSING"
    RECEIPTS_UNVERIFIED = "RECEIPTS_UNVERIFIED"
    PRESENT_UNCALIBRATED = "PRESENT_UNCALIBRATED"


B5_REQUIRED_INGREDIENTS = tuple(B5Ingredient)
B5_VARIANTS = frozenset({"B5/E_RECLAIM", "B5/E_FAILED_BREAK"})
B5_PHASE_PREDICATE_REFS = (
    "B5.R0.PRIOR_BREAKOUT_EVENT",
    "B5.RC.EXACT_PIVOT_RETEST",
    "B5.RE.M15_RECLAIM_OR_FAILED_BREAK",
    "B5.RF.RETEST_SUPPORT_BREAK",
)
# Policy/evidence receipts are never proof of approved formulas.
B5_PARAMETER_STATUS = "PARAM_CANDIDATE_NOT_APPROVED"

_POLICY_INGREDIENTS = frozenset({
    B5Ingredient.RC_WINDOW_POLICY, B5Ingredient.RF_RISK_POLICY,
})
_ALLOWED_TIMEFRAMES = {
    B5Ingredient.RC_PIVOT_RETEST: frozenset({Timeframe.M15}),
    B5Ingredient.RC_PRIOR_ATR: frozenset({Timeframe.D1}),
    B5Ingredient.RE_M15_TRIGGER: frozenset({Timeframe.M15}),
    B5Ingredient.RF_SUPPORT_H1_D1: frozenset({Timeframe.H1, Timeframe.D1}),
    B5Ingredient.RF_MICRO_HIGH_BREAK: frozenset({Timeframe.M15, Timeframe.H1}),
    B5Ingredient.RF_VOLUME: frozenset({Timeframe.H1, Timeframe.D1}),
}


def _text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(name + " must be nonempty text")


@dataclass(frozen=True)
class B5PhaseReceipt:
    """A source/policy reference; never a declaration that a phase passed.

    A 'policy' receipt carries a versioned external reference only. The window
    length, ATR multiplier, risk model and all other numeric policy parameters
    remain unspecified until independently approved. The market-bar receipts
    must cite a unique v1.2 resolved closed bar in the same instrument/basis.
    """
    ingredient: B5Ingredient
    anchor_pivot_event_id: str
    evidence_id: str
    instrument_id: str
    exchange: str
    price_basis: PriceBasis
    calendar_version: str
    event_time_utc: datetime
    first_known_time_utc: datetime
    source_revision: str
    method_version: str
    bar: ResolvedBarSnapshotV12 | None = None
    observed_value: Decimal | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.ingredient, B5Ingredient):
            raise TypeError("Explicit B5Ingredient required")
        for name in ("anchor_pivot_event_id", "evidence_id", "instrument_id",
                     "exchange", "calendar_version", "source_revision", "method_version"):
            _text(getattr(self, name), name)
        if not isinstance(self.price_basis, PriceBasis) or self.price_basis is PriceBasis.UNKNOWN:
            raise ValueError("Explicit known price basis required")
        require_utc(self.event_time_utc)
        require_utc(self.first_known_time_utc)
        if self.first_known_time_utc < self.event_time_utc:
            raise ValueError("Receipt cannot precede its event")
        if self.bar is not None and not isinstance(self.bar, ResolvedBarSnapshotV12):
            raise TypeError("bar must be ResolvedBarSnapshotV12 or None")
        if self.observed_value is not None and (
            not isinstance(self.observed_value, Decimal)
            or not self.observed_value.is_finite()
        ):
            raise ValueError("Observed value must be finite Decimal or None")
        if self.ingredient in _POLICY_INGREDIENTS:
            if self.bar is not None or self.observed_value is not None:
                raise ValueError("Policy receipt cannot impersonate a market bar or value")
        elif self.bar is None:
            raise ValueError("Market observation ingredient needs resolved bar")


@dataclass(frozen=True)
class B5PhaseManifestAssessment:
    strategy: Strategy
    variant_id: str
    as_of_utc: datetime
    state: B5PhaseReadiness
    reason: str
    missing: tuple[B5Ingredient, ...]
    observed: tuple[B5Ingredient, ...]
    parameter_status: str = B5_PARAMETER_STATUS
    detector_approved: bool = False
    actionable: bool = False

    def __post_init__(self) -> None:
        require_utc(self.as_of_utc)
        if not isinstance(self.strategy, Strategy) or self.variant_id not in B5_VARIANTS:
            raise ValueError("B5 strategy and explicit E variant are required")
        if not isinstance(self.state, B5PhaseReadiness):
            raise TypeError("Unrecognized B5 manifest state")
        _text(self.reason, "reason")
        if (self.parameter_status != B5_PARAMETER_STATUS
                or self.detector_approved or self.actionable):
            raise ValueError("Phase receipts never approve a detector or trade")
        if not isinstance(self.missing, tuple) or not isinstance(self.observed, tuple):
            raise TypeError("Manifest evidence inventories must be tuples")
        if any(not isinstance(item, B5Ingredient) for item in self.missing + self.observed):
            raise TypeError("Invalid ingredient inventory")


def inspect_b5_phase_receipts(
    pivot: PriorPivot | None,
    breakout: ResolvedBarSnapshotV12 | None,
    retest: ResolvedBarSnapshotV12 | None,
    receipts: tuple[B5PhaseReceipt, ...],
    *,
    strategy: Strategy,
    variant_id: str,
    as_of_utc: datetime,
) -> B5PhaseManifestAssessment:
    """Audit presence and causal lineage only; do not execute B5 predicates.

    A structurally 'present' manifest is still SPEC_PENDING_CALIBRATION and
    may not emit DETECTED/NOT_DETECTED, confidence, entry/SL/TP or a trade.
    """
    require_utc(as_of_utc)
    if not isinstance(strategy, Strategy):
        raise TypeError("Strategy must be SHORT or SWING")
    if variant_id not in B5_VARIANTS:
        raise ValueError("Select an explicit canonical B5/E variant")
    if not isinstance(receipts, tuple) or any(
        not isinstance(r, B5PhaseReceipt) for r in receipts
    ):
        raise TypeError("Immutable B5PhaseReceipt tuple required")

    def finish(state: B5PhaseReadiness, reason: str,
               missing: tuple[B5Ingredient, ...] = (),
               observed: tuple[B5Ingredient, ...] = ()) -> B5PhaseManifestAssessment:
        return B5PhaseManifestAssessment(
            strategy, variant_id, as_of_utc, state, reason, missing, observed,
        )

    base = extract_b5_features(pivot, breakout, retest, strategy=strategy,
                               as_of_utc=as_of_utc)
    if base.state is not B5FeatureState.EXTRACTED_UNCALIBRATED:
        return finish(B5PhaseReadiness.BASE_UNVERIFIED, "B5_R0_OR_RETEST_BASE_" + base.state.value)

    assert pivot is not None and retest is not None and retest.selected is not None
    retest_bar = retest.selected
    ref_key = retest_bar.market_bar_key
    seen: dict[B5Ingredient, B5PhaseReceipt] = {}
    for receipt in receipts:
        if receipt.ingredient in seen:
            return finish(B5PhaseReadiness.RECEIPTS_UNVERIFIED,
                          "DUPLICATE_OR_CONFLICTING_INGREDIENT")
        seen[receipt.ingredient] = receipt

        if (receipt.anchor_pivot_event_id != pivot.event_id
                or receipt.instrument_id != ref_key.instrument_id
                or receipt.exchange != ref_key.exchange
                or receipt.price_basis != ref_key.price_basis
                or receipt.calendar_version != ref_key.calendar_version):
            return finish(B5PhaseReadiness.RECEIPTS_UNVERIFIED,
                          "ANCHOR_INSTRUMENT_BASIS_OR_CALENDAR_MISMATCH")
        if (receipt.event_time_utc > as_of_utc
                or receipt.first_known_time_utc > as_of_utc):
            return finish(B5PhaseReadiness.RECEIPTS_UNVERIFIED, "FUTURE_EVIDENCE")
        if receipt.bar is None:
            # The referenced policy is merely declared, never interpreted
            # as a numeric approval or as a substitute for actual risk checks.
            continue
        resolution = receipt.bar
        selected = resolution.selected
        if selected is None or not resolution.confirmation_prerequisites(as_of_utc):
            return finish(B5PhaseReadiness.RECEIPTS_UNVERIFIED,
                          "BAR_NOT_SOURCE_QUALIFIED_AS_OF")
        key = selected.market_bar_key
        if (key.instrument_id != ref_key.instrument_id
                or key.exchange != ref_key.exchange
                or key.instrument_class != ref_key.instrument_class
                or key.price_basis != ref_key.price_basis
                or key.calendar_version != ref_key.calendar_version
                or key.timeframe not in _ALLOWED_TIMEFRAMES[receipt.ingredient]):
            return finish(B5PhaseReadiness.RECEIPTS_UNVERIFIED,
                          "BAR_IDENTITY_OR_TIMEFRAME_MISMATCH")
        if receipt.evidence_id not in selected.source_event_ids:
            return finish(B5PhaseReadiness.RECEIPTS_UNVERIFIED,
                          "EVIDENCE_EVENT_NOT_IN_SOURCE_BAR")
        if (receipt.source_revision != selected.observation_revision.source_revision_or_payload_digest
                or receipt.event_time_utc != selected.bar_end_utc
                or receipt.first_known_time_utc < selected.verified_at_utc):
            return finish(B5PhaseReadiness.RECEIPTS_UNVERIFIED,
                          "BAR_REVISION_OR_CAUSAL_KNOWLEDGE_MISMATCH")
        if receipt.ingredient in (
            B5Ingredient.RC_PIVOT_RETEST, B5Ingredient.RE_M15_TRIGGER,
        ) and selected != retest_bar:
            return finish(B5PhaseReadiness.RECEIPTS_UNVERIFIED,
                          "RETEST_BAR_NOT_SAME_CAUSAL_EVENT")
        if receipt.ingredient is B5Ingredient.RC_PRIOR_ATR:
            if (selected.bar_end_utc > ref_key.bar_start_utc
                    or selected.verified_at_utc > ref_key.bar_start_utc):
                return finish(B5PhaseReadiness.RECEIPTS_UNVERIFIED,
                              "ATR_NOT_KNOWN_BEFORE_RETEST")
            if receipt.observed_value is None or receipt.observed_value <= 0:
                return finish(B5PhaseReadiness.RECEIPTS_UNVERIFIED,
                              "ATR_VALUE_MISSING_OR_NONPOSITIVE")
        if (receipt.ingredient is B5Ingredient.RF_MICRO_HIGH_BREAK
                and selected.bar_end_utc <= retest_bar.bar_end_utc):
            return finish(B5PhaseReadiness.RECEIPTS_UNVERIFIED,
                          "MICRO_HIGH_NOT_AFTER_RETEST")

    missing = tuple(item for item in B5_REQUIRED_INGREDIENTS if item not in seen)
    observed = tuple(item for item in B5_REQUIRED_INGREDIENTS if item in seen)
    if missing:
        return finish(B5PhaseReadiness.RECEIPTS_MISSING,
                      "REQUIRED_PHASE_EVIDENCE_NOT_SUPPLIED", missing, observed)
    return finish(B5PhaseReadiness.PRESENT_UNCALIBRATED,
                  "R_C_R_E_R_F_FORMULAS_THRESHOLDS_AND_RISK_NOT_APPROVED",
                  (), observed)
