"""P0.13 explicit unapproved B5 SHORT/SWING candidate-grid registration.

This is a calibration *protocol* with empty parameter values, not a
threshold sweep or runnable trading strategy. All six B5 formula slots
are independent per strategy AND variant. No fake performance/approval.
"""
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from .b5_formula_geometry import draft_for
from .b5_phase_contract import B5_VARIANTS
from .contracts import Strategy


class B5CalibrationAxis(str, Enum):
    RC_WINDOW_SESSIONS = "RC_WINDOW_SESSIONS"
    RC_TOLERANCE_ATR = "RC_TOLERANCE_ATR"
    RE_RECLAIM_BUFFER_ATR = "RE_RECLAIM_BUFFER_ATR"
    RF_SUPPORT_BUFFER_ATR = "RF_SUPPORT_BUFFER_ATR"
    RF_MICRO_BREAK_BUFFER_ATR = "RF_MICRO_BREAK_BUFFER_ATR"
    RF_MIN_RVOL = "RF_MIN_RVOL"


class CalibrationDraftState(str, Enum):
    PRE_REGISTERED_UNCALIBRATED = "PRE_REGISTERED_UNCALIBRATED"


def _unit(axis: B5CalibrationAxis) -> str:
    if axis is B5CalibrationAxis.RC_WINDOW_SESSIONS:
        return "EXCHANGE_TRADING_SESSIONS"
    if axis is B5CalibrationAxis.RF_MIN_RVOL:
        return "RVOL_TOD_OR_APPROVED_RVOL_RATIO"
    return "ATR14_D1_MULTIPLE"


@dataclass(frozen=True)
class B5CalibrationSlot:
    strategy: Strategy
    variant_id: str
    axis: B5CalibrationAxis
    unit: str
    candidate_values: tuple[Decimal, ...] | None = None
    calibrated_value: Decimal | None = None
    parameter_approved: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.strategy, Strategy):
            raise TypeError("Explicit strategy required")
        if self.variant_id not in B5_VARIANTS:
            raise ValueError("Explicit B5 E variant required")
        if not isinstance(self.axis, B5CalibrationAxis):
            raise TypeError("Typed B5 axis required")
        if self.unit != _unit(self.axis):
            raise ValueError("B5 axis has incompatible units")
        if (self.candidate_values is not None or self.calibrated_value is not None
                or self.parameter_approved):
            raise ValueError("P0.13 freezes unapproved numeric grid to None")


@dataclass(frozen=True)
class B5ValidationProtocol:
    """Review gate contract, not a runnable walk-forward implementation."""
    strategy: Strategy
    variant_id: str
    formula_version: str
    metric_ids: tuple[str, ...]
    holdout_selection_frozen: bool = False
    split_calendar_qualified: bool = False
    input_source_licensed: bool = False
    source_history_complete: bool = False
    first_known_replay_verified: bool = False
    fill_cost_settlement_simulator_approved: bool = False
    risk_policy_approved: bool = False
    oos_executed: bool = False
    validation_approved: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.strategy, Strategy):
            raise TypeError("Explicit strategy required")
        if self.variant_id not in B5_VARIANTS:
            raise ValueError("Explicit E variant required")
        if self.formula_version != draft_for(self.strategy).rule_version:
            raise ValueError("Must cite canonical uncalibrated formula draft")
        expected = (
            "SIGNAL_FREQUENCY_PER_SESSION", "FALSE_ALERT_RATE",
            "PRECISION_RECALL_WITH_LABEL_POLICY", "NET_EXPECTANCY_AFTER_COSTS",
            "MAX_DRAWDOWN", "HOLDOUT_STABILITY", "SENSITIVITY_AND_COVERAGE",
        )
        if self.metric_ids != expected:
            raise ValueError("Pre-registered evaluation metric IDs are mandatory")
        for field in (
            "holdout_selection_frozen", "split_calendar_qualified",
            "input_source_licensed", "source_history_complete",
            "first_known_replay_verified", "fill_cost_settlement_simulator_approved",
            "risk_policy_approved", "oos_executed", "validation_approved",
        ):
            if getattr(self, field) is not False:
                raise ValueError("No P0.13 evidence permits declaring review gates passed")


@dataclass(frozen=True)
class B5CalibrationGridDraft:
    grid_version: str
    slots: tuple[B5CalibrationSlot, ...]
    protocols: tuple[B5ValidationProtocol, ...]
    state: CalibrationDraftState = CalibrationDraftState.PRE_REGISTERED_UNCALIBRATED
    approved: bool = False
    executable: bool = False
    actionable: bool = False

    def __post_init__(self) -> None:
        if self.grid_version != "B5/SHORT_SWING/CALIBRATION_GRID_DRAFT_0_1":
            raise ValueError("Unknown B5 calibration grid version")
        if (not isinstance(self.slots, tuple)
                or not isinstance(self.protocols, tuple)):
            raise TypeError("Immutable draft inventories required")
        variants = tuple(sorted(B5_VARIANTS))
        keys = {
            (strategy, variant, axis)
            for strategy in Strategy
            for variant in variants
            for axis in B5CalibrationAxis
        }
        observed_keys = [
            (slot.strategy, slot.variant_id, slot.axis) for slot in self.slots
            if isinstance(slot, B5CalibrationSlot)
        ]
        if len(observed_keys) != len(self.slots) or set(observed_keys) != keys or len(observed_keys) != len(keys):
            raise ValueError("Require complete distinct SHORT/SWING x E variant x six axes")
        protocol_keys = [
            (p.strategy, p.variant_id) for p in self.protocols
            if isinstance(p, B5ValidationProtocol)
        ]
        expected_protocol_keys = {
            (strategy, variant) for strategy in Strategy for variant in variants
        }
        if (len(protocol_keys) != len(self.protocols)
                or len(protocol_keys) != len(expected_protocol_keys)
                or set(protocol_keys) != expected_protocol_keys):
            raise ValueError("One separate validation protocol per strategy and variant")
        if (self.state is not CalibrationDraftState.PRE_REGISTERED_UNCALIBRATED
                or self.approved or self.executable or self.actionable):
            raise ValueError("P0.13 is an unapproved, nonexecuting candidate registry")


def build_b5_calibration_grid() -> B5CalibrationGridDraft:
    """Register dimensions and gates, not numeric search values."""
    variants = tuple(sorted(B5_VARIANTS))
    metric_ids = (
        "SIGNAL_FREQUENCY_PER_SESSION", "FALSE_ALERT_RATE",
        "PRECISION_RECALL_WITH_LABEL_POLICY", "NET_EXPECTANCY_AFTER_COSTS",
        "MAX_DRAWDOWN", "HOLDOUT_STABILITY", "SENSITIVITY_AND_COVERAGE",
    )
    slots = tuple(
        B5CalibrationSlot(strategy, variant, axis, _unit(axis))
        for strategy in Strategy
        for variant in variants
        for axis in B5CalibrationAxis
    )
    protocols = tuple(
        B5ValidationProtocol(
            strategy, variant, draft_for(strategy).rule_version, metric_ids,
        )
        for strategy in Strategy for variant in variants
    )
    return B5CalibrationGridDraft(
        "B5/SHORT_SWING/CALIBRATION_GRID_DRAFT_0_1", slots, protocols,
    )
