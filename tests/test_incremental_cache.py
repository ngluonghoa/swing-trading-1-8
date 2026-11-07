"""P0.C1 synthetic-only persistence, append/correction and checkpoint tests."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path
import sqlite3
import tempfile
import unittest
from contextlib import closing

from swing_trading.incremental_cache import (
    Provider,CacheIdentity,FixtureBar,SyntheticIncrementalStore,
    advance_checkpoint,full_recompute,invalidation_preview,
)
from swing_trading.cache_fetch_planner import plan_refresh,SourceCapability,RefreshAction

UTC=timezone.utc
START=datetime(2026,11,6,2,0,tzinfo=UTC)
FIVE=timedelta(minutes=5)


def identity(provider=Provider.SSI, **kw):
    return CacheIdentity(provider=provider,endpoint_id='fixture.ohlc',instrument_id='SYN_FPT',
                         exchange='HOSE',timeframe='M5',session_id='2026-11-06.CONTINUOUS',
                         price_basis='RAW',adjustment_revision='ADJ1',calendar_version='CAL1',
                         aggregation_policy_version='AG1',indicator_version='EMA20_ATR14_1',**kw)


def bar(n,close=None,rev='r1',closed=True):
    c=Decimal(100+n) if close is None else Decimal(close)
    return FixtureBar(START+FIVE*n,START+FIVE*(n+1),c-1,c+2,c-2,c,1000+n,
                      rev,START+FIVE*(n+1),closed=closed)


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'test_fixture.sqlite'
        self.store=SyntheticIncrementalStore(self.path)
        self.store.initialize()
        self.key=identity()

    def apply(self,bars,at=25,scope=0,end=None,complete=False,full=False,key=None):
        return self.store.apply_fixture_window(key or self.key,tuple(bars),
                         observed_at_utc=START+FIVE*at,
                         scope_start_utc=START+FIVE*scope,
                         scope_end_utc=START+FIVE*(at if end is None else end),
                         complete_scope=complete,full_session_reconciled=full)

    def assert_full_parity(self,key=None):
        k=key or self.key
        self.assertEqual(self.store.read_checkpoints(k),full_recompute(self.store.read_bars(k)))

    def test_initial_cold_build_creates_immutable_closed_checkpoints(self):
        a=self.apply((bar(i) for i in range(20)),at=20,complete=True,full=True)
        self.assertEqual((a.inserted,a.indicator_bars_recomputed),(20,20))
        self.assertEqual(a.invalidated_layers,('L1','L2','L3','L4','L5'))
        self.assertEqual(len(self.store.read_checkpoints(self.key)),20)
        self.assert_full_parity()
        self.assertIsNone(self.store.read_checkpoints(self.key)[12].atr14)
        self.assertIsNotNone(self.store.read_checkpoints(self.key)[13].atr14)

    def test_warm_refetch_identical_no_recomputation(self):
        self.apply([bar(i) for i in range(20)],at=20,complete=True,full=True)
        u=self.apply([bar(i) for i in range(18,20)],at=21,scope=18,complete=True)
        self.assertEqual((u.inserted,u.revised,u.unchanged,u.indicator_bars_recomputed),(0,0,2,0))
        self.assertEqual(u.invalidated_layers,())
        self.assert_full_parity()

    def test_append_recomputes_only_one_new_bar(self):
        self.apply([bar(i) for i in range(20)],at=20,complete=True,full=True)
        u=self.apply([bar(19),bar(20)],at=21,scope=19,complete=True)
        self.assertEqual((u.inserted,u.unchanged,u.indicator_bars_recomputed),(1,1,1))
        self.assert_full_parity()

    def test_revise_recent_recomputes_affected_tail_not_entire_history(self):
        self.apply([bar(i) for i in range(22)],at=22,complete=True,full=True)
        edited=bar(20,close='151',rev='r2')
        u=self.apply([edited,bar(21)],at=23,scope=20,complete=True)
        self.assertEqual((u.revised,u.indicator_bars_recomputed),(1,2))
        self.assertEqual(u.first_dirty_utc,bar(20).start_utc)
        self.assert_full_parity()

    def test_old_correction_recomputes_causal_tail(self):
        self.apply([bar(i) for i in range(22)],at=22,complete=True,full=True)
        u=self.apply([bar(4,close=110,rev='r2')],at=23,scope=4,complete=False)
        self.assertEqual(u.indicator_bars_recomputed,18)
        self.assert_full_parity()

    def test_delete_with_complete_window_only(self):
        self.apply([bar(i) for i in range(10)],at=10,complete=True,full=True)
        u=self.apply([bar(7),bar(9)],at=11,scope=7,complete=True)
        self.assertEqual(u.deleted,1)
        self.assertNotIn(bar(8).start_utc,[x.start_utc for x in self.store.read_bars(self.key)])
        self.assert_full_parity()

    def test_no_delete_for_incomplete_source_page(self):
        self.apply([bar(i) for i in range(10)],at=10,complete=True,full=True)
        u=self.apply([bar(9)],at=11,scope=7,complete=False)
        self.assertEqual(u.deleted,0)
        self.assertEqual(len(self.store.read_bars(self.key)),10)

    def test_source_lineage_revision_without_changed_content(self):
        self.apply([bar(0)],at=1,complete=True,full=True)
        u=self.apply([bar(0,rev='r2')],at=2,scope=0)
        self.assertEqual((u.lineage_only,u.indicator_bars_recomputed),(1,0))
        self.assertEqual(self.store.read_bars(self.key)[0].revision,'r2')

    def test_closed_vs_open_isolation(self):
        self.apply([bar(0)],at=1,complete=True,full=True)
        u=self.apply([bar(1,closed=False)],at=2,scope=1)
        self.assertEqual((u.ignored_open,u.indicator_bars_recomputed),(1,0))
        self.assertEqual(len(self.store.read_bars(self.key)),1)
        with self.assertRaises(ValueError):
            advance_checkpoint(bar(1,closed=False),self.store.read_checkpoints(self.key)[0])

    def test_cold_warm_store_survives_sqlite_restart(self):
        self.apply([bar(i) for i in range(20)],at=20,complete=True,full=True)
        new_store=SyntheticIncrementalStore(self.path)
        self.assertEqual(len(new_store.read_bars(self.key)),20)
        self.assertEqual(new_store.read_checkpoints(self.key),self.store.read_checkpoints(self.key))
        self.store=new_store
        self.apply([bar(19),bar(20)],at=21,scope=19,complete=True)
        self.assert_full_parity()

    def test_provider_isolation_and_identity_version_isolation(self):
        self.apply([bar(i) for i in range(4)],at=4,complete=True,full=True)
        dn=identity(Provider.DNSE)
        self.assertEqual(self.store.read_bars(dn),())
        self.apply([bar(i,close=1000+i) for i in range(4)],at=4,complete=True,full=True,key=dn)
        self.assertNotEqual(self.store.read_bars(self.key)[0].close,self.store.read_bars(dn)[0].close)
        new_version=replace(self.key,adjustment_revision='ADJ2')
        self.assertEqual(self.store.read_bars(new_version),())
        changed_rights=replace(self.key,source_rights_policy_version='RIGHTS.REVOKED')
        changed_indicator=replace(self.key,indicator_parameter_version='EMA20.ATR14.NEW')
        self.assertEqual(self.store.read_bars(changed_rights),())
        self.assertEqual(self.store.read_checkpoints(changed_indicator),())

    def test_persisted_cursor_and_delta_plan_after_restart(self):
        self.apply([bar(i) for i in range(10)],at=10,complete=True,full=True)
        cur=SyntheticIncrementalStore(self.path).cursor(self.key)
        self.assertEqual(cur.last_closed_start_utc,bar(9).start_utc)
        p=plan_refresh(now_utc=START+FIVE*11,session_start_utc=START,
                       latest_expected_closed_start_utc=bar(10).start_utc,
                       bar_duration=FIVE,capability=SourceCapability.WINDOWED,cursor=cur)
        self.assertEqual(p.action,RefreshAction.REQUEST_WINDOW)
        self.assertEqual(p.start_utc,bar(9).start_utc)

    def test_cache_does_not_grant_rights_or_real_data_storage(self):
        with self.assertRaises(PermissionError):
            replace(self.key,environment='PRODUCTION')
        u=self.apply([bar(0)],at=1)
        self.assertFalse(u.market_authorized)
        self.assertTrue(u.fixture_only)

    def test_corrupted_fixture_data_is_detected(self):
        self.apply([bar(0)],at=1)
        with closing(sqlite3.connect(self.path)) as c:
            c.execute('UPDATE fixture_bars SET c=?',('101',))
            c.commit()
        with self.assertRaisesRegex(RuntimeError,'digest mismatch'):
            self.store.read_bars(self.key)

    def test_atomic_reject_invalid_update_preserves_old_snapshot(self):
        self.apply([bar(0)],at=1)
        before=self.store.read_bars(self.key)
        with self.assertRaises(ValueError):
            self.apply([bar(1),bar(0)],at=3)
        self.assertEqual(self.store.read_bars(self.key),before)

    def test_future_unknown_record_rejected(self):
        with self.assertRaisesRegex(ValueError,'unknown at observation'):
            self.apply([bar(3)],at=3)

    def test_closed_record_cannot_be_persisted_before_bar_closes(self):
        b=replace(bar(2),end_utc=START+FIVE*4,first_known_utc=START+FIVE*3)
        with self.assertRaisesRegex(ValueError,'actually closes'):
            self.apply([b],at=3)

    def test_no_forward_clock_regression(self):
        self.apply([bar(0)],at=3)
        with self.assertRaisesRegex(ValueError,'regress cache observation clock'):
            self.apply([bar(0)],at=2)

    def test_incomplete_full_scope_marking_refused(self):
        with self.assertRaises(ValueError):
            self.apply([bar(0)],at=1,complete=False,full=True)

    def test_digest_identity_and_normalized_semantics(self):
        b=bar(1)
        self.assertEqual(b.normalized_digest,bar(1,rev='r2').normalized_digest)
        self.assertNotEqual(b.normalized_digest,bar(1,close=999).normalized_digest)
        self.assertNotEqual(self.key.fingerprint,identity(provider=Provider.DNSE).fingerprint)

    def test_invalid_fractional_volume_and_hlc_rejected(self):
        with self.assertRaises(ValueError):
            replace(bar(1),volume=Decimal('1.2'))
        with self.assertRaises(ValueError):
            replace(bar(1),low=Decimal('99999'))

    def test_zero_volume_is_not_missing(self):
        b=replace(bar(0),volume=0)
        self.apply([b],at=1)
        self.assertEqual(self.store.read_bars(self.key)[0].volume,0)

    def test_feature_invalidation_rules(self):
        self.assertEqual(invalidation_preview('RULE_OR_PARAMETER'),('L4','L5'))
        self.assertEqual(invalidation_preview('INDEX_OR_SECTOR'),('L2','L3','L4','L5'))
        self.assertEqual(invalidation_preview('UI_ONLY'),('L5',))
        self.assertEqual(invalidation_preview('NO_CHANGE'),())

    def test_meta_does_not_silently_certify_live_source(self):
        self.apply([bar(0)],at=1,complete=True,full=True)
        c=self.store.cursor(self.key)
        self.assertIsNotNone(c)
        self.assertFalse(hasattr(c,'signer_verified'))

    def test_missing_seed_replays_full_required_history(self):
        self.apply([bar(i) for i in range(10)],at=10,complete=True,full=True)
        u=self.apply([bar(0,close=200,rev='r2')],at=11,scope=0)
        self.assertEqual(u.indicator_bars_recomputed,10)
        self.assert_full_parity()

    def test_source_revision_history_not_retroactively_used(self):
        with self.assertRaises(ValueError):
            replace(bar(1),first_known_utc=START)


    def test_lineage_only_event_is_append_only(self):
        self.apply([bar(0)],at=1)
        self.apply([bar(0,rev='r2')],at=2)
        with closing(sqlite3.connect(self.path)) as c:
            rows=c.execute('SELECT event_type FROM fixture_lineage ORDER BY id').fetchall()
        self.assertEqual([x[0] for x in rows],['APPEND','LINEAGE_ONLY'])

    def test_correction_first_known_cannot_recede(self):
        self.apply([bar(1)],at=2,scope=1)
        old=self.store.read_bars(self.key)
        from dataclasses import replace
        earlier=replace(bar(1,rev='r2'),first_known_utc=START+FIVE)
        with self.assertRaisesRegex(ValueError,'move backwards'):
            self.apply([earlier],at=3,scope=1)
        self.assertEqual(old,self.store.read_bars(self.key))


if __name__=='__main__':unittest.main()
