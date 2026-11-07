"""Synthetic weekly chunk reuse and globally valid SQLite restore (C4A)."""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from swing_trading.incremental_cache import (
    CacheIdentity, FixtureBar, Provider, SyntheticIncrementalStore, full_recompute,
)
from swing_trading.segmented_cache import (
    SyntheticWeeklyChunkStore, FixtureWindowIndex, FixtureWindowRef,
    require_authorized_window_cache,
)

UTC = timezone.utc
T0 = datetime(2026, 1, 5, 2, tzinfo=UTC)  # Monday UTC
NOW = datetime(2026, 2, 2, tzinfo=UTC)

def key(name="TEST001", provider=Provider.SSI):
    return CacheIdentity(provider=provider, endpoint_id="fake.m5",instrument_id=name,
        exchange="HOSE",timeframe="D1",session_id="FIXTURE.2026.Q1",
        price_basis="RAW", adjustment_revision="A1",calendar_version="VNTEST1",
        aggregation_policy_version="FAKEAG1",indicator_version="EMA20ATR14")

def fake(day, *, price=None, revision="r1", known=None):
    c = Decimal(100 + day if price is None else price)
    start = T0 + timedelta(days=day)
    return FixtureBar(start, start+timedelta(days=1), c-1,c+2,c-2,c,
                      1000+day, revision, known or start+timedelta(days=1))

class WeeklySegmentsTest(unittest.TestCase):
    def setUp(self):
        temp=TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)
        self.working=SyntheticIncrementalStore(self.path/"fixture.sqlite")
        self.working.initialize()
        self.identity=key()
        self.cloud=SyntheticWeeklyChunkStore()
        self.bars=tuple(fake(i) for i in range(15))

    def commit(self,bars=None,head=None,identity=None,**kw):
        return self.cloud.commit(identity or self.identity,
             self.bars if bars is None else bars,
             expected_head=head,observed_at_utc=NOW,**kw)

    def test_three_windows_initial(self):
        r=self.commit()
        self.assertEqual((r.created_windows,r.reused_windows,r.manifest_changed),(3,0,True))
        self.assertEqual(self.cloud.object_count,3)
        self.assertEqual(self.cloud.load(self.identity,pinned_head=self.cloud.head(self.identity)),self.bars)

    def test_noop_does_not_rewrite_existing_windows(self):
        self.commit()
        head=self.cloud.head(self.identity)
        r=self.commit(head=head)
        self.assertEqual((r.created_windows,r.reused_windows,r.manifest_changed),(0,3,False))
        self.assertEqual(self.cloud.head(self.identity),head)
        self.assertEqual(self.cloud.object_count,3)
        self.assertEqual((r.actual_drive_calls,r.market_data_calls,r.live_cache_approved),(0,0,False))

    def test_append_into_same_week_changes_only_final_window(self):
        self.commit()
        r=self.commit(self.bars+(fake(15),),head=self.cloud.head(self.identity))
        self.assertEqual((r.created_windows,r.reused_windows),(1,2))
        self.assertEqual(self.cloud.object_count,4)

    def test_append_next_week_changes_only_new_window(self):
        self.commit()
        rows=tuple(fake(i) for i in range(21))
        r=self.commit(rows,head=self.cloud.head(self.identity))
        self.assertEqual((r.created_windows,r.reused_windows),(1,3))
        self.assertEqual(self.cloud.object_count,4)

    def test_revision_old_window_changes_only_one(self):
        self.commit()
        old=self.cloud.head(self.identity)
        updated=tuple(fake(i,price=Decimal(155),revision="r2",known=NOW-timedelta(hours=2))
                      if i==2 else fake(i) for i in range(15))
        r=self.commit(updated,head=old)
        self.assertEqual((r.created_windows,r.reused_windows),(1,2))
        self.assertEqual(self.cloud.object_count,4)
        self.assertNotEqual(old,self.cloud.head(self.identity))
        newer=self.cloud._indexes[self.cloud.head(self.identity)]
        self.assertEqual((newer.generation,newer.parent_sha256),(2,old))

    def test_other_symbol_preserves_head(self):
        self.commit()
        another=key("TEST002")
        self.cloud.commit(another,self.bars,expected_head=None,observed_at_utc=NOW)
        other=self.cloud.head(another)
        edited=(replace(self.bars[0],close=Decimal(109),revision="r2",
                        first_known_utc=NOW-timedelta(hours=1)),)+self.bars[1:]
        self.commit(edited,head=self.cloud.head(self.identity))
        self.assertEqual(self.cloud.head(another),other)

    def test_other_provider_isolated(self):
        self.commit()
        other=key(provider=Provider.VCBS)
        self.cloud.commit(other,self.bars,expected_head=None,observed_at_utc=NOW)
        self.assertNotEqual(self.cloud.head(other),self.cloud.head(self.identity))

    def test_selected_window_read_does_not_fetch_all(self):
        self.commit()
        head=self.cloud.head(self.identity)
        selected=self.cloud.load(self.identity,pinned_head=head,windows=("2026-01-12",))
        self.assertEqual(selected,self.bars[7:14])

    def test_selected_window_can_avoid_unselected_corrupt_chunk(self):
        self.commit()
        head=self.cloud.head(self.identity)
        self.cloud.corrupt_latest_window_for_test(self.identity)
        self.assertEqual(self.cloud.load(self.identity,pinned_head=head,windows=("2026-01-05",)),
                         self.bars[:7])
        with self.assertRaises(ValueError):
            self.cloud.load(self.identity,pinned_head=head)

    def test_corruption_is_checked_on_noop(self):
        self.commit()
        self.cloud.corrupt_latest_window_for_test(self.identity)
        with self.assertRaises(ValueError):self.commit(head=self.cloud.head(self.identity))

    def test_wrong_head_denied(self):
        self.commit()
        with self.assertRaises(ValueError):
            self.cloud.load(self.identity,pinned_head="0"*64)

    def test_stale_writer_denied(self):
        self.commit()
        with self.assertRaises(ValueError):self.commit(head=None)

    def test_missing_prior_week_requires_authoritative_deletion(self):
        self.commit()
        with self.assertRaises(ValueError):
            self.commit(self.bars[7:],head=self.cloud.head(self.identity))

    def test_roll_back_floor_denied(self):
        self.commit()
        with self.assertRaises(ValueError):
            self.cloud.load(self.identity,pinned_head=self.cloud.head(self.identity),
                            minimum_generation=2)

    def test_fault_after_staging_has_no_pointer(self):
        with self.assertRaises(RuntimeError):
            self.commit(fail_after_staging=True)
        self.assertIsNone(self.cloud.head(self.identity))
        self.assertEqual(self.cloud.object_count,3)
        self.assertTrue(self.commit().manifest_changed)

    def test_full_restore_replays_global_indicators(self):
        self.commit()
        restored=SyntheticIncrementalStore(self.path/"restored.sqlite")
        restored.initialize()
        n=self.cloud.restore_full(restored,self.identity,pinned_head=self.cloud.head(self.identity))
        self.assertEqual(n,15)
        self.assertEqual(restored.read_bars(self.identity),self.bars)
        self.assertEqual(restored.read_checkpoints(self.identity),full_recompute(self.bars))
        with self.assertRaises(ValueError):
            self.cloud.restore_full(restored,self.identity,pinned_head=self.cloud.head(self.identity))

    def test_full_restore_after_historical_revision(self):
        self.commit()
        edited=tuple(fake(i,price=Decimal(105),revision="r2",known=NOW-timedelta(hours=1))
                     if i==3 else fake(i) for i in range(15))
        self.commit(edited,head=self.cloud.head(self.identity))
        restored=SyntheticIncrementalStore(self.path/"restored.sqlite")
        restored.initialize()
        self.cloud.restore_full(restored,self.identity,pinned_head=self.cloud.head(self.identity))
        self.assertEqual(restored.read_checkpoints(self.identity),full_recompute(edited))

    def test_reject_open_candle(self):
        with self.assertRaises(ValueError):
            self.commit(self.bars[:-1]+(replace(self.bars[-1],closed=False),))

    def test_reject_future_known_revision(self):
        with self.assertRaises(ValueError):
            self.commit(self.bars[:-1]+(replace(self.bars[-1],first_known_utc=NOW+timedelta(days=1)),))

    def test_reject_wrong_window_and_noncanonical_ref(self):
        self.commit()
        man=self.cloud._indexes[self.cloud.head(self.identity)]
        with self.assertRaises(ValueError):
            FixtureWindowRef("2026-01-06", man.windows[0].name,
                             man.windows[0].sha256,man.windows[0].byte_count,7)
        with self.assertRaises(ValueError):
            self.cloud.load(self.identity,pinned_head=man.digest,windows=("2026-01-05","2026-01-05"))

    def test_no_real_storage_authorization(self):
        with self.assertRaises(PermissionError):
            require_authorized_window_cache()

if __name__=="__main__":
    unittest.main()
