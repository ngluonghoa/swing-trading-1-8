"""P0.17 local-only, fully synthetic journal and explicit reference retention tests."""
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest

from swing_trading.d1_mcp_transport_bridge import BridgeRun, SourceFetchReceipt
from swing_trading.dnse_d1_reference_fallback import D1Provider, D1ReadState
from swing_trading.durable_evidence import ZERO as EXISTING_GENESIS
from swing_trading.market_data import PriceBasis
from swing_trading.reference_journal import (
    ZERO, DiagnosticReference, ReferenceJournal, ReferenceJournalCorrupt,
    ReferenceRetentionAuthorization,
)
from test_d1_mcp_transport_bridge import bridge, ssi_payload
from test_dnse_d1_reference_fallback import request, NOW


def _approved(expiry=None):
    return ReferenceRetentionAuthorization(
        "fixture-policy-1", expiry or NOW + timedelta(days=2),
        licensed_retention_approved=True, secured_storage_approved=True,
    )


class ReferenceJournalTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "references.sqlite"
        self.store = ReferenceJournal(self.path)
        self.store.initialize()
        self.req = request()
        self.good = bridge()[0].run(self.req)

    def test_genesis_is_independent_and_no_silent_initialization(self):
        self.assertEqual(ZERO, EXISTING_GENESIS)
        self.assertEqual(self.store.verify(), (0, ZERO))
        with self.assertRaises(FileExistsError):
            self.store.initialize()
        with self.assertRaises(FileNotFoundError):
            ReferenceJournal(self.path.with_name("absent.sqlite")).verify()

    def test_default_metadata_only_no_quote_persisted(self):
        count, tip = self.store.append("run001", self.req, self.good,
                                       expected_tip=ZERO)
        self.assertEqual(count, 1)
        self.assertNotEqual(tip, ZERO)
        self.assertEqual(self.store.verify(), (count, tip))
        self.assertIsNone(self.store.read_diagnostic(
            run_id="run001", provider=D1Provider.SSI, as_of_utc=NOW))
        with sqlite3.connect(self.path) as c:
            body = json.loads(c.execute("SELECT body FROM journal").fetchone()[0])
            self.assertEqual(body["selected_provider"], "SSI")
            self.assertEqual(body["receipts"][0]["provider"], "SSI")
            self.assertEqual(body["reference_only"], True)
            self.assertNotIn("vnd_ohlc", body)
            self.assertNotIn("quote_digest", body)
            self.assertEqual(c.execute("SELECT count(*) FROM cache").fetchone()[0], 0)

    def test_explicit_retention_reads_only_diagnostic_ssi(self):
        self.store.append("run002", self.req, self.good,
                          expected_tip=ZERO, retention=_approved())
        saved = self.store.read_diagnostic(
            run_id="run002", provider=D1Provider.SSI, as_of_utc=NOW)
        self.assertIsInstance(saved, DiagnosticReference)
        self.assertEqual(saved.provider, D1Provider.SSI)
        self.assertEqual(saved.vnd_ohlc[3], 11700)
        self.assertEqual(saved.volume, 5177600)
        self.assertIs(saved.price_basis, PriceBasis.UNKNOWN)
        self.assertFalse(saved.actionable)
        self.assertFalse(saved.eligible_for_backtest)
        self.assertFalse(saved.eligible_for_indicators)

    def test_fallback_dnse_provider_isolation_and_explicit_run_id(self):
        unavailable = {"status": "error", "error": "DOWNSTREAM_UNAVAILABLE"}
        fallback = bridge(ssi_response=unavailable)[0].run(self.req)
        self.assertEqual(fallback.audit.state, D1ReadState.FALLBACK_DNSE_REFERENCE_ONLY)
        self.store.append("fallback", self.req, fallback,
                          expected_tip=ZERO, retention=_approved())
        got = self.store.read_diagnostic(
            run_id="fallback", provider=D1Provider.DNSE, as_of_utc=NOW)
        self.assertEqual(tuple(got.vnd_ohlc), (11600, 11900, 11500, 11700))
        self.assertEqual(got.provider, D1Provider.DNSE)
        self.assertIsNone(self.store.read_diagnostic(
            run_id="fallback", provider=D1Provider.SSI, as_of_utc=NOW))
        with self.assertRaises(TypeError):
            self.store.read_diagnostic(run_id="fallback", provider="DNSE", as_of_utc=NOW)
        with sqlite3.connect(self.path) as c:
            self.assertEqual(c.execute("SELECT count(*) FROM cache").fetchone()[0], 1)

    def test_no_retrospective_asof_or_expired_reference(self):
        self.store.append("r", self.req, self.good,
                          expected_tip=ZERO, retention=_approved())
        self.assertIsNone(self.store.read_diagnostic(
            run_id="r", provider=D1Provider.SSI,
            as_of_utc=NOW - timedelta(minutes=2)))
        self.assertIsNone(self.store.read_diagnostic(
            run_id="r", provider=D1Provider.SSI,
            as_of_utc=NOW + timedelta(days=2)))
        self.assertIsNotNone(self.store.read_diagnostic(
            run_id="r", provider=D1Provider.SSI, as_of_utc=NOW))

    def test_prune_removes_quote_but_preserves_append_only_receipt(self):
        self.store.append("r", self.req, self.good,
                          expected_tip=ZERO, retention=_approved())
        prior = self.store.verify()
        self.assertEqual(self.store.prune_expired(
            now_utc=NOW + timedelta(days=2)), 1)
        self.assertEqual(self.store.prune_expired(
            now_utc=NOW + timedelta(days=2)), 0)
        self.assertEqual(self.store.verify(), prior)
        self.assertIsNone(self.store.read_diagnostic(
            run_id="r", provider=D1Provider.SSI, as_of_utc=NOW))
        with sqlite3.connect(self.path) as c:
            self.assertEqual(c.execute("SELECT count(*) FROM journal").fetchone()[0], 1)

    def test_licence_and_storage_controls_are_both_required(self):
        for licence, secure in [(False, True), (True, False), (False, False)]:
            with self.subTest(licence=licence, secure=secure):
                with self.assertRaises(PermissionError):
                    ReferenceRetentionAuthorization(
                        "policy", NOW + timedelta(days=1),
                        licensed_retention_approved=licence,
                        secured_storage_approved=secure)
        with self.assertRaises(TypeError):
            self.store.append("r", self.req, self.good,
                              expected_tip=ZERO, retention=True)
        self.assertEqual(self.store.verify(), (0, ZERO))

    def test_cache_ttl_requires_positive_bounded_limit(self):
        for expires in (NOW - timedelta(days=1),
                        NOW + timedelta(days=31),
                        NOW - timedelta(minutes=2)):
            with self.subTest(expires=expires):
                with self.assertRaises(ValueError):
                    self.store.append("r", self.req, self.good,
                        expected_tip=ZERO, retention=_approved(expires))
        self.assertEqual(self.store.verify(), (0, ZERO))

    def test_stale_head_and_repeated_run_id_fail_atomically(self):
        first = self.store.append("r1", self.req, self.good, expected_tip=ZERO)
        with self.assertRaises(ReferenceJournalCorrupt):
            self.store.append("r2", self.req, self.good, expected_tip=ZERO)
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.append("r1", self.req, self.good, expected_tip=first[1])
        self.assertEqual(self.store.verify(), first)
        self.assertEqual(self.store.append(
            "r2", self.req, self.good, expected_tip=first[1])[0], 2)

    def test_receipts_after_audit_cutoff_are_rejected(self):
        early_request = request()
        receipt = self.good.receipts[0]
        late = replace(receipt, retrieved_at_utc=NOW + timedelta(seconds=1))
        manipulated = replace(self.good, receipts=(late,))
        with self.assertRaises(ValueError):
            self.store.append("r", early_request, manipulated, expected_tip=ZERO)
        self.assertEqual(self.store.verify(), (0, ZERO))

    def test_reject_cross_symbol_or_malformed_receipt(self):
        wrong = replace(self.good.receipts[0], symbol="VGI")
        changed = replace(self.good, receipts=(wrong,))
        with self.assertRaises(ValueError):
            self.store.append("r", self.req, changed, expected_tip=ZERO)
        self.assertEqual(self.store.verify(), (0, ZERO))

    def test_blocked_request_is_metadata_only(self):
        r = request(day=date(2026, 11, 6))
        blocked = bridge()[0].run(r)
        self.assertEqual(blocked.audit.state, D1ReadState.BLOCKED)
        self.store.append("blocked", r, blocked, expected_tip=ZERO)
        self.assertEqual(self.store.verify()[0], 1)
        with self.assertRaises(ValueError):
            self.store.append("blocked-with-quote", r, blocked,
                              expected_tip=self.store.verify()[1], retention=_approved())

    def test_append_only_trigger_blocks_sqlite_rewrites(self):
        self.store.append("r", self.req, self.good, expected_tip=ZERO)
        with sqlite3.connect(self.path) as c:
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute("UPDATE journal SET body='{}' WHERE run_id='r'")
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute("DELETE FROM journal WHERE run_id='r'")
        self.assertEqual(self.store.verify()[0], 1)

    def test_missing_immutable_trigger_detected(self):
        self.store.append("r", self.req, self.good, expected_tip=ZERO)
        with sqlite3.connect(self.path) as c:
            c.execute("DROP TRIGGER journal_no_update")
        with self.assertRaises(ReferenceJournalCorrupt):
            self.store.verify()

    def test_corrupt_cache_is_detected_even_if_sqlite_integrity_ok(self):
        self.store.append("r", self.req, self.good,
                          expected_tip=ZERO, retention=_approved())
        with sqlite3.connect(self.path) as c:
            c.execute("UPDATE cache SET quote_json='{}' WHERE run_id='r'")
        with self.assertRaises(ReferenceJournalCorrupt):
            self.store.verify()

    def test_malformed_tip_and_run_id_refused(self):
        for tip in ("", "f" * 63, "F" * 64):
            with self.subTest(tip=tip), self.assertRaises(ValueError):
                self.store.append("r", self.req, self.good, expected_tip=tip)
        with self.assertRaises(ValueError):
            self.store.append("../escape", self.req, self.good, expected_tip=ZERO)
        self.assertEqual(self.store.verify(), (0, ZERO))


if __name__ == "__main__":
    unittest.main()
