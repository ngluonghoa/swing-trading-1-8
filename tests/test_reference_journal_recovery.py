"""GĐ4/P0.18: synthetic metadata-only backup, independent pinning and recovery."""
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest

from swing_trading.dnse_d1_reference_fallback import D1Provider
from swing_trading.reference_journal import ReferenceJournal, ReferenceJournalCorrupt, ZERO
from swing_trading.reference_journal_recovery import (
    JournalCheckpoint, create_candidate_journal_checkpoint,
    verify_journal_backup_against_pinned, restore_journal_from_pinned,
    verify_journal_history_prefix,
)
from swing_trading.evidence_checkpoint import file_sha256
from test_reference_journal import _approved
from test_d1_mcp_transport_bridge import bridge
from test_dnse_d1_reference_fallback import request, NOW


class JournalRecoveryFixtureTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.store = ReferenceJournal(self.root / "live.sqlite")
        self.store.initialize()
        self.req = request()

    def put(self, run_id, provider="SSI", retain=True):
        connector = (bridge() if provider == "SSI" else
                     bridge(ssi_response={
                         "status": "error", "error": "DOWNSTREAM_UNAVAILABLE"
                     }))
        result = connector[0].run(self.req)
        return self.store.append(
            run_id, self.req, result, expected_tip=self.store.verify()[1],
            retention=_approved() if retain else None
        )

    def backup(self, *, name="backup.sqlite", cp="cp-A", store="store-A"):
        return create_candidate_journal_checkpoint(
            self.store, self.root / name, cp, store, NOW
        )

    def pin(self, checkpoint):
        # Simulated independent custody: a serialized document passed back in.
        # This test does NOT attest to an actual external, trusted custodian.
        return JournalCheckpoint.parse_json(checkpoint.canonical_json())

    def test_empty_journal_checkpoint_roundtrip(self):
        cp = self.backup()
        self.assertEqual(cp.record_count, 0)
        self.assertEqual(cp.chain_tip_sha256, ZERO)
        self.assertEqual(cp.omitted_cache_rows, 0)
        self.assertEqual(cp.snapshot_kind, "METADATA_ONLY")
        self.assertEqual(
            verify_journal_backup_against_pinned(
                self.root / "backup.sqlite", self.pin(cp),
                expected_store_id="store-A"),
            (0, ZERO),
        )
        restored = restore_journal_from_pinned(
            self.root / "backup.sqlite", self.root / "restored.sqlite",
            self.pin(cp), expected_store_id="store-A"
        )
        self.assertEqual(restored.verify(), (0, ZERO))

    def test_two_providers_one_db_metadata_only_no_quote_bytes(self):
        self.put("ssi-01", "SSI")
        second = self.put("dnse-01", "DNSE")
        self.assertEqual(second[0], 2)
        cp = self.backup()
        self.assertEqual(cp.record_count, 2)
        self.assertEqual(cp.chain_tip_sha256, second[1])
        self.assertEqual(cp.omitted_cache_rows, 2)
        self.assertEqual(cp.backup_sha256,
                         file_sha256(self.root / "backup.sqlite"))
        with sqlite3.connect(self.root / "backup.sqlite") as c:
            self.assertEqual(
                c.execute("SELECT count(*) FROM cache").fetchone()[0], 0)
            rows = [json.loads(r[0]) for r in c.execute(
                "SELECT body FROM journal ORDER BY seq"
            )]
            self.assertEqual(
                [r["selected_provider"] for r in rows], ["SSI", "DNSE"])
            self.assertTrue(all(r["reference_only"] for r in rows))
            self.assertTrue(all("quote_digest" in r for r in rows))
        backup_bytes = (self.root / "backup.sqlite").read_bytes()
        self.assertNotIn(b"vnd_ohlc", backup_bytes)
        self.assertNotIn(b"5177600", backup_bytes)
        for suffix in ("-wal", "-shm", "-journal"):
            self.assertFalse(
                (self.root / ("backup.sqlite" + suffix)).exists())

    def test_restore_never_resurrects_licensed_quotes(self):
        self.put("ssi", "SSI")
        self.put("dnse", "DNSE")
        cp = self.pin(self.backup())
        restored = restore_journal_from_pinned(
            self.root / "backup.sqlite", self.root / "restored.sqlite",
            cp, expected_store_id="store-A"
        )
        self.assertEqual(restored.verify(),
                         (cp.record_count, cp.chain_tip_sha256))
        for run_id, provider in [("ssi", D1Provider.SSI), ("dnse", D1Provider.DNSE)]:
            self.assertIsNotNone(
                self.store.read_diagnostic(
                    run_id=run_id, provider=provider, as_of_utc=NOW))
            self.assertIsNone(
                restored.read_diagnostic(
                    run_id=run_id, provider=provider, as_of_utc=NOW))
        # A recovered metadata-only store can append a NEW authorized receipt
        # without changing its historical prefix, or referencing old quotes.
        value = restored.append(
            "after-restore", self.req, bridge()[0].run(self.req),
            expected_tip=cp.chain_tip_sha256
        )
        self.assertEqual(value[0], 3)
        self.assertEqual(verify_journal_history_prefix(
            restored, cp, expected_store_id="store-A"), value)

    def test_corrupted_backup_rejected_no_new_destination(self):
        self.put("r", "SSI")
        cp = self.pin(self.backup())
        snap = self.root / "backup.sqlite"
        with snap.open("r+b") as f:
            f.seek(17)
            b = f.read(1)
            f.seek(17)
            f.write(bytes([b[0] ^ 0xff]))
        with self.assertRaises(ReferenceJournalCorrupt):
            verify_journal_backup_against_pinned(
                snap, cp, expected_store_id="store-A")
        dst = self.root / "failed.sqlite"
        with self.assertRaises(ReferenceJournalCorrupt):
            restore_journal_from_pinned(
                snap, dst, cp, expected_store_id="store-A")
        self.assertFalse(dst.exists())

    def test_wrong_store_count_digest_or_tip_refused(self):
        self.put("r", retain=False)
        cp = self.pin(self.backup())
        path = self.root / "backup.sqlite"
        for altered in (
            replace(cp, backup_sha256="f" * 64),
            replace(cp, chain_tip_sha256="f" * 64),
            replace(cp, record_count=cp.record_count + 1),
        ):
            with self.subTest(altered=altered), self.assertRaises(ReferenceJournalCorrupt):
                verify_journal_backup_against_pinned(
                    path, altered, expected_store_id="store-A")
        with self.assertRaises(ReferenceJournalCorrupt):
            verify_journal_backup_against_pinned(
                path, cp, expected_store_id="wrong-store")

    def test_no_overwrite_on_backup_or_restore(self):
        self.put("r", retain=False)
        cp = self.pin(self.backup())
        with self.assertRaises(FileExistsError):
            self.backup()
        restored = restore_journal_from_pinned(
            self.root / "backup.sqlite", self.root / "restored.sqlite",
            cp, expected_store_id="store-A")
        with self.assertRaises(FileExistsError):
            restore_journal_from_pinned(
                self.root / "backup.sqlite", restored.path,
                cp, expected_store_id="store-A")
        self.assertEqual(restored.verify()[0], 1)

    def test_prefix_cannot_be_truncated_or_rewritten(self):
        self.put("r", retain=False)
        cp = self.pin(self.backup())
        second = self.put("r2", retain=False)
        self.assertEqual(verify_journal_history_prefix(
            self.store, cp, expected_store_id="store-A"), second)
        other = ReferenceJournal(self.root / "other.sqlite")
        other.initialize()
        with self.assertRaises(ReferenceJournalCorrupt):
            verify_journal_history_prefix(
                other, cp, expected_store_id="store-A")
        with self.assertRaises(ReferenceJournalCorrupt):
            verify_journal_history_prefix(
                self.store, replace(cp, chain_tip_sha256="f" * 64),
                expected_store_id="store-A")
        with self.assertRaises(ReferenceJournalCorrupt):
            verify_journal_history_prefix(
                self.store, cp, expected_store_id="other-store")

    def test_metadata_snapshot_with_cache_already_pruned(self):
        self.put("ssi", retain=True)
        self.store.prune_expired(now_utc=NOW + timedelta(days=3))
        cp = self.pin(self.backup())
        self.assertEqual(cp.omitted_cache_rows, 0)
        self.assertEqual(cp.record_count, 1)
        self.assertEqual(
            verify_journal_backup_against_pinned(
                self.root / "backup.sqlite", cp, expected_store_id="store-A"),
            self.store.verify()
        )

    def test_tampered_source_refused_before_export(self):
        self.put("r", retain=False)
        with sqlite3.connect(self.store.path) as c:
            c.execute("DROP TRIGGER journal_no_update")
        target = self.root / "failed.sqlite"
        with self.assertRaises(ReferenceJournalCorrupt):
            self.backup(name="failed.sqlite")
        self.assertFalse(target.exists())

    def test_checkpoint_schema_is_strict(self):
        self.put("r", retain=False)
        cp = self.pin(self.backup())
        with self.assertRaises(ValueError):
            replace(cp, created_at_utc=NOW.replace(tzinfo=None))
        for altered in (
            {"record_count": True},
            {"snapshot_kind": "RAW_QUOTE_BACKUP"},
            {"schema_version": 2},
            {"checkpoint_id": "../unsafe"},
            {"chain_tip_sha256": "INVALID"},
            {"omitted_cache_rows": -1},
        ):
            with self.subTest(altered=altered), self.assertRaises(ValueError):
                replace(cp, **altered)
        data = json.loads(cp.canonical_json())
        data["new_key"] = "silent-default"
        with self.assertRaises(ValueError):
            JournalCheckpoint.parse_json(json.dumps(data))
        del data["new_key"]
        del data["snapshot_kind"]
        with self.assertRaises(ValueError):
            JournalCheckpoint.parse_json(json.dumps(data))
        with self.assertRaises(TypeError):
            JournalCheckpoint.parse_json(None)
        with self.assertRaises(TypeError):
            verify_journal_backup_against_pinned(
                self.root / "backup.sqlite", {"not": "pinned"},
                expected_store_id="store-A")

    def test_expired_and_unexpired_quotes_never_appear_in_backup(self):
        self.put("old", retain=True)
        self.store.prune_expired(now_utc=NOW + timedelta(days=3))
        self.put("new", retain=True)
        cp = self.backup()
        self.assertEqual(cp.omitted_cache_rows, 1)
        binary = (self.root / "backup.sqlite").read_bytes()
        self.assertNotIn(b"vnd_ohlc", binary)
        self.assertEqual(cp.record_count, 2)


if __name__ == "__main__":
    unittest.main()
