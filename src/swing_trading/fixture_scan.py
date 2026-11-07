"""SYNTHETIC-only refresh coordinator to measure actual avoided fixture fetches.

The injected callback is deliberately NOT an SSI/DNSE transport: no production
provider permission, rate-limit control, market-source quality, or trading API.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from .cache_fetch_planner import (
    RefreshAction, RefreshPlan, SourceCapability, plan_refresh, _utc,
)
from .incremental_cache import CacheIdentity, CacheUpdate, FixtureBar, SyntheticIncrementalStore


@dataclass(frozen=True)
class FixtureResponse:
    observations: tuple[FixtureBar,...]
    complete_scope: bool
    bytes_received: int

    def __post_init__(self) -> None:
        if not isinstance(self.observations,tuple) or any(not isinstance(x,FixtureBar) for x in self.observations):
            raise TypeError("Fixture response must have typed immutable records")
        if type(self.complete_scope) is not bool:
            raise TypeError("Response completeness must be boolean")
        if type(self.bytes_received) is not int or self.bytes_received < 0:
            raise ValueError("Nonnegative measured byte count required")


@dataclass(frozen=True)
class FixtureScanReceipt:
    plan: RefreshPlan
    fixture_requests: int
    bytes_received: int
    returned_rows: int
    update: CacheUpdate | None
    cache_hit: bool
    source_coverage_verified: bool = False
    market_eligible: bool = False


def execute_fixture_scan(
    *,
    store: SyntheticIncrementalStore,
    identity: CacheIdentity,
    now_utc: datetime,
    session_start_utc: datetime,
    latest_expected_closed_start_utc: datetime,
    bar_duration: timedelta,
    capability: SourceCapability,
    fetch_fixture: Callable[[RefreshPlan],FixtureResponse],
    correction_reconcile_interval: timedelta = timedelta(minutes=30),
) -> FixtureScanReceipt:
    """Run planned *fixture* scan, deduplicate calculations and count requests.

    A cache hit never certifies current market freshness or source entitlement.
    Producer must supply truthful response completeness/bytes. In production
    any authenticating source adapter and exchange/calendar rules are separate
    gated work items, not an option on this function.
    """
    if not isinstance(store,SyntheticIncrementalStore) or not isinstance(identity,CacheIdentity):
        raise TypeError("Synthetic fixture store and identity required")
    if not callable(fetch_fixture):
        raise TypeError("Explicit fixture callback required")
    now = _utc(now_utc)
    plan = plan_refresh(
        now_utc=now,session_start_utc=session_start_utc,
        latest_expected_closed_start_utc=latest_expected_closed_start_utc,
        bar_duration=bar_duration,capability=capability,cursor=store.cursor(identity),
        correction_reconcile_interval=correction_reconcile_interval,
    )
    if plan.action is RefreshAction.REUSE_CLOSED:
        return FixtureScanReceipt(plan,0,0,0,None,True)
    if plan.action is RefreshAction.BLOCKED:
        return FixtureScanReceipt(plan,0,0,0,None,False)
    response=fetch_fixture(plan)
    if not isinstance(response,FixtureResponse):
        raise TypeError("Fixture callback returned untyped response")
    # Never mark full-range revalidation when paging/gaps are not certified.
    full=(plan.action is RefreshAction.REQUEST_FULL_SESSION and response.complete_scope)
    update=store.apply_fixture_window(identity,response.observations,
        observed_at_utc=now,scope_start_utc=plan.start_utc,scope_end_utc=plan.end_utc,
        complete_scope=response.complete_scope,full_session_reconciled=full)
    return FixtureScanReceipt(plan,1,response.bytes_received,len(response.observations),
                              update,False)
