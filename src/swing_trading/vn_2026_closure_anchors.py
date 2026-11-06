"""P0.11 narrow official-notice 2026 NON-trading-date collision anchors.

These selected HOSE/HNX published holiday notices are evidence of specific
closures, NOT a complete, revision-verified trading calendar or actual bars.
Do not infer that any date absent from these anchors is a trading day.
"""
from dataclasses import dataclass
from datetime import date, timedelta, timezone
from enum import Enum

from .d1_atr_reconciliation import D1SessionInventory


_VN = timezone(timedelta(hours=7))
_SUPPORTED = frozenset({"HOSE", "HNX"})
_HSX_NOTICE = "https://www.hsx.vn/vi/tin-tuc/hose-thong-bao-lich-nghi-giao-dich-nam-2026/2437411"
_HNX_GENERAL = "https://www.hnx.vn/vi-vn/chi-tiet-lich-nghi-gd-60021971.html?_page=1"
_HNX_NEW_YEAR_AMENDMENT = "https://www.hnx.vn/vi-vn/chi-tiet-lich-nghi-gd-60022084.html?_page=1"

# Dates directly described in dated exchange announcements. This is NOT
# a generated list of every 2026 trading day or ad-hoc closure.
_2026_EXPLICIT_NONTRADING = frozenset({
    date(2026, 1, 1), date(2026, 1, 2),
    date(2026, 1, 10),  # Weekend government workday, exchange closed.
    date(2026, 2, 16), date(2026, 2, 17), date(2026, 2, 18),
    date(2026, 2, 19), date(2026, 2, 20),
    date(2026, 4, 27), date(2026, 4, 30), date(2026, 5, 1),
    date(2026, 8, 22),  # Weekend government workday, exchange closed.
    date(2026, 8, 31), date(2026, 9, 1), date(2026, 9, 2),
})


def known_2026_nontrading_dates(exchange: str) -> frozenset[date]:
    if exchange not in _SUPPORTED:
        raise ValueError("Known 2026 notice coverage only for HOSE and HNX")
    return _2026_EXPLICIT_NONTRADING


def official_notice_urls(exchange: str) -> tuple[str, ...]:
    if exchange == "HOSE":
        return (_HSX_NOTICE,)
    if exchange == "HNX":
        return (_HNX_GENERAL, _HNX_NEW_YEAR_AMENDMENT)
    raise ValueError("Official notice registry only for HOSE/HNX")


class ClosureAuditState(str, Enum):
    BLOCKED = "BLOCKED"
    NO_KNOWN_COLLISION_UNCERTIFIED = "NO_KNOWN_COLLISION_UNCERTIFIED"


@dataclass(frozen=True)
class KnownClosureAudit:
    state: ClosureAuditState
    reason: str
    exchange: str
    conflicting_session_ids: tuple[str, ...]
    notice_urls: tuple[str, ...]
    full_calendar_certified: bool = False
    actionable: bool = False

    def __post_init__(self) -> None:
        if (not isinstance(self.state, ClosureAuditState)
                or not isinstance(self.conflicting_session_ids, tuple)
                or not isinstance(self.notice_urls, tuple)):
            raise ValueError("Typed closure audit fields required")
        if not self.reason or self.exchange not in _SUPPORTED:
            raise ValueError("Known exchange and reason required")
        if self.full_calendar_certified or self.actionable:
            raise ValueError("Holiday notices never certify a full calendar")


def audit_2026_notice_closure_collisions(
    inventory: D1SessionInventory,
    *,
    exchange: str,
) -> KnownClosureAudit:
    """Reject explicit exchange closure dates found in expected D1 sessions."""
    if not isinstance(inventory, D1SessionInventory):
        raise TypeError("D1SessionInventory required")
    closure_days = known_2026_nontrading_dates(exchange)
    urls = official_notice_urls(exchange)
    local_dates = tuple(slot.start_utc.astimezone(_VN).date()
                        for slot in inventory.slots)
    if any(day.year != 2026 for day in local_dates):
        return KnownClosureAudit(
            ClosureAuditState.BLOCKED,
            "YEAR_OUTSIDE_2026_NOTICE_SCOPE", exchange, (), urls,
        )
    collisions = tuple(slot.session_period_id for slot, day in
                       zip(inventory.slots, local_dates) if day in closure_days)
    if collisions:
        return KnownClosureAudit(
            ClosureAuditState.BLOCKED,
            "SESSION_ON_PUBLISHED_EXCHANGE_CLOSURE", exchange,
            collisions, urls,
        )
    return KnownClosureAudit(
        ClosureAuditState.NO_KNOWN_COLLISION_UNCERTIFIED,
        "NO_COLLISION_ONLY_FULL_CALENDAR_AND_SOURCE_COMPLETENESS_OPEN",
        exchange, (), urls,
    )
