"""End-to-end synthetic five-minute repeated scan — zero actual SSI/DNSE calls."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import tempfile
import unittest

from swing_trading.cache_fetch_planner import RefreshAction,SourceCapability
from swing_trading.fixture_scan import FixtureResponse,execute_fixture_scan
from swing_trading.incremental_cache import SyntheticIncrementalStore,full_recompute
from test_incremental_cache import bar,identity,START,FIVE


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.store=SyntheticIncrementalStore(Path(t.name)/'fixture.sqlite')
        self.store.initialize()
        self.key=identity()
        self.market=[bar(i) for i in range(30)]
        self.calls=[]

    def fetcher(self,plan):
        self.calls.append((plan.action,plan.start_utc,plan.end_utc))
        found=tuple(b for b in self.market if
                    plan.start_utc <= b.start_utc < plan.end_utc and b.end_utc<=plan.end_utc)
        return FixtureResponse(found,True,len(found)*120)

    def scan(self,minute,cap=SourceCapability.WINDOWED,interval=timedelta(minutes=30)):
        return execute_fixture_scan(store=self.store,identity=self.key,
               now_utc=START+timedelta(minutes=minute),session_start_utc=START,
               latest_expected_closed_start_utc=START+timedelta(minutes=(minute//5-1)*5),
               bar_duration=FIVE,capability=cap,fetch_fixture=self.fetcher,
               correction_reconcile_interval=interval)

    def test_0945_then_0950_downloads_one_old_plus_one_new_not_full_day(self):
        first=self.scan(45)
        self.assertEqual(first.plan.action,RefreshAction.REQUEST_FULL_SESSION)
        self.assertEqual(first.returned_rows,9)
        second=self.scan(50)
        self.assertEqual(second.plan.action,RefreshAction.REQUEST_WINDOW)
        self.assertEqual(second.returned_rows,2)
        self.assertEqual(second.update.indicator_bars_recomputed,1)
        self.assertEqual(second.bytes_received,240)
        self.assertEqual(len(self.store.read_bars(self.key)),10)
        self.assertEqual(self.store.read_checkpoints(self.key),full_recompute(self.store.read_bars(self.key)))
        self.assertFalse(second.market_eligible)

    def test_repeat_same_closed_window_no_request_before_refresh_deadline(self):
        self.scan(45)
        second=self.scan(46)
        self.assertTrue(second.cache_hit)
        self.assertEqual((second.fixture_requests,second.bytes_received),(0,0))
        self.assertEqual(len(self.calls),1)
        self.assertFalse(second.source_coverage_verified)

    def test_same_window_overdue_still_fetches_but_no_indicator_recompute(self):
        self.scan(45)
        second=self.scan(49)
        self.assertTrue(second.cache_hit) # within 5-minute policy
        third=self.scan(50)
        self.assertFalse(third.cache_hit)
        self.assertEqual(third.update.indicator_bars_recomputed,1)

    def test_periodic_full_session_detects_old_source_correction(self):
        self.scan(45)
        self.market[2]=bar(2,close=333,rev='r2')
        p=self.scan(50,interval=timedelta(minutes=5))
        self.assertEqual(p.plan.action,RefreshAction.REQUEST_FULL_SESSION)
        self.assertEqual(p.update.revised,1)
        self.assertEqual(p.update.indicator_bars_recomputed,8)
        self.assertEqual(self.store.read_checkpoints(self.key),full_recompute(self.store.read_bars(self.key)))

    def test_full_session_only_provider_refetches_full_session_honestly(self):
        self.scan(45,cap=SourceCapability.FULL_SESSION)
        p=self.scan(50,cap=SourceCapability.FULL_SESSION)
        self.assertEqual(p.plan.action,RefreshAction.REQUEST_FULL_SESSION)
        self.assertEqual(p.returned_rows,10)
        self.assertEqual(p.update.indicator_bars_recomputed,1)

    def test_unknown_capability_never_calls_callback(self):
        p=self.scan(45,cap=SourceCapability.UNKNOWN)
        self.assertEqual(p.plan.action,RefreshAction.BLOCKED)
        self.assertEqual(self.calls,[])

    def test_restart_does_not_refetch_history_if_cursor_is_valid(self):
        self.scan(45)
        self.store=SyntheticIncrementalStore(self.store.path)
        p=self.scan(50)
        self.assertEqual(p.plan.action,RefreshAction.REQUEST_WINDOW)
        self.assertEqual(p.returned_rows,2)

    def test_source_returned_empty_complete_scope_removes_missing_rows_in_scope(self):
        self.scan(45)
        self.market=[b for b in self.market if b.start_utc!=bar(8).start_utc]
        p=self.scan(50)
        self.assertEqual(p.update.deleted,1)
        self.assertEqual(self.store.read_checkpoints(self.key),full_recompute(self.store.read_bars(self.key)))

    def test_incomplete_page_cannot_delete_existing_bars(self):
        self.scan(45)
        def partial(_plan):return FixtureResponse((),False,0)
        p=execute_fixture_scan(store=self.store,identity=self.key,
            now_utc=START+timedelta(minutes=50),session_start_utc=START,
            latest_expected_closed_start_utc=bar(9).start_utc,bar_duration=FIVE,
            capability=SourceCapability.WINDOWED,fetch_fixture=partial)
        self.assertEqual(p.update.deleted,0)
        self.assertEqual(len(self.store.read_bars(self.key)),9)

if __name__=='__main__':unittest.main()
