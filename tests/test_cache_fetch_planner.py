"""P0.C1 synthetic refresh planning tests; no network market requests."""
import unittest
from datetime import datetime, timedelta, timezone

from swing_trading.cache_fetch_planner import (
    SourceCapability,SourceCursor,RefreshAction,plan_refresh,
)

UTC=timezone.utc
T0=datetime(2026,11,6,2,0,tzinfo=UTC)
FIVE=timedelta(minutes=5)


def plan(*, minute=50, current=45, checked=45, full=45,
         cap=SourceCapability.WINDOWED, cursor=True, **kw):
    cur=(SourceCursor(T0+timedelta(minutes=current),
                      T0+timedelta(minutes=checked),
                      T0+timedelta(minutes=full) if full is not None else None)
         if cursor else None)
    return plan_refresh(now_utc=T0+timedelta(minutes=minute),
                        session_start_utc=T0,
                        latest_expected_closed_start_utc=T0+timedelta(minutes=(minute//5-1)*5),
                        bar_duration=FIVE,capability=cap,cursor=cur,**kw)


class PlannerTests(unittest.TestCase):
    def test_first_call_full_scope_cold(self):
        p=plan(cursor=False)
        self.assertEqual(p.action,RefreshAction.REQUEST_FULL_SESSION)
        self.assertEqual(p.start_utc,T0)
        self.assertFalse(p.data_authorized)

    def test_five_minute_delta_overlaps_last_bar(self):
        p=plan(current=40)
        self.assertEqual(p.action,RefreshAction.REQUEST_WINDOW)
        self.assertEqual(p.start_utc,T0+timedelta(minutes=40))
        self.assertEqual(p.end_utc,T0+timedelta(minutes=50))
        self.assertEqual(p.reason,'NEW_CLOSED_BAR')

    def test_api_full_day_only_is_honest_about_refetch(self):
        p=plan(cap=SourceCapability.FULL_SESSION)
        self.assertEqual(p.action,RefreshAction.REQUEST_FULL_SESSION)
        self.assertEqual(p.start_utc,T0)

    def test_unknown_provider_capability_blocks(self):
        self.assertEqual(plan(cap=SourceCapability.UNKNOWN).action,RefreshAction.BLOCKED)

    def test_periodic_reconcile_catches_older_corrections(self):
        p=plan(minute=50,full=10)
        self.assertEqual(p.action,RefreshAction.REQUEST_FULL_SESSION)
        self.assertEqual(p.reason,'CORRECTION_RECONCILIATION_DUE')

    def test_no_full_reconcile_requires_full_fetch(self):
        self.assertEqual(plan(full=None).action,RefreshAction.REQUEST_FULL_SESSION)

    def test_reuse_when_no_new_closed_and_recently_checked(self):
        p=plan(minute=49,current=40,checked=47,full=47)
        self.assertEqual(p.action,RefreshAction.REUSE_CLOSED)
        self.assertFalse(p.certified_source_freshness)

    def test_recheck_after_interval(self):
        p=plan(minute=49,current=40,checked=40,full=40)
        self.assertEqual(p.action,RefreshAction.REQUEST_WINDOW)
        self.assertEqual(p.reason,'SOURCE_REVALIDATION_DUE')

    def test_provisional_forces_fetch(self):
        p=plan(minute=49,current=40,checked=47,full=47,provisional_requested=True)
        self.assertEqual(p.action,RefreshAction.REQUEST_WINDOW)

    def test_end_of_session_reuse_requires_verified_immutable_head(self):
        p=plan(minute=50,session_ended_verified=True,immutable_source_head_verified=True)
        self.assertEqual(p.action,RefreshAction.REUSE_CLOSED)
        self.assertFalse(p.data_authorized)

    def test_last_bar_cannot_be_from_future(self):
        with self.assertRaisesRegex(ValueError,'actually closed'):
            plan_refresh(now_utc=T0+FIVE,session_start_utc=T0,
                         latest_expected_closed_start_utc=T0+FIVE,
                         bar_duration=FIVE,capability=SourceCapability.WINDOWED,cursor=None)

    def test_cursor_future_observation_rejected(self):
        with self.assertRaisesRegex(ValueError,'future cache'):
            plan(minute=50,checked=51,full=45,current=45)

    def test_cursor_ahead_of_market_clock_fails_closed(self):
        self.assertEqual(plan(minute=50,current=46,checked=48,full=48).action,
                         RefreshAction.BLOCKED)

    def test_invalid_calendar_and_duration_block(self):
        with self.assertRaises(ValueError):
            plan_refresh(now_utc=T0+FIVE,session_start_utc=T0+FIVE,
                         latest_expected_closed_start_utc=T0,
                         bar_duration=FIVE,capability=SourceCapability.WINDOWED,cursor=None)
        with self.assertRaises(ValueError):
            plan_refresh(now_utc=T0+FIVE,session_start_utc=T0,
                         latest_expected_closed_start_utc=T0,
                         bar_duration=timedelta(0),capability=SourceCapability.WINDOWED,cursor=None)

    def test_wrong_type_overlap_and_source_rejected(self):
        with self.assertRaises((TypeError,ValueError)):
            plan(overlap_bars=True)
        with self.assertRaises(TypeError):
            plan(cap='WINDOWED')

    def test_overlap_bounded_at_session_start(self):
        p=plan(minute=10,current=0,checked=5,full=5,overlap_bars=24)
        self.assertEqual(p.start_utc,T0)

    def test_reconcile_is_not_an_entitlement(self):
        p=plan(minute=50,full=0)
        self.assertFalse(p.certified_source_freshness)
        self.assertFalse(p.data_authorized)


if __name__=='__main__':unittest.main()
