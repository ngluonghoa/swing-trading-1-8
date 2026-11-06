"""P0.10 D1 session-inventory audit and causal ATR14 correction/append replay.

This independently compares indicator implementations against an explicit,
unverified caller-supplied session inventory. No official HOSE/HNX/UPCoM
calendar, SSI entitlement, history coverage or trading use is certified.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from .causal_indicators import (
    IndicatorState, _source_context, _validate_ordered_bars,
    calculate_wilder_atr14,
)
from .market_data import Timeframe
from .replay import require_utc
from .source_quality import ResolvedBarSnapshotV12


class SessionAuditState(str, Enum):
    BLOCKED = "BLOCKED"
    MATCH_UNCERTIFIED = "MATCH_UNCERTIFIED"


@dataclass(frozen=True)
class D1ExpectedSession:
    session_period_id: str
    start_utc: datetime
    end_utc: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.session_period_id, str) or not self.session_period_id.strip():
            raise ValueError("Session ID required")
        require_utc(self.start_utc)
        require_utc(self.end_utc)
        if self.end_utc <= self.start_utc:
            raise ValueError("Expected session must have positive duration")


@dataclass(frozen=True)
class D1SessionInventory:
    """External expected slots, NOT proof that they cover actual market days."""
    source_label: str
    calendar_version: str
    manifest_revision: str
    first_known_time_utc: datetime
    slots: tuple[D1ExpectedSession, ...]
    independently_certified: bool = False

    def __post_init__(self) -> None:
        for name in ("source_label", "calendar_version", "manifest_revision"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(name + " required")
        require_utc(self.first_known_time_utc)
        if not isinstance(self.slots, tuple) or not self.slots:
            raise ValueError("Nonempty immutable session slots required")
        if any(not isinstance(slot, D1ExpectedSession) for slot in self.slots):
            raise TypeError("Every expected slot must be D1ExpectedSession")
        if self.independently_certified is not False:
            raise ValueError("Independent official market calendar certification unavailable")
        seen = set()
        previous_end = None
        for slot in self.slots:
            if slot.session_period_id in seen:
                raise ValueError("Duplicate expected session ID")
            if previous_end is not None and slot.start_utc < previous_end:
                raise ValueError("Unsorted or overlapping expected sessions")
            seen.add(slot.session_period_id)
            previous_end = slot.end_utc


@dataclass(frozen=True)
class D1SessionAudit:
    state: SessionAuditState
    reason: str
    expected_count: int
    actual_count: int
    missing_session_ids: tuple[str, ...] = ()
    unexpected_session_ids: tuple[str, ...] = ()
    calendar_certified: bool = False
    actionable: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.state, SessionAuditState) or not self.reason:
            raise ValueError("Typed session audit state/reason required")
        if type(self.expected_count) is not int or self.expected_count < 0:
            raise ValueError("Invalid expected count")
        if type(self.actual_count) is not int or self.actual_count < 0:
            raise ValueError("Invalid actual count")
        if not isinstance(self.missing_session_ids, tuple) or not isinstance(self.unexpected_session_ids, tuple):
            raise ValueError("Session ID lists must be tuples")
        if self.calendar_certified or self.actionable:
            raise ValueError("Calendar inventory comparison cannot certify market data")


def audit_d1_session_inventory(
    history: tuple[ResolvedBarSnapshotV12, ...],
    inventory: D1SessionInventory,
    *,
    as_of_utc: datetime,
) -> D1SessionAudit:
    """Compare exact D1 session IDs/start/end with an externally supplied list."""
    require_utc(as_of_utc)
    if not isinstance(inventory, D1SessionInventory):
        raise TypeError("D1SessionInventory required")
    expected = inventory.slots

    def finish(reason, *, ok=False, actual=0, missing=(), extra=()):
        return D1SessionAudit(
            SessionAuditState.MATCH_UNCERTIFIED if ok else SessionAuditState.BLOCKED,
            reason, len(expected), actual, tuple(missing), tuple(extra),
        )

    if inventory.first_known_time_utc > as_of_utc:
        return finish("INVENTORY_NOT_KNOWN_AS_OF")
    rows, bad = _validate_ordered_bars(history, as_of_utc, as_of_utc, Timeframe.D1)
    if rows is None:
        return finish("SOURCE_HISTORY_" + bad)
    ids = tuple(row.market_bar_key.session_period_id for row in rows)
    expected_ids = tuple(slot.session_period_id for slot in expected)
    if len(set(ids)) != len(ids):
        return finish("DUPLICATE_ACTUAL_SESSION_ID", actual=len(rows))
    missing = tuple(x for x in expected_ids if x not in ids)
    extra = tuple(x for x in ids if x not in expected_ids)
    if missing or extra:
        return finish("EXPECTED_SESSION_INVENTORY_DIFFERS",
                      actual=len(rows), missing=missing, extra=extra)
    if ids != expected_ids:
        return finish("SESSION_SEQUENCE_MISMATCH", actual=len(rows))
    for row, slot in zip(rows, expected):
        key = row.market_bar_key
        if key.calendar_version != inventory.calendar_version:
            return finish("CALENDAR_VERSION_MISMATCH", actual=len(rows))
        if key.bar_start_utc != slot.start_utc or row.bar_end_utc != slot.end_utc:
            return finish("SESSION_BOUNDARY_MISMATCH", actual=len(rows))
    return finish("EXACT_MATCH_TO_UNCERTIFIED_SESSION_INVENTORY",
                  ok=True, actual=len(rows))


class ATRReplayState(str, Enum):
    BLOCKED = "BLOCKED"
    PARITY_UNCERTIFIED = "PARITY_UNCERTIFIED"
    DIVERGED = "DIVERGED"


@dataclass(frozen=True)
class ATRReplayAudit:
    state: ATRReplayState
    reason: str
    old_atr: Decimal | None
    batch_atr: Decimal | None
    replay_atr: Decimal | None
    first_dirty_index: int | None
    replay_from_index: int | None
    replayed_true_ranges: int
    calendar_certified: bool = False
    source_certified: bool = False
    actionable: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.state, ATRReplayState) or not self.reason:
            raise ValueError("Explicit ATR replay state and reason required")
        if type(self.replayed_true_ranges) is not int or self.replayed_true_ranges < 0:
            raise ValueError("Invalid replay count")
        for index in (self.first_dirty_index, self.replay_from_index):
            if index is not None and (type(index) is not int or index < 0):
                raise ValueError("Invalid replay index")
        for v in (self.old_atr, self.batch_atr, self.replay_atr):
            if v is not None and (not isinstance(v, Decimal) or not v.is_finite()):
                raise ValueError("ATR values must be finite Decimal")
        if self.calendar_certified or self.source_certified or self.actionable:
            raise ValueError("Synthetic ATR replay never approves market data or trading")


def reconcile_atr14_d1(
    old_history: tuple[ResolvedBarSnapshotV12, ...],
    current_history: tuple[ResolvedBarSnapshotV12, ...],
    inventory: D1SessionInventory,
    *,
    old_as_of_utc: datetime,
    as_of_utc: datetime,
) -> ATRReplayAudit:
    """Replay append/correction from first dirty index and demand EXACT batch parity.

    Revision changes in historical closes affect subsequent true ranges, so
    replay starts at the dirty bar (and uses the unchanged prior close);
    edits inside the first 15 bars force a fresh 14-TR seed.
    """
    require_utc(old_as_of_utc)
    require_utc(as_of_utc)

    def finish(state, reason, old=None, batch=None, replay=None, dirty=None,
               start=None, tr_count=0):
        return ATRReplayAudit(state, reason, old, batch, replay,
                              dirty, start, tr_count)

    if old_as_of_utc > as_of_utc:
        return finish(ATRReplayState.BLOCKED, "AS_OF_CLOCK_MOVED_BACKWARDS")
    if not isinstance(inventory, D1SessionInventory):
        raise TypeError("D1SessionInventory required")
    if inventory.first_known_time_utc > old_as_of_utc:
        return finish(ATRReplayState.BLOCKED, "SESSION_INVENTORY_NOT_KNOWN_AT_CHECKPOINT")
    if not isinstance(old_history, tuple) or not isinstance(current_history, tuple):
        return finish(ATRReplayState.BLOCKED, "HISTORY_INPUT_NOT_IMMUTABLE")
    if len(old_history) < 15 or len(current_history) < 15:
        return finish(ATRReplayState.BLOCKED, "REQUIRE_15_D1_BARS_FOR_REPLAY")
    if len(current_history) < len(old_history):
        return finish(ATRReplayState.BLOCKED, "HISTORY_TRUNCATION_REQUIRES_INDEPENDENT_RESEED")
    if len(old_history) > len(inventory.slots):
        return finish(ATRReplayState.BLOCKED, "CHECKPOINT_LONGER_THAN_EXPECTED_INVENTORY")

    prior_inventory = D1SessionInventory(
        inventory.source_label, inventory.calendar_version,
        inventory.manifest_revision, inventory.first_known_time_utc,
        inventory.slots[:len(old_history)],
    )
    earlier = audit_d1_session_inventory(old_history, prior_inventory, as_of_utc=old_as_of_utc)
    if earlier.state is not SessionAuditState.MATCH_UNCERTIFIED:
        return finish(ATRReplayState.BLOCKED, "OLD_HISTORY_" + earlier.reason)
    current = audit_d1_session_inventory(current_history, inventory, as_of_utc=as_of_utc)
    if current.state is not SessionAuditState.MATCH_UNCERTIFIED:
        return finish(ATRReplayState.BLOCKED, "CURRENT_HISTORY_" + current.reason)

    old_rows = tuple(item.selected for item in old_history)
    new_rows = tuple(item.selected for item in current_history)
    # Both audits require a single selected snapshot for every position.
    if _source_context(old_rows[0]) != _source_context(new_rows[0]):
        return finish(ATRReplayState.BLOCKED, "SOURCE_OR_ADJUSTMENT_POLICY_CHANGED_RESEED_REQUIRED")
    if tuple(row.market_bar_key for row in old_rows) != tuple(
        row.market_bar_key for row in new_rows[:len(old_rows)]
    ):
        return finish(ATRReplayState.BLOCKED, "HISTORICAL_SESSION_INSERTION_RESEED_REQUIRED")

    previous = calculate_wilder_atr14(old_history, as_of_utc=old_as_of_utc)
    full = calculate_wilder_atr14(current_history, as_of_utc=as_of_utc)
    if (previous.state is not IndicatorState.COMPUTED_UNCALIBRATED
            or full.state is not IndicatorState.COMPUTED_UNCALIBRATED):
        return finish(ATRReplayState.BLOCKED, "BATCH_ATR_PREREQUISITES_FAILED")

    dirty = next(
        (i for i in range(len(old_rows)) if old_rows[i] != new_rows[i]), None
    )
    if dirty is None and len(new_rows) > len(old_rows):
        dirty = len(old_rows)
    if dirty is None:
        return finish(ATRReplayState.PARITY_UNCERTIFIED,
                      "IDEMPOTENT_NO_CHANGED_SOURCE_REVISION",
                      previous.value, full.value, previous.value, None, None, 0)

    if dirty < len(old_rows) and new_rows[dirty].observation_revision.first_known_time_utc <= old_as_of_utc:
        return finish(ATRReplayState.BLOCKED, "CORRECTION_WAS_ALREADY_KNOWN_AT_CHECKPOINT")

    if dirty < 15:
        # Changed seed period: throw away the checkpoint and rebuild seed
        # from the newly visible 15-bar history.
        seed = calculate_wilder_atr14(current_history[:15], as_of_utc=as_of_utc)
        if seed.state is not IndicatorState.COMPUTED_UNCALIBRATED:
            return finish(ATRReplayState.BLOCKED, "NEW_SEED_ATR_PREREQUISITES_FAILED")
        value = seed.value
        start = 15
        from_index = 0
        tr_count = len(new_rows) - 1
    else:
        # Unchanged prefix is a causally valid old ATR checkpoint.
        checkpoint = calculate_wilder_atr14(old_history[:dirty], as_of_utc=old_as_of_utc)
        if checkpoint.state is not IndicatorState.COMPUTED_UNCALIBRATED:
            return finish(ATRReplayState.BLOCKED, "OLD_CHECKPOINT_ATR_PREREQUISITES_FAILED")
        value = checkpoint.value
        start = dirty
        from_index = dirty
        tr_count = len(new_rows) - dirty

    for index in range(start, len(new_rows)):
        current_bar = new_rows[index]
        prior_close = new_rows[index - 1].close
        tr = max(
            current_bar.high - current_bar.low,
            abs(current_bar.high - prior_close),
            abs(current_bar.low - prior_close),
        )
        value = (Decimal(13) * value + tr) / Decimal(14)

    if value != full.value:
        return finish(ATRReplayState.DIVERGED, "BATCH_AND_INCREMENTAL_ATR_DIFFER",
                      previous.value, full.value, value, dirty, from_index, tr_count)
    return finish(ATRReplayState.PARITY_UNCERTIFIED, "EXACT_BATCH_REPLAY_PARITY_ON_INPUTS",
                  previous.value, full.value, value, dirty, from_index, tr_count)
