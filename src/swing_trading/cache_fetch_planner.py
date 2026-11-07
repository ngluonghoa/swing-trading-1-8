"""Pure, read-only five-minute refresh planning for Swing Trading 1.8.

NO HTTP/MCP access, vendor entitlement, background scheduling, storage approval,
market calendar certification, or actionable trading authorization is provided.
A plan is a proposed request, not evidence the provider supports a delta API.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("UTC-aware datetime required")
    return value.astimezone(timezone.utc)


class SourceCapability(str, Enum):
    WINDOWED = "WINDOWED"        # Only after adapter-specific capability confirmation.
    FULL_SESSION = "FULL_SESSION" # Request whole day, then compare locally.
    UNKNOWN = "UNKNOWN"          # No invented delta support.


class RefreshAction(str, Enum):
    REUSE_CLOSED = "REUSE_CLOSED"
    REQUEST_WINDOW = "REQUEST_WINDOW"
    REQUEST_FULL_SESSION = "REQUEST_FULL_SESSION"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class SourceCursor:
    """Locally observed synthetic/checkpoint metadata, NOT a trusted source head."""
    last_closed_start_utc: datetime
    last_checked_utc: datetime
    last_full_reconciled_utc: datetime | None

    def __post_init__(self) -> None:
        _utc(self.last_closed_start_utc)
        _utc(self.last_checked_utc)
        if self.last_full_reconciled_utc is not None:
            _utc(self.last_full_reconciled_utc)
        if self.last_checked_utc < self.last_closed_start_utc:
            raise ValueError("Check time predates candle")
        if self.last_full_reconciled_utc is not None and self.last_full_reconciled_utc > self.last_checked_utc:
            raise ValueError("Reconcile time cannot exceed checked time")


@dataclass(frozen=True)
class RefreshPlan:
    action: RefreshAction
    start_utc: datetime | None
    end_utc: datetime | None
    reason: str
    expected_closed_utc: datetime | None
    requires_source_revalidation: bool
    certified_source_freshness: bool = False
    data_authorized: bool = False

    def __post_init__(self) -> None:
        if (self.action in (RefreshAction.REQUEST_WINDOW, RefreshAction.REQUEST_FULL_SESSION)) != (self.start_utc is not None and self.end_utc is not None):
            raise ValueError("Request action and window must agree")
        if self.start_utc is not None:
            _utc(self.start_utc)
            _utc(self.end_utc)
            if self.start_utc >= self.end_utc:
                raise ValueError("Empty request")
        if self.certified_source_freshness or self.data_authorized:
            raise ValueError("Local planner never certifies a source or trading use")


def plan_refresh(
    *,
    now_utc: datetime,
    session_start_utc: datetime,
    latest_expected_closed_start_utc: datetime,
    bar_duration: timedelta,
    capability: SourceCapability,
    cursor: SourceCursor | None,
    refresh_interval: timedelta = timedelta(minutes=5),
    correction_reconcile_interval: timedelta = timedelta(minutes=30),
    overlap_bars: int = 1,
    provisional_requested: bool = False,
    session_ended_verified: bool = False,
    immutable_source_head_verified: bool = False,
) -> RefreshPlan:
    """Choose a candidate fetch scope; never manufacture a vendor delta cursor.

    `latest_expected_closed_start_utc` is a *caller supplied session-aware* bar
    start, not independently verified by this function.  Periodic full-session
    comparisons catch corrections outside the overlap when source lacks a trusted
    change ledger. A verified final immutable head is not claimed by default.
    """
    now = _utc(now_utc)
    start = _utc(session_start_utc)
    expected = _utc(latest_expected_closed_start_utc)
    if (type(bar_duration) is not timedelta or bar_duration <= timedelta(0)
            or bar_duration > timedelta(days=1)):
        raise ValueError("Positive finite bar duration required")
    if type(capability) is not SourceCapability:
        raise TypeError("Explicit capability required")
    if not isinstance(refresh_interval, timedelta) or refresh_interval <= timedelta(0):
        raise ValueError("Positive refresh interval required")
    if not isinstance(correction_reconcile_interval, timedelta) or correction_reconcile_interval <= timedelta(0):
        raise ValueError("Positive correction interval required")
    if type(overlap_bars) is not int or not 0 <= overlap_bars <= 24:
        raise ValueError("Overlap bars 0..24 required")
    if any(type(v) is not bool for v in (provisional_requested, session_ended_verified, immutable_source_head_verified)):
        raise TypeError("Boolean session/provisional flags required")
    if start > expected or expected + bar_duration > now:
        raise ValueError("Latest closed bar must be in session and actually closed at clock")
    if cursor is not None and not isinstance(cursor, SourceCursor):
        raise TypeError("Typed cursor required")
    if cursor is not None and cursor.last_checked_utc > now:
        raise ValueError("Cannot reuse a future cache validation")
    if capability is SourceCapability.UNKNOWN:
        return RefreshPlan(RefreshAction.BLOCKED, None, None,
                           "PROVIDER_DELTA_AND_FULL_SCOPE_UNVERIFIED", expected, True)
    if cursor is not None and cursor.last_closed_start_utc > expected:
        return RefreshPlan(RefreshAction.BLOCKED, None, None,
                           "SOURCE_OR_SESSION_CLOCK_MOVED_BACKWARDS", expected, True)

    def request(reason: str, *, full: bool = False) -> RefreshPlan:
        if full or capability is SourceCapability.FULL_SESSION or cursor is None:
            return RefreshPlan(RefreshAction.REQUEST_FULL_SESSION, start, now, reason,
                               expected, True)
        wanted = max(start, cursor.last_closed_start_utc + bar_duration * (1 - overlap_bars))
        return RefreshPlan(RefreshAction.REQUEST_WINDOW, wanted, now, reason,
                           expected, True)

    if cursor is None:
        return request("NO_PRIOR_CACHE")
    if (session_ended_verified and immutable_source_head_verified
            and cursor.last_closed_start_utc == expected):
        return RefreshPlan(RefreshAction.REUSE_CLOSED, None, None,
                           "INDEPENDENT_FINALITY_CLAIM_REUSE_NOT_PRODUCTION_CERTIFIED",
                           expected, False)
    if (cursor.last_full_reconciled_utc is None or
            now - cursor.last_full_reconciled_utc >= correction_reconcile_interval):
        return request("CORRECTION_RECONCILIATION_DUE", full=True)
    if cursor.last_closed_start_utc < expected:
        return request("NEW_CLOSED_BAR")
    if provisional_requested:
        return request("OPEN_BAR_PREVIEW_REQUESTED")
    if now - cursor.last_checked_utc >= refresh_interval:
        return request("SOURCE_REVALIDATION_DUE")
    return RefreshPlan(RefreshAction.REUSE_CLOSED, None, None,
                       "NO_NEW_CLOSED_BAR_WITHIN_REFRESH_POLICY", expected, False)
