"""P0.14 synthetic temporal split/purge/embargo audit for B5 SHORT and SWING.

This is NOT a backtest, model fitting, authorized label policy, official
exchange session calendar, holdout freeze or source licence attestation.
The supplied slot inventory and split boundaries remain unapproved drafts.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .b5_phase_contract import B5_VARIANTS
from .contracts import Strategy
from .d1_atr_reconciliation import D1SessionInventory
from .replay import require_utc


class B5Fold(str, Enum):
    TRAIN = "TRAIN"
    VALIDATION = "VALIDATION"
    HOLDOUT = "HOLDOUT"


class SplitAuditState(str, Enum):
    BLOCKED = "BLOCKED"
    STRUCTURALLY_SEPARATED_UNCERTIFIED = "STRUCTURALLY_SEPARATED_UNCERTIFIED"


@dataclass(frozen=True)
class SessionFold:
    fold: B5Fold
    start_index: int
    stop_index: int  # exclusive

    def __post_init__(self) -> None:
        if not isinstance(self.fold, B5Fold):
            raise TypeError("Fold must be typed")
        if (type(self.start_index) is not int or type(self.stop_index) is not int
                or self.start_index < 0 or self.stop_index <= self.start_index):
            raise ValueError("Positive half-open session interval required")


@dataclass(frozen=True)
class B5SplitCandidate:
    """Strategy + variant specific, no numeric trading threshold or release."""
    strategy: Strategy
    variant_id: str
    calendar: D1SessionInventory
    train: SessionFold
    validation: SessionFold
    holdout: SessionFold
    embargo_sessions: int
    max_observed_label_span_sessions: int
    source_snapshot_id: str
    label_policy_version: str
    split_version: str = "B5/TEMPORAL_SPLIT_CANDIDATE_0_1"
    calendar_certified: bool = False
    source_licensed: bool = False
    holdout_frozen: bool = False
    approved: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.strategy, Strategy):
            raise TypeError("SHORT/SWING Strategy required")
        if self.variant_id not in B5_VARIANTS:
            raise ValueError("Explicit B5 E variant required")
        if not isinstance(self.calendar, D1SessionInventory):
            raise TypeError("Explicit immutable D1 session manifest required")
        if (self.train.fold is not B5Fold.TRAIN
                or self.validation.fold is not B5Fold.VALIDATION
                or self.holdout.fold is not B5Fold.HOLDOUT):
            raise ValueError("Chronological TRAIN/VALIDATION/HOLDOUT fold identity required")
        if (type(self.embargo_sessions) is not int or self.embargo_sessions < 0
                or type(self.max_observed_label_span_sessions) is not int
                or self.max_observed_label_span_sessions <= 0):
            raise ValueError("Explicit nonnegative embargo and positive label cap required")
        if (not isinstance(self.source_snapshot_id, str) or not self.source_snapshot_id.strip()
                or not isinstance(self.label_policy_version, str)
                or not self.label_policy_version.strip()):
            raise ValueError("Source snapshot and label policy IDs are mandatory")
        if self.split_version != "B5/TEMPORAL_SPLIT_CANDIDATE_0_1":
            raise ValueError("Unknown split proposal version")
        if any((self.calendar_certified, self.source_licensed,
                self.holdout_frozen, self.approved)):
            raise ValueError("P0.14 draft never certifies or freezes external source/holdout")


@dataclass(frozen=True)
class B5LabelFootprint:
    """Only event visibility and label horizon, NEVER a return or metric."""
    event_id: str
    strategy: Strategy
    variant_id: str
    decision_session_id: str
    label_end_session_id: str
    first_known_time_utc: datetime
    label_first_known_utc: datetime
    source_revision: str
    label_policy_version: str

    def __post_init__(self) -> None:
        for field in ("event_id", "decision_session_id", "label_end_session_id",
                      "source_revision", "label_policy_version"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(field + " required")
        if not isinstance(self.strategy, Strategy) or self.variant_id not in B5_VARIANTS:
            raise ValueError("Explicit strategy and variant required")
        require_utc(self.first_known_time_utc)
        require_utc(self.label_first_known_utc)


@dataclass(frozen=True)
class B5SplitReview:
    strategy: Strategy
    variant_id: str
    state: SplitAuditState
    reason: str
    train_count: int
    validation_count: int
    holdout_count: int
    violations: tuple[tuple[str, str], ...]
    trading_calendar_certified: bool = False
    source_licence_verified: bool = False
    holdout_unsealed: bool = False
    threshold_approved: bool = False
    historical_backtest_run: bool = False
    actionable: bool = False

    def __post_init__(self) -> None:
        if (not isinstance(self.strategy, Strategy)
                or self.variant_id not in B5_VARIANTS
                or not isinstance(self.state, SplitAuditState) or not self.reason):
            raise ValueError("Explicit review identity/state/reason required")
        if any(type(x) is not int or x < 0 for x in
               (self.train_count, self.validation_count, self.holdout_count)):
            raise ValueError("Counts must be nonnegative")
        if not isinstance(self.violations, tuple):
            raise TypeError("Violations must be immutable")
        if any((self.trading_calendar_certified, self.source_licence_verified,
                self.holdout_unsealed, self.threshold_approved,
                self.historical_backtest_run, self.actionable)):
            raise ValueError("Structural split audit does not approve backtests/trading")


def audit_b5_temporal_split(
    plan: B5SplitCandidate,
    events: tuple[B5LabelFootprint, ...],
    *,
    as_of_utc: datetime,
) -> B5SplitReview:
    """Reject any label overlap into the next scoring fold.

    Purge based on each observed label-end session; embargo is a *caller
    supplied* mandatory gap between scoring-fold ranges. Neither value
    is an approved strategy parameter or proof of label policy fitness.
    """
    require_utc(as_of_utc)
    if not isinstance(plan, B5SplitCandidate):
        raise TypeError("Typed split plan required")
    if not isinstance(events, tuple) or any(not isinstance(x, B5LabelFootprint) for x in events):
        raise TypeError("Immutable event footprint tuple required")

    counts = {fold: 0 for fold in B5Fold}
    def result(state, reason, violations=()):
        return B5SplitReview(plan.strategy, plan.variant_id, state, reason,
                             counts[B5Fold.TRAIN], counts[B5Fold.VALIDATION],
                             counts[B5Fold.HOLDOUT], tuple(violations))

    slots = plan.calendar.slots
    if plan.calendar.first_known_time_utc > as_of_utc:
        return result(SplitAuditState.BLOCKED, "CALENDAR_MANIFEST_NOT_KNOWN_AT_AUDIT_ASOF")
    if (plan.train.stop_index > plan.validation.start_index
            or plan.validation.stop_index > plan.holdout.start_index
            or plan.holdout.stop_index > len(slots)):
        return result(SplitAuditState.BLOCKED, "FOLD_OVERLAP_OR_OUTSIDE_MANIFEST")
    if (plan.validation.start_index - plan.train.stop_index < plan.embargo_sessions
            or plan.holdout.start_index - plan.validation.stop_index < plan.embargo_sessions):
        return result(SplitAuditState.BLOCKED, "REQUIRED_EMBARGO_GAP_NOT_PROVIDED")

    index = {slot.session_period_id: i for i, slot in enumerate(slots)}
    folds = (plan.train, plan.validation, plan.holdout)
    seen_ids = set()
    prev_decision_index = -1
    violations = []
    for event in events:
        if event.event_id in seen_ids:
            violations.append((event.event_id, "DUPLICATE_EVENT_ID"))
            continue
        seen_ids.add(event.event_id)
        if (event.strategy is not plan.strategy
                or event.variant_id != plan.variant_id):
            violations.append((event.event_id, "OTHER_STRATEGY_OR_VARIANT_EVENT"))
            continue
        if event.label_policy_version != plan.label_policy_version:
            violations.append((event.event_id, "LABEL_POLICY_VERSION_MISMATCH"))
            continue
        decision = index.get(event.decision_session_id)
        label_end = index.get(event.label_end_session_id)
        if decision is None or label_end is None:
            violations.append((event.event_id, "EVENT_SESSION_MISSING_FROM_MANIFEST"))
            continue
        if decision < prev_decision_index:
            violations.append((event.event_id, "EVENTS_NOT_CHRONOLOGICALLY_SORTED"))
        prev_decision_index = decision
        selected = next((fold for fold in folds
                         if fold.start_index <= decision < fold.stop_index), None)
        if selected is None:
            violations.append((event.event_id, "EVENT_IN_EMBARGO_OR_OUTSIDE_SCORING_FOLD"))
            continue
        counts[selected.fold] += 1
        if label_end <= decision:
            violations.append((event.event_id, "LABEL_MUST_EXTEND_AFTER_DECISION"))
            continue
        if label_end - decision > plan.max_observed_label_span_sessions:
            violations.append((event.event_id, "LABEL_SPAN_EXCEEDS_DECLARED_CAP"))
        if event.first_known_time_utc > slots[decision].end_utc:
            violations.append((event.event_id, "FEATURE_REVISION_NOT_KNOWN_AT_DECISION"))
        if event.label_first_known_utc < slots[label_end].end_utc:
            violations.append((event.event_id, "LABEL_KNOWN_BEFORE_ITS_HORIZON_CLOSED"))
        if (event.label_first_known_utc > as_of_utc
                or event.first_known_time_utc > as_of_utc):
            violations.append((event.event_id, "EVENT_OR_LABEL_NOT_KNOWN_AT_AUDIT_ASOF"))
        if selected.fold is B5Fold.TRAIN and label_end >= plan.validation.start_index:
            violations.append((event.event_id, "TRAIN_LABEL_LEAKS_INTO_VALIDATION"))
        elif selected.fold is B5Fold.VALIDATION and label_end >= plan.holdout.start_index:
            violations.append((event.event_id, "VALIDATION_LABEL_LEAKS_INTO_HOLDOUT"))
        elif selected.fold is B5Fold.HOLDOUT and label_end >= plan.holdout.stop_index:
            violations.append((event.event_id, "HOLDOUT_LABEL_AFTER_WINDOW"))
    if violations:
        return result(SplitAuditState.BLOCKED, "EVENT_LEAKAGE_OR_SOURCE_QUALIFICATION_FAILED",
                      violations)
    if not events or any(counts[fold] == 0 for fold in B5Fold):
        return result(SplitAuditState.BLOCKED, "REQUIRE_OBSERVED_EVENTS_IN_EACH_FOLD")
    return result(SplitAuditState.STRUCTURALLY_SEPARATED_UNCERTIFIED,
                  "NO_OBSERVED_LABEL_OVERLAP_IN_UNCERTIFIED_CANDIDATE_SPLIT")
