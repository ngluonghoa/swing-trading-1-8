"""GĐ4/P0.23: synthetic source metadata-only diagnostics and fail-closed gates."""
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
import unittest

from swing_trading.dnse_d1_reference_fallback import D1Provider
from swing_trading.source_capability_evidence import (
    ProbeEndpoint, ProbeState, SourceCapabilityObservation,
    BacktestEvidenceBlockers, summarize_source_capability, audit_backtest_evidence,
)
from test_d1_mcp_transport_bridge import ssi_payload, dnse_payload
from test_dnse_d1_reference_fallback import NOW


class SourceCapabilityTests(unittest.TestCase):
    def audit(self, endpoint, body, symbol="SHS"):
        return summarize_source_capability(
            endpoint, body, symbol=symbol, checked_at_utc=NOW
        )

    def test_ssi_daily_rows_are_counts_not_market_certification(self):
        p=self.audit(ProbeEndpoint.SSI_DAILY,ssi_payload())
        self.assertEqual(p.provider,D1Provider.SSI)
        self.assertEqual(p.observed_rows,2)
        self.assertEqual(p.state,ProbeState.RETURNED_ROWS)
        self.assertEqual(p.time_label_class,"DAY_ROW")
        self.assertTrue(p.reference_only)
        self.assertFalse(p.eligible_for_indicators)
        self.assertFalse(p.eligible_for_backtest)
        self.assertFalse(p.actionable)
        self.assertFalse(p.clock_independently_attested)

    def test_ssi_intraday_rows_cannot_imply_m1_completeness(self):
        payload={"status":"ok","data":{"ticks":[
            {"symbol":"SHS","trading_date":"13/10/2026 09:00:00",
             "open":"11600","close":"11700"},
            {"symbol":"SHS","trading_date":"13/10/2026 09:02:00",
             "open":"11700","close":"11800"},
        ]}}
        for endpoint in (ProbeEndpoint.SSI_INTRADAY,ProbeEndpoint.SSI_FULL_INTRADAY):
            with self.subTest(endpoint=endpoint):
                p=self.audit(endpoint,payload)
                self.assertEqual(p.observed_rows,2)
                self.assertEqual(p.time_label_class,"INTRADAY_TICK_UNQUALIFIED")
                self.assertFalse(p.continuous_m1_m5_m15_coverage_verified)
                self.assertFalse(p.full_source_pagination_verified)
                self.assertFalse(p.historical_first_known_verified)

    def test_ssi_unavailable_is_explicit_metadata_state(self):
        p=self.audit(ProbeEndpoint.SSI_FULL_INTRADAY,{
            "status":"error","data":None,
            "error":{"code":"DOWNSTREAM_UNAVAILABLE"}
        })
        self.assertEqual(p.state,ProbeState.DOWNSTREAM_UNAVAILABLE)
        self.assertEqual(p.observed_rows,0)
        self.assertFalse(p.eligible_for_backtest)

    def test_ssi_other_error_is_not_reclassified_as_source_unavailable(self):
        for error in ({"code":"PERMISSION_DENIED"},"RATE_LIMIT",None):
            with self.subTest(error=error):
                p=self.audit(ProbeEndpoint.SSI_FULL_INTRADAY,{
                    "status":"error","error":error
                })
                self.assertEqual(p.state,ProbeState.UNCLASSIFIED_ERROR)

    def test_dnse_day_parallel_arrays_qualify_only_day_label(self):
        p=self.audit(ProbeEndpoint.DNSE_DAY,dnse_payload())
        self.assertEqual(p.provider,D1Provider.DNSE)
        self.assertEqual(p.state,ProbeState.RETURNED_ROWS)
        self.assertEqual(p.observed_rows,3)
        self.assertEqual(p.time_label_class,"DAY_SESSION_LABEL")
        self.assertFalse(p.historical_first_known_verified)
        self.assertFalse(p.adjustment_basis_verified)

    def test_empty_rows_are_not_data_coverage(self):
        s=self.audit(ProbeEndpoint.SSI_DAILY,{
            "status":"ok","data":{"stocks":[]}
        })
        d=self.audit(ProbeEndpoint.DNSE_DAY,{
            "data":{"t":[],"o":[],"h":[],"l":[],"c":[],"v":[]}
        })
        self.assertEqual(s.state,ProbeState.RETURNED_EMPTY)
        self.assertEqual(d.state,ProbeState.RETURNED_EMPTY)
        self.assertEqual(s.observed_rows,0)
        self.assertEqual(d.observed_rows,0)

    def test_malformed_ssi_rows_do_not_qualify(self):
        for rows in (
            [{"symbol":"WRONG","trading_date":"13/10/2026"}],
            [{"symbol":"SHS"}],
            [42],
        ):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.audit(ProbeEndpoint.SSI_DAILY,{
                    "status":"ok","data":{"stocks":rows}
                })

    def test_dnse_unequal_arrays_fail(self):
        data=dnse_payload()
        data["data"]["v"].pop()
        with self.assertRaises(ValueError):
            self.audit(ProbeEndpoint.DNSE_DAY,data)

    def test_dnse_day_duplicate_or_invalid_clock_label_fail(self):
        data=dnse_payload()
        data["data"]["t"][1]=data["data"]["t"][0]
        with self.assertRaises(ValueError):
            self.audit(ProbeEndpoint.DNSE_DAY,data)
        data=dnse_payload()
        data["data"]["t"][1]+=3600
        with self.assertRaises(ValueError):
            self.audit(ProbeEndpoint.DNSE_DAY,data)

    def test_dnse_no_intraday_but_day_is_still_not_first_known(self):
        x=self.audit(ProbeEndpoint.DNSE_DAY,dnse_payload())
        self.assertFalse(x.continuous_m1_m5_m15_coverage_verified)
        self.assertFalse(x.historical_first_known_verified)
        self.assertFalse(x.source_rights_verified)

    def test_wrong_endpoints_or_payload_types_rejected(self):
        with self.assertRaises(TypeError):
            self.audit("price_get_history",dnse_payload())
        with self.assertRaises(TypeError):
            self.audit(ProbeEndpoint.SSI_DAILY,[])
        with self.assertRaises(TypeError):
            summarize_source_capability(
                ProbeEndpoint.SSI_DAILY,ssi_payload(),
                symbol="SHS",checked_at_utc=NOW.replace(tzinfo=None)
            )
        with self.assertRaises(ValueError):
            self.audit(ProbeEndpoint.SSI_DAILY,ssi_payload(),symbol="shs")

    def test_large_payload_exceeds_transient_bound(self):
        payload={"status":"ok","data":{"ticks":[]},"padding":"x"*(4*1024*1024)}
        with self.assertRaises(ValueError):
            self.audit(ProbeEndpoint.SSI_INTRADAY,payload)

    def test_no_raw_market_data_or_credentials_survive_summary(self):
        payload=ssi_payload()
        payload["credential"]={"api_key":"DO_NOT_SAVE"}
        row=payload["data"]["stocks"][0]
        row["close"]="999123"
        audit=self.audit(ProbeEndpoint.SSI_DAILY,payload)
        text=repr(audit)
        self.assertNotIn("999123",text)
        self.assertNotIn("DO_NOT_SAVE",text)
        self.assertFalse(hasattr(audit,"quotes"))
        self.assertFalse(hasattr(audit,"raw_response"))

    def test_flags_cannot_be_promoted_with_replace(self):
        x=self.audit(ProbeEndpoint.SSI_DAILY,ssi_payload())
        with self.assertRaises(ValueError):
            replace(x,reference_only=False)
        with self.assertRaises(TypeError):
            replace(x,source_rights_verified=True)
        with self.assertRaises(TypeError):
            replace(x,actionable=True)
        with self.assertRaises(ValueError):
            replace(x,observed_rows=0)
        with self.assertRaises(FrozenInstanceError):
            x.symbol="HACK"

    def test_cross_provider_identity_cannot_be_relabelled(self):
        x=self.audit(ProbeEndpoint.SSI_DAILY,ssi_payload())
        with self.assertRaises(TypeError):
            replace(x,provider=D1Provider.DNSE)
        with self.assertRaises(TypeError):
            replace(x,endpoint=ProbeEndpoint.DNSE_DAY)

    def test_merged_probe_matrix_lists_sources_but_never_approves_bt(self):
        s=self.audit(ProbeEndpoint.SSI_DAILY,ssi_payload())
        d=self.audit(ProbeEndpoint.DNSE_DAY,dnse_payload())
        failed=self.audit(ProbeEndpoint.SSI_FULL_INTRADAY,{
            "status":"error","error":{"code":"DOWNSTREAM_UNAVAILABLE"}
        })
        assessment=audit_backtest_evidence((s,d,failed))
        self.assertIsInstance(assessment,BacktestEvidenceBlockers)
        self.assertEqual(len(assessment.observed_source_endpoints),2)
        self.assertNotIn(
            "SSI.marketdata_list_stock_infor",assessment.observed_source_endpoints
        )
        self.assertFalse(assessment.ready_for_historical_backtest)
        self.assertFalse(assessment.actionable)
        self.assertIn(
            "PROVIDER_RETENTION_RIGHTS_NOT_INDEPENDENTLY_VERIFIED",
            assessment.unresolved
        )
        self.assertIn(
            "SOURCE_NATIVE_HISTORICAL_M1_M5_M15_COVERAGE_UNVERIFIED",
            assessment.unresolved
        )

    def test_matrix_does_not_claim_readiness_with_no_probes(self):
        a=audit_backtest_evidence(())
        self.assertEqual(a.observed_source_endpoints,())
        self.assertFalse(a.ready_for_historical_backtest)
        with self.assertRaises(TypeError):
            audit_backtest_evidence([self.audit(ProbeEndpoint.SSI_DAILY,ssi_payload())])


if __name__=="__main__":
    unittest.main()
