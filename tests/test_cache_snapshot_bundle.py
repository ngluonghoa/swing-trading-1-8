"""C3A offline synthetic cache snapshot and restart/cold-warm parity tests."""
import json
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from swing_trading.incremental_cache import (
    CacheIdentity, FixtureBar, Provider, SyntheticIncrementalStore, full_recompute,
)
from swing_trading.cache_snapshot_bundle import (
    FixtureSnapshotManifest, create_fixture_snapshot, restore_fixture_snapshot,
    require_approved_cache_transport, verify_fixture_snapshot,
)

START = datetime(2026, 11, 9, 2, 0, tzinfo=timezone.utc)
STEP = timedelta(minutes=5)
NOW = START + STEP * 25

def identity(provider):
    return CacheIdentity(provider, "fixture.ohlc", "SYN_FPT", "HOSE", "M5",
                         "2026-11-09.CONTINUOUS", "RAW", "ADJ1", "CAL1",
                         "AG1", "EMA_ATR1")

def bar(i, close=None, revision="r1"):
    c = Decimal(100+i if close is None else close)
    return FixtureBar(START+STEP*i, START+STEP*(i+1),c-1,c+2,c-2,c,
                      123+i,revision,START+STEP*(i+1))

class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.src = self.root/"working.sqlite"
        self.snapshot = self.root/"snapshot-001.sqlite"
        self.manifest_path = self.root/"snapshot-001.manifest.json"
        self.target = self.root/"restored.sqlite"
        self.store = SyntheticIncrementalStore(self.src)
        self.store.initialize()
        for p in Provider:
            self.store.apply_fixture_window(
                identity(p), tuple(bar(i) for i in range(20)),
                observed_at_utc=START+STEP*20, scope_start_utc=START,
                scope_end_utc=START+STEP*20,
                complete_scope=True,full_session_reconciled=True)

    def make(self, **kw):
        kw0=dict(snapshot_id="fixture1",generation=1,
                 previous_manifest_sha256=None,created_at_utc=NOW)
        kw0.update(kw)
        return create_fixture_snapshot(self.store,self.snapshot,self.manifest_path,**kw0)

    def verify(self, m, **kw):
        return verify_fixture_snapshot(self.snapshot,self.manifest_path.read_text(),
                                       pinned_manifest_sha256=m.digest,**kw)

    def restore(self, m, **kw):
        return restore_fixture_snapshot(self.snapshot,self.target,
                    self.manifest_path.read_text(),pinned_manifest_sha256=m.digest,**kw)

    def test_creation_and_manifest_are_synthetic_only(self):
        m=self.make()
        self.assertEqual(m.row_counts[1],60)
        self.assertEqual(m.row_counts[2],60)
        self.assertFalse(m.live_market_data_authorized)
        self.assertFalse(m.drive_upload_performed)
        self.assertEqual(m.storage_class,"DRIVE_STAGING_SYNTHETIC_ONLY")
        self.assertEqual(self.verify(m),m)
    def test_three_providers_recover_independently(self):
        m=self.make()
        restored=self.restore(m)
        for provider in Provider:
            key=identity(provider)
            self.assertEqual(restored.read_bars(key), self.store.read_bars(key))
            self.assertEqual(restored.read_checkpoints(key),self.store.read_checkpoints(key))
            self.assertEqual(restored.read_checkpoints(key),full_recompute(restored.read_bars(key)))
    def test_warm_recheck_after_restore_no_recompute(self):
        m=self.make()
        restored=self.restore(m)
        update=restored.apply_fixture_window(identity(Provider.SSI),tuple(bar(i) for i in (18,19)),
                           observed_at_utc=NOW,scope_start_utc=START+STEP*18,
                           scope_end_utc=START+STEP*20,complete_scope=False)
        self.assertEqual(update.indicator_bars_recomputed,0)
        self.assertEqual(update.unchanged,2)
    def test_append_after_restore_only_tail_recompute(self):
        m=self.make()
        restored=self.restore(m)
        update=restored.apply_fixture_window(identity(Provider.SSI),(bar(20),),
                         observed_at_utc=NOW,scope_start_utc=START+STEP*20,
                         scope_end_utc=START+STEP*21,complete_scope=False)
        self.assertEqual(update.inserted,1)
        self.assertEqual(update.indicator_bars_recomputed,1)
        self.assertEqual(restored.read_checkpoints(identity(Provider.SSI)),
                         full_recompute(restored.read_bars(identity(Provider.SSI))))
    def test_revision_after_restore_isolated_by_provider(self):
        m=self.make()
        restored=self.restore(m)
        untouched=restored.read_checkpoints(identity(Provider.DNSE))
        update=restored.apply_fixture_window(identity(Provider.VCBS),(bar(18,close=190,revision="r2"),),
                         observed_at_utc=NOW,scope_start_utc=START+STEP*18,
                         scope_end_utc=START+STEP*19,complete_scope=False)
        self.assertEqual(update.revised,1)
        self.assertEqual(update.indicator_bars_recomputed,2)
        self.assertEqual(restored.read_checkpoints(identity(Provider.DNSE)),untouched)
    def test_backup_includes_wal_commits(self):
        with sqlite3.connect(self.src) as conn:
            mode=conn.execute("PRAGMA journal_mode").fetchone()[0]
        self.assertEqual(mode.lower(),"wal")
        m=self.make()
        self.assertEqual(self.restore(m).read_bars(identity(Provider.SSI)),self.store.read_bars(identity(Provider.SSI)))
    def test_never_overwrite_snapshot(self):
        self.make()
        with self.assertRaises(FileExistsError):self.make(snapshot_id="retry")
    def test_never_overwrite_manifest(self):
        self.manifest_path.write_text("occupied")
        with self.assertRaises(FileExistsError):self.make()
        self.assertFalse(self.snapshot.exists())
    def test_never_overwrite_restore(self):
        m=self.make()
        self.target.write_text("occupied")
        with self.assertRaises(FileExistsError):self.restore(m)
        self.assertEqual(self.target.read_text(),"occupied")
    def test_snapshot_and_manifest_paths_distinct(self):
        with self.assertRaises(ValueError):
            create_fixture_snapshot(self.store,self.snapshot,self.snapshot,
                 snapshot_id="id",generation=1,previous_manifest_sha256=None,created_at_utc=NOW)
    def test_reject_nonabsolute_target(self):
        with self.assertRaises(ValueError):
            create_fixture_snapshot(self.store,Path("relative.sqlite"),self.manifest_path,
                 snapshot_id="id",generation=1,previous_manifest_sha256=None,created_at_utc=NOW)
    def test_reject_symlink_target(self):
        link=self.root/"link"
        link.symlink_to(self.root/"outside")
        with self.assertRaises(ValueError):
            create_fixture_snapshot(self.store,link,self.manifest_path,
                snapshot_id="id",generation=1,previous_manifest_sha256=None,created_at_utc=NOW)
    def test_reject_git_work_tree(self):
        nested=self.root/"repo"
        nested.mkdir()
        (nested/".git").mkdir()
        with self.assertRaises(ValueError):
            create_fixture_snapshot(self.store,nested/"x.sqlite",self.manifest_path,
                snapshot_id="id",generation=1,previous_manifest_sha256=None,created_at_utc=NOW)
    def test_snapshot_checksum_catches_tampering(self):
        m=self.make()
        with self.snapshot.open("ab") as f:f.write(b"tamper")
        with self.assertRaises(ValueError):self.verify(m)
    def test_bad_manifest_digest(self):
        m=self.make()
        with self.assertRaises(ValueError):
            verify_fixture_snapshot(self.snapshot,self.manifest_path.read_text(),pinned_manifest_sha256="0"*64)
    def test_bad_pinned_digest_format(self):
        m=self.make()
        with self.assertRaises(ValueError):
            verify_fixture_snapshot(self.snapshot,self.manifest_path.read_text(),pinned_manifest_sha256="X")
    def test_manifest_canonical_round_trip(self):
        m=self.make()
        self.assertEqual(FixtureSnapshotManifest.parse_json(m.canonical_json()),m)
    def test_manifest_unknown_key(self):
        m=self.make()
        obj=json.loads(m.canonical_json())
        obj["market_authorized"]=True
        with self.assertRaises(ValueError):FixtureSnapshotManifest.parse_json(json.dumps(obj))
    def test_manifest_duplicate_json_key(self):
        m=self.make()
        payload=m.canonical_json().replace('"snapshot_id":"fixture1"', '"snapshot_id":"fixture1","snapshot_id":"fixture2"')
        with self.assertRaises(ValueError):FixtureSnapshotManifest.parse_json(payload)
    def test_manifest_noncanonical_rejected(self):
        m=self.make()
        with self.assertRaises(ValueError):FixtureSnapshotManifest.parse_json(json.dumps(json.loads(m.canonical_json())))
    def test_manifest_false_authority_cannot_be_asserted(self):
        m=self.make()
        with self.assertRaises(ValueError):replace(m,live_market_data_authorized=True)
        with self.assertRaises(ValueError):replace(m,drive_upload_performed=True)
    def test_unknown_schema_denied_before_publish(self):
        with sqlite3.connect(self.src) as c:
            c.execute("UPDATE config SET val='77' WHERE name='schema'")
        with self.assertRaises(ValueError):self.make()
        self.assertFalse(self.snapshot.exists())
    def test_unknown_table_denied(self):
        with sqlite3.connect(self.src) as c:c.execute("CREATE TABLE forbidden (a TEXT)")
        with self.assertRaises(ValueError):self.make()
    def test_broken_checkpoint_parity_denied(self):
        with sqlite3.connect(self.src) as c:
            c.execute("UPDATE fixture_checkpoints SET ema20='999999' WHERE cache_key=(SELECT MIN(cache_key) FROM fixture_checkpoints) AND start_utc=(SELECT MIN(start_utc) FROM fixture_checkpoints)")
        with self.assertRaises(ValueError):self.make()
    def test_broken_bar_digest_denied(self):
        with sqlite3.connect(self.src) as c:
            c.execute("UPDATE fixture_bars SET c='999999' WHERE cache_key=(SELECT MIN(cache_key) FROM fixture_bars) AND start_utc=(SELECT MIN(start_utc) FROM fixture_bars)")
        with self.assertRaises(RuntimeError):self.make()
    def test_no_snapshot_partial_output_after_bad_manifest_args(self):
        with self.assertRaises(ValueError):self.make(snapshot_id="invalid id")
        self.assertFalse(self.snapshot.exists())
        self.assertFalse(self.manifest_path.exists())
    def test_no_snapshot_from_untyped_store(self):
        with self.assertRaises(TypeError):
            create_fixture_snapshot(str(self.src),self.snapshot,self.manifest_path,
                snapshot_id="id",generation=1,previous_manifest_sha256=None,created_at_utc=NOW)
    def test_requires_utc_timestamp(self):
        with self.assertRaises(ValueError):self.make(created_at_utc=datetime(2026,11,9))
    def test_no_nonutc_offset(self):
        with self.assertRaises(ValueError):self.make(created_at_utc=NOW.astimezone(timezone(timedelta(hours=7))))
    def test_genesis_cannot_claim_parent(self):
        with self.assertRaises(ValueError):self.make(previous_manifest_sha256="0"*64)
    def test_followup_requires_parent(self):
        with self.assertRaises(ValueError):self.make(generation=2)
    def test_followup_chain_requires_previous_pin(self):
        parent=self.make()
        second=self.root/"snapshot-002.sqlite"
        receipt=self.root/"snapshot-002.manifest.json"
        nxt=create_fixture_snapshot(self.store,second,receipt,snapshot_id="fixture2",generation=2,
                    previous_manifest_sha256=parent.digest,created_at_utc=NOW+STEP)
        self.assertEqual(nxt.previous_manifest_sha256,parent.digest)
        verified=verify_fixture_snapshot(second,receipt.read_text(),
                  pinned_manifest_sha256=nxt.digest,expected_parent_sha256=parent.digest,
                  minimum_generation=2)
        self.assertEqual(verified,nxt)
        with self.assertRaises(ValueError):
            verify_fixture_snapshot(second,receipt.read_text(),
                  pinned_manifest_sha256=nxt.digest,expected_parent_sha256="0"*64)
    def test_relative_rollback_floor(self):
        m=self.make()
        with self.assertRaises(ValueError):self.verify(m,minimum_generation=2)
    def test_caller_replaces_both_pin_and_manifest_not_secure(self):
        m=self.make()
        self.assertFalse(m.live_market_data_authorized)
        # This synthetic self-consistency proof is not independent off-host custody.
        self.assertEqual(self.verify(m),m)
    def test_empty_cache_snapshot_supported(self):
        blank=self.root/"empty.sqlite"
        s=SyntheticIncrementalStore(blank)
        s.initialize()
        snap=self.root/"empty-snap.sqlite"
        receipt=self.root/"empty.manifest.json"
        m=create_fixture_snapshot(s,snap,receipt,snapshot_id="empty",generation=1,
                                  previous_manifest_sha256=None,created_at_utc=NOW)
        self.assertEqual(m.row_counts[1:4],(0,0,0))
    def test_restore_denies_stale_sidecar(self):
        m=self.make()
        Path(str(self.target)+"-wal").write_bytes(b"")
        with self.assertRaises(ValueError):self.restore(m)
    def test_restore_denies_corrupt_bytes_and_remains_absent(self):
        m=self.make()
        with self.snapshot.open("ab") as f:f.write(b"x")
        with self.assertRaises(ValueError):self.restore(m)
        self.assertFalse(self.target.exists())
    def test_no_market_authorization(self):
        with self.assertRaises(PermissionError):require_approved_cache_transport()
    def test_only_metadata_in_manifest(self):
        m=self.make()
        j=m.canonical_json()
        self.assertNotIn("SYN_FPT",j)
        self.assertNotIn("fixture.ohlc",j)
        self.assertNotIn("ohlcv",j.lower())
        self.assertNotIn("price",j.lower())
    def test_manifest_size_bound(self):
        m=self.make()
        with self.assertRaises(ValueError):FixtureSnapshotManifest.parse_json(m.canonical_json()+"x"*5000)
    def test_boolean_generation_rejected(self):
        with self.assertRaises(ValueError):self.make(generation=True)
    def test_row_counts_boolean_rejected(self):
        m=self.make()
        with self.assertRaises(ValueError):replace(m,row_counts=(True,0,0,0,0))
    def test_manifest_digest_is_sha256(self):
        m=self.make()
        self.assertEqual(len(m.digest),64)
    def test_restore_twice_refuses_overwrite(self):
        m=self.make()
        self.restore(m)
        with self.assertRaises(FileExistsError):self.restore(m)

if __name__ == "__main__":
    unittest.main()
