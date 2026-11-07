"""C3B synthetic-only partition chunks, version manifests and mixed-scope reuse."""
import json
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from swing_trading.incremental_cache import (
    CacheIdentity, FixtureBar, Provider, SyntheticIncrementalStore, full_recompute,
)
from swing_trading.partition_chunk_cache import (
    MAGIC, PartitionWrite, FixturePartitionManifest, SyntheticDrivePartitionIndex,
    decode_fixture_chunk, encode_fixture_chunk, require_real_market_cache_transport,
)

UTC=timezone.utc
START=datetime(2026,11,6,2,0,tzinfo=UTC)
FIVE=timedelta(minutes=5)
NOW=START+FIVE*40


def identity(ticker="TEST001",provider=Provider.SSI,timeframe="M5",**changes):
    vals=dict(provider=provider,endpoint_id="fixture.ohlc",instrument_id=ticker,
        exchange="HOSE",timeframe=timeframe,session_id="2026-11-06.CONTINUOUS",
        price_basis="RAW",adjustment_revision="ADJ1",calendar_version="CAL1",
        aggregation_policy_version="AG1",indicator_version="EMA_ATR_V1")
    vals.update(changes)
    return CacheIdentity(**vals)


def bar(n,close=None,revision="r1"):
    c=Decimal(100+n if close is None else close)
    return FixtureBar(START+FIVE*n,START+FIVE*(n+1),
        c-1,c+2,c-2,c,1000+n,revision,START+FIVE*(n+1))


class ChunkTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)
        self.store=SyntheticIncrementalStore(self.path/"working.sqlite")
        self.store.initialize()
        self.cloud=SyntheticDrivePartitionIndex()
        self.key=identity()
        self.apply(self.key,tuple(bar(i) for i in range(20)),at=20,scope=0,full=True)

    def apply(self,k,rows,*,at=40,scope=0,full=False):
        return self.store.apply_fixture_window(
            k,tuple(rows),observed_at_utc=START+FIVE*at,
            scope_start_utc=START+FIVE*scope,
            scope_end_utc=START+FIVE*at,
            complete_scope=full,full_session_reconciled=full)

    def stage(self,key=None,head=None,**kw):
        k=key or self.key
        return self.cloud.stage_and_publish(k,self.store.read_bars(k),
            expected_head_sha256=head,created_at_utc=NOW,**kw)

    def pin(self,key=None):
        return self.cloud.active_manifest_sha(key or self.key)

    def test_encode_decode_identity_round_trip(self):
        bars=self.store.read_bars(self.key)
        self.assertEqual(decode_fixture_chunk(encode_fixture_chunk(self.key,bars),
                         expected_identity=self.key),bars)
    def test_same_bytes_after_repeated_encode(self):
        bars=self.store.read_bars(self.key)
        self.assertEqual(encode_fixture_chunk(self.key,bars),encode_fixture_chunk(self.key,bars))
    def test_marker_required(self):
        original=encode_fixture_chunk(self.key,self.store.read_bars(self.key))
        with self.assertRaises(ValueError):
            decode_fixture_chunk(original.removeprefix(MAGIC),expected_identity=self.key)
    def test_other_instrument_cannot_decode(self):
        with self.assertRaises(ValueError):
            decode_fixture_chunk(encode_fixture_chunk(self.key,self.store.read_bars(self.key)),
                                 expected_identity=identity("TEST002"))
    def test_other_provider_cannot_decode(self):
        with self.assertRaises(ValueError):
            decode_fixture_chunk(encode_fixture_chunk(self.key,self.store.read_bars(self.key)),
                                 expected_identity=identity(provider=Provider.DNSE))
    def test_other_timeframe_cannot_decode(self):
        with self.assertRaises(ValueError):
            decode_fixture_chunk(encode_fixture_chunk(self.key,self.store.read_bars(self.key)),
                                 expected_identity=identity(timeframe="M15"))
    def test_other_corporate_action_policy_cannot_decode(self):
        with self.assertRaises(ValueError):
            decode_fixture_chunk(encode_fixture_chunk(self.key,self.store.read_bars(self.key)),
                                 expected_identity=identity(adjustment_revision="ADJ2"))
    def test_no_open_candle(self):
        b=bar(0)
        with self.assertRaises(ValueError):
            encode_fixture_chunk(self.key,(replace(b,closed=False),))
    def test_no_duplicate_timestamp(self):
        b=bar(0)
        with self.assertRaises(ValueError):
            encode_fixture_chunk(self.key,(b,b))
    def test_no_out_of_order(self):
        with self.assertRaises(ValueError):
            encode_fixture_chunk(self.key,(bar(1),bar(0)))
    def test_no_empty_partition(self):
        with self.assertRaises(ValueError):
            encode_fixture_chunk(self.key,())
    def test_no_list_instead_of_tuple(self):
        with self.assertRaises(ValueError):
            encode_fixture_chunk(self.key,[bar(0)])
    def test_no_fake_rights_assertion(self):
        chunk=encode_fixture_chunk(self.key,self.store.read_bars(self.key))
        raw=json.loads(chunk[len(MAGIC):])
        raw["market_data_authorized"]=True
        forged=MAGIC+json.dumps(raw,sort_keys=True,separators=(",",":")).encode()
        with self.assertRaises(ValueError):
            decode_fixture_chunk(forged,expected_identity=self.key)
    def test_no_extra_payload_fields(self):
        chunk=encode_fixture_chunk(self.key,self.store.read_bars(self.key))
        raw=json.loads(chunk[len(MAGIC):])
        raw["secret"]="never"
        forged=MAGIC+json.dumps(raw,sort_keys=True,separators=(",",":")).encode()
        with self.assertRaises(ValueError):
            decode_fixture_chunk(forged,expected_identity=self.key)
    def test_no_duplicate_json_fields(self):
        raw=encode_fixture_chunk(self.key,self.store.read_bars(self.key)).replace(
            b'"fixture_only":true',b'"fixture_only":true,"fixture_only":false')
        with self.assertRaises(ValueError):
            decode_fixture_chunk(raw,expected_identity=self.key)
    def test_corrupt_bar_digest_denied(self):
        raw=encode_fixture_chunk(self.key,self.store.read_bars(self.key))
        raw=raw.replace(b'"close":"100"',b'"close":"100.5"',1)
        with self.assertRaises(ValueError):
            decode_fixture_chunk(raw,expected_identity=self.key)
    def test_corrupt_checkpoint_denied(self):
        raw=encode_fixture_chunk(self.key,self.store.read_bars(self.key))
        raw=raw.replace(b'"ema20":"100"',b'"ema20":"199"',1)
        with self.assertRaises(ValueError):
            decode_fixture_chunk(raw,expected_identity=self.key)
    def test_noncanonical_json_denied(self):
        raw=encode_fixture_chunk(self.key,self.store.read_bars(self.key))
        with self.assertRaises(ValueError):
            decode_fixture_chunk(MAGIC+json.dumps(json.loads(raw[len(MAGIC):])).encode(),
                                 expected_identity=self.key)
    def test_bytes_not_raw_price_marked_authorized(self):
        raw=encode_fixture_chunk(self.key,self.store.read_bars(self.key))
        self.assertTrue(raw.startswith(MAGIC))
        self.assertIn(b'"market_data_authorized":false',raw)

    def test_first_publish_and_load(self):
        self.assertEqual(self.stage(),PartitionWrite.CREATED)
        self.assertEqual(self.cloud.chunk_count,1)
        self.assertEqual(self.cloud.manifest_count,1)
        self.assertEqual(self.cloud.load(self.key,pinned_manifest_sha256=self.pin()),
                         self.store.read_bars(self.key))
    def test_manifest_is_metadata_only(self):
        self.stage()
        m=self.cloud._manifests[self.pin()]
        self.assertNotIn("TEST001",m)
        self.assertNotIn("close",m)
        self.assertNotIn("volume",m)
        self.assertIn('"drive_upload_performed":false',m)
    def test_repeat_publish_does_not_create_new_generation(self):
        self.stage()
        self.assertEqual(self.stage(head=self.pin()),PartitionWrite.REUSED)
        self.assertEqual((self.cloud.chunk_count,self.cloud.manifest_count),(1,1))
    def test_change_one_bar_creates_new_immutable_manifest(self):
        self.stage()
        prior=self.pin()
        self.apply(self.key,(bar(18,close=152,revision="r2"),),scope=18)
        self.assertEqual(self.stage(head=prior),PartitionWrite.UPDATED)
        self.assertNotEqual(self.pin(),prior)
        self.assertEqual((self.cloud.chunk_count,self.cloud.manifest_count),(2,2))
        m=FixturePartitionManifest.parse_json(self.cloud._manifests[self.pin()])
        self.assertEqual((m.generation,m.previous_manifest_sha256),(2,prior))
        self.assertEqual(self.cloud.load(self.key,pinned_manifest_sha256=self.pin()),
                         self.store.read_bars(self.key))
    def test_version_only_revision_new_chunk(self):
        self.stage()
        self.apply(self.key,(bar(19,revision="r2"),),scope=19)
        self.assertEqual(self.stage(head=self.pin()),PartitionWrite.UPDATED)
    def test_append_one_closed_bar_new_chunk(self):
        self.stage()
        self.apply(self.key,(bar(20),),scope=20)
        self.assertEqual(self.stage(head=self.pin()),PartitionWrite.UPDATED)
        self.assertEqual(len(self.cloud.load(self.key,pinned_manifest_sha256=self.pin())),21)
    def test_stale_expected_head_denied(self):
        self.stage()
        with self.assertRaises(ValueError):self.stage(head=None)
    def test_manifest_pin_required(self):
        self.stage()
        with self.assertRaises(ValueError):self.cloud.load(self.key,pinned_manifest_sha256="0"*64)
    def test_rollback_generation_floor_denied(self):
        self.stage()
        with self.assertRaises(ValueError):
            self.cloud.load(self.key,pinned_manifest_sha256=self.pin(),minimum_generation=2)
    def test_manifest_parse_canonical(self):
        self.stage()
        content=self.cloud._manifests[self.pin()]
        self.assertEqual(FixturePartitionManifest.parse_json(content).canonical_json(),content)
    def test_manifest_duplicate_key_denied(self):
        self.stage()
        s=self.cloud._manifests[self.pin()].replace('"generation":1','"generation":1,"generation":2')
        with self.assertRaises(ValueError):FixturePartitionManifest.parse_json(s)
    def test_manifest_no_true_drive_flag(self):
        self.stage()
        m=FixturePartitionManifest.parse_json(self.cloud._manifests[self.pin()])
        with self.assertRaises(ValueError):replace(m,drive_upload_performed=True)
    def test_manifest_no_true_rights(self):
        self.stage()
        m=FixturePartitionManifest.parse_json(self.cloud._manifests[self.pin()])
        with self.assertRaises(ValueError):replace(m,live_market_data_authorized=True)
    def test_corrupt_active_chunk_denied(self):
        self.stage()
        self.cloud.simulate_corrupt_chunk(self.key)
        with self.assertRaises(ValueError):
            self.cloud.load(self.key,pinned_manifest_sha256=self.pin())
    def test_missing_active_chunk_denied(self):
        self.stage()
        self.cloud.simulate_missing_chunk(self.key)
        with self.assertRaises(ValueError):
            self.cloud.load(self.key,pinned_manifest_sha256=self.pin())
    def test_forged_active_pointer_denied(self):
        self.stage()
        self.cloud.simulate_forged_head(self.key,"0"*64)
        with self.assertRaises(ValueError):
            self.cloud.load(self.key,pinned_manifest_sha256="0"*64)
    def test_corrupt_history_manifest_denied(self):
        self.stage()
        self.cloud._manifests[self.pin()]="{}"
        with self.assertRaises(ValueError):
            self.cloud.load(self.key,pinned_manifest_sha256=self.pin())
    def test_staged_crash_cannot_publish_active_pointer(self):
        with self.assertRaises(RuntimeError):
            self.stage(simulate_crash_after_chunk=True)
        self.assertIsNone(self.pin())
        self.assertEqual(self.cloud.chunk_count,1)
        self.assertEqual(self.cloud.manifest_count,0)
        self.assertEqual(self.stage(),PartitionWrite.CREATED)
    def test_repeated_noop_does_not_reuse_corrupt_active_chunk(self):
        self.stage()
        self.cloud.simulate_corrupt_chunk(self.key)
        with self.assertRaises(ValueError):
            self.stage(head=self.pin())
    def test_other_partition_unchanged_after_revision(self):
        other=identity("TEST002")
        self.apply(other,tuple(bar(i) for i in range(20)),at=20,full=True)
        self.stage()
        self.stage(other)
        other_sha=self.pin(other)
        self.apply(self.key,(bar(18,close=155,revision="r2"),),scope=18)
        self.stage(head=self.pin())
        self.assertEqual(self.pin(other),other_sha)
    def test_three_providers_separate_partitions(self):
        keys=[identity(provider=p) for p in Provider]
        for key in keys[1:]:self.apply(key,tuple(bar(i) for i in range(20)),at=20,full=True)
        result=self.cloud.sync_selected(self.store,tuple(keys),created_at_utc=NOW)
        self.assertEqual((result.created,result.updated,result.reused),(3,0,0))
        self.assertEqual(len({self.pin(k) for k in keys}),3)
    def test_restore_into_fresh_sqlite_without_source(self):
        self.stage()
        target=SyntheticIncrementalStore(self.path/"reopened.sqlite")
        target.initialize()
        self.assertEqual(self.cloud.restore_partition(target,self.key,pinned_manifest_sha256=self.pin()),20)
        self.assertEqual(target.read_bars(self.key),self.store.read_bars(self.key))
        self.assertEqual(target.read_checkpoints(self.key),self.store.read_checkpoints(self.key))
    def test_restore_existing_partition_denied(self):
        self.stage()
        with self.assertRaises(ValueError):
            self.cloud.restore_partition(self.store,self.key,pinned_manifest_sha256=self.pin())
    def test_restore_wrong_provider_pin_denied(self):
        self.stage()
        target=SyntheticIncrementalStore(self.path/"reopened.sqlite")
        target.initialize()
        with self.assertRaises(ValueError):
            self.cloud.restore_partition(target,identity(provider=Provider.VCBS),
                                         pinned_manifest_sha256=self.pin())
    def test_restore_without_pin_denied(self):
        self.stage()
        target=SyntheticIncrementalStore(self.path/"reopened.sqlite")
        target.initialize()
        with self.assertRaises(ValueError):
            self.cloud.restore_partition(target,self.key,pinned_manifest_sha256="1"*64)
    def test_resume_recheck_reuses_indicator_checkpoint(self):
        self.stage()
        target=SyntheticIncrementalStore(self.path/"reopened.sqlite")
        target.initialize()
        self.cloud.restore_partition(target,self.key,pinned_manifest_sha256=self.pin())
        update=target.apply_fixture_window(self.key,(bar(19),),
                   observed_at_utc=NOW,scope_start_utc=START+FIVE*19,
                   scope_end_utc=START+FIVE*20,complete_scope=False)
        self.assertEqual((update.unchanged,update.indicator_bars_recomputed),(1,0))
    def test_incremental_tail_after_restore(self):
        self.stage()
        target=SyntheticIncrementalStore(self.path/"reopened.sqlite")
        target.initialize()
        self.cloud.restore_partition(target,self.key,pinned_manifest_sha256=self.pin())
        update=target.apply_fixture_window(self.key,(bar(20),),
                   observed_at_utc=NOW,scope_start_utc=START+FIVE*20,
                   scope_end_utc=START+FIVE*21,complete_scope=False)
        self.assertEqual((update.inserted,update.indicator_bars_recomputed),(1,1))
        self.assertEqual(target.read_checkpoints(self.key),full_recompute(target.read_bars(self.key)))
    def test_sync_selected_duplicate_denied(self):
        with self.assertRaises(ValueError):
            self.cloud.sync_selected(self.store,(self.key,self.key),created_at_utc=NOW)
    def test_sync_selected_empty_denied(self):
        with self.assertRaises(ValueError):
            self.cloud.sync_selected(self.store,(),created_at_utc=NOW)
    def test_sync_selected_non_typed_denied(self):
        with self.assertRaises(TypeError):
            self.cloud.sync_selected(self.store,[self.key],created_at_utc=NOW)
    def test_empty_local_partition_skipped(self):
        result=self.cloud.sync_selected(self.store,(identity("UNKNOWN"),),created_at_utc=NOW)
        self.assertEqual((result.created,result.updated,result.reused),(0,0,0))
    def test_cannot_stage_future_source_clock(self):
        with self.assertRaises(ValueError):
            self.cloud.stage_and_publish(self.key,self.store.read_bars(self.key),
                expected_head_sha256=None,created_at_utc=START)
    def test_invalid_utc_clock_denied(self):
        with self.assertRaises(ValueError):
            self.cloud.stage_and_publish(self.key,self.store.read_bars(self.key),
                expected_head_sha256=None,created_at_utc=NOW.astimezone(timezone(timedelta(hours=7))))
    def test_no_real_api_or_live_claim(self):
        r=self.cloud.sync_selected(self.store,(self.key,),created_at_utc=NOW)
        self.assertEqual((r.source_api_calls,r.actual_drive_api_calls,r.live_cache_authorized),(0,0,False))
        with self.assertRaises(PermissionError):require_real_market_cache_transport()

    def test_mixed_5_20_1_20_scopes_and_one_dirty_partition(self):
        keys=tuple(identity("TEST%03d"%i) for i in range(20))
        for key in keys[1:]:self.apply(key,tuple(bar(i) for i in range(20)),at=20,full=True)
        p1=self.cloud.sync_selected(self.store,keys[:5],created_at_utc=NOW)
        first={key.fingerprint:self.pin(key) for key in keys[:5]}
        self.assertEqual((p1.created,p1.updated,p1.reused),(5,0,0))
        p2=self.cloud.sync_selected(self.store,keys,created_at_utc=NOW)
        self.assertEqual((p2.created,p2.updated,p2.reused),(15,0,5))
        self.assertEqual(first,{key.fingerprint:self.pin(key) for key in keys[:5]})
        p3=self.cloud.sync_selected(self.store,keys[2:3],created_at_utc=NOW)
        p4=self.cloud.sync_selected(self.store,keys,created_at_utc=NOW)
        self.assertEqual((p3.created,p3.updated,p3.reused),(0,0,1))
        self.assertEqual((p4.created,p4.updated,p4.reused),(0,0,20))
        self.assertEqual((self.cloud.chunk_count,self.cloud.manifest_count),(20,20))
        self.apply(keys[2],(bar(18,close=148,revision="r2"),),scope=18)
        p5=self.cloud.sync_selected(self.store,keys,created_at_utc=NOW)
        self.assertEqual((p5.created,p5.updated,p5.reused),(0,1,19))
        self.assertEqual((self.cloud.chunk_count,self.cloud.manifest_count),(21,21))
        target=SyntheticIncrementalStore(self.path/"restored.sqlite")
        target.initialize()
        for k in keys:
            self.cloud.restore_partition(target,k,pinned_manifest_sha256=self.pin(k))
            self.assertEqual(target.read_bars(k),self.store.read_bars(k))
        self.assertEqual(len({self.pin(k) for k in keys}),20)


if __name__=="__main__":
    unittest.main()
