"""GĐ4/P0.25 — synthetic native-bar product-vs-MCP & inert-query contracts."""
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta, timezone
import unittest

from swing_trading.dnse_d1_reference_fallback import D1Provider
from swing_trading.market_data import Timeframe
from swing_trading.native_minute_bar_source_plan import (
    BarProduct, BarProductDescription, NativeBarCandidate,
    ResolutionEvidence, SourceBarGateClosed, UnsentReadOnlyQuery,
    candidate_native_bar_sources, describe_bar_product,
    resolution_evidence, sketch_first_page_query,
)

DAY = date(2026, 10, 14)
START = datetime(2026, 10, 14, 2, 0, tzinfo=timezone.utc)
END = datetime(2026, 10, 14, 7, 45, tzinfo=timezone.utc)


class NativeMinuteBarSourcePlanTests(unittest.TestCase):
    def test_catalog_four_surfaces_and_connected_separate_from_external(self):
        products=tuple(describe_bar_product(p) for p in BarProduct)
        self.assertEqual(len(products), 4)
        self.assertEqual(sum(x.available_as_connected_mcp for x in products), 2)
        self.assertEqual(sum(x.documented_native_ohlc for x in products), 2)
        for x in products:
            self.assertFalse(x.authenticated_to_product)
            self.assertFalse(x.licensed_historical_retention)
            self.assertFalse(x.source_native_history_verified)

    def test_fastconnect_is_not_connected_ssi_mcp(self):
        s=describe_bar_product(BarProduct.SSI_FASTCONNECT_INTRADAY_OHLC)
        self.assertEqual(s.provider,D1Provider.SSI)
        self.assertEqual(s.endpoint,"Market/IntradayOhlc")
        self.assertFalse(s.available_as_connected_mcp)
        self.assertTrue(s.documented_native_ohlc)
        c=describe_bar_product(BarProduct.SSI_CONNECTED_INTRADAY_TICKS)
        self.assertTrue(c.available_as_connected_mcp)
        self.assertFalse(c.documented_native_ohlc)

    def test_dnse_openapi_is_not_connected_dnse_day_history(self):
        s=describe_bar_product(BarProduct.DNSE_OPENAPI_OHLC)
        c=describe_bar_product(BarProduct.DNSE_CONNECTED_DAY_ONLY)
        self.assertFalse(s.available_as_connected_mcp)
        self.assertTrue(s.documented_native_ohlc)
        self.assertTrue(c.available_as_connected_mcp)
        self.assertFalse(c.documented_native_ohlc)
        self.assertEqual(s.required_auth_fields,
                         ("X-API-Key","X-Aux-Date","X-Signature"))

    def test_connected_mcp_never_becomes_native_m1_m5_m15(self):
        for f in (Timeframe.M1, Timeframe.M5, Timeframe.M15):
            for p in (BarProduct.SSI_CONNECTED_INTRADAY_TICKS,
                      BarProduct.DNSE_CONNECTED_DAY_ONLY):
                with self.subTest(f=f,p=p):
                    self.assertEqual(resolution_evidence(p,f),
                                     ResolutionEvidence.NOT_NATIVE_MINUTE_BARS)
                    with self.assertRaises(SourceBarGateClosed):
                        sketch_first_page_query(p,f,symbol="SHS",session_day=DAY)

    def test_dnse_openapi_explicitly_lists_m1_m5_m15(self):
        for f in (Timeframe.M1,Timeframe.M5,Timeframe.M15):
            self.assertEqual(
                resolution_evidence(BarProduct.DNSE_OPENAPI_OHLC,f),
                ResolutionEvidence.EXPLICIT_TIMEFRAME_LISTED,
            )

    def test_ssi_only_default_1m_confirmed_by_public_parameter_text(self):
        self.assertEqual(
            resolution_evidence(BarProduct.SSI_FASTCONNECT_INTRADAY_OHLC,Timeframe.M1),
            ResolutionEvidence.DEFAULT_1M_DOCUMENTED_ONLY,
        )
        for f in (Timeframe.M5,Timeframe.M15):
            self.assertEqual(
                resolution_evidence(BarProduct.SSI_FASTCONNECT_INTRADAY_OHLC,f),
                ResolutionEvidence.INTEGER_PARAMETER_VALUE_NOT_ENUMERATED,
            )

    def test_candidate_matrix_has_no_ready_or_actionable_products(self):
        for f in (Timeframe.M1,Timeframe.M5,Timeframe.M15):
            candidates=candidate_native_bar_sources(f)
            self.assertEqual(len(candidates),4)
            self.assertEqual({x.product for x in candidates},set(BarProduct))
            for x in candidates:
                self.assertIsInstance(x,NativeBarCandidate)
                self.assertFalse(x.executable)
                self.assertFalse(x.entitled)
                self.assertFalse(x.usable_for_indicators)
                self.assertFalse(x.historical_backtest_qualified)
                self.assertFalse(x.actionable)
                self.assertIn("NO_PROVIDER_LICENSED_HISTORICAL_RETENTION_EVIDENCE",
                              x.unresolved)

    def test_documented_endpoint_does_not_remove_missing_mcp_gate(self):
        x=next(c for c in candidate_native_bar_sources(Timeframe.M1)
               if c.product is BarProduct.DNSE_OPENAPI_OHLC)
        self.assertEqual(x.resolution_evidence,
                         ResolutionEvidence.EXPLICIT_TIMEFRAME_LISTED)
        self.assertIn("NO_CONNECTED_NATIVE_MINUTE_BAR_ENDPOINT",x.unresolved)
        self.assertFalse(x.historical_backtest_qualified)

    def test_ssi_m1_first_page_sketch_uses_only_public_parameters(self):
        q=sketch_first_page_query(
            BarProduct.SSI_FASTCONNECT_INTRADAY_OHLC,Timeframe.M1,
            symbol="SHS",session_day=DAY,
        )
        self.assertIsInstance(q,UnsentReadOnlyQuery)
        p=dict(q.parameter_pairs)
        self.assertEqual(p["fromDate"],"14/10/2026")
        self.assertEqual(p["toDate"],"14/10/2026")
        self.assertEqual(p["pageIndex"],1)
        self.assertEqual(p["pageSize"],1000)
        self.assertEqual(p["resollution"],1)
        self.assertEqual(q.method_from_public_docs,
                         "GET_DOCUMENTED_METHOD_UNCONFIRMED")
        self.assertTrue(q.first_page_only)
        self.assertFalse(q.ready_to_send)
        self.assertFalse(q.connected)

    def test_ssi_m5_m15_not_guessed_from_unenumerated_integer(self):
        for f in (Timeframe.M5,Timeframe.M15):
            with self.assertRaises(SourceBarGateClosed):
                sketch_first_page_query(
                    BarProduct.SSI_FASTCONNECT_INTRADAY_OHLC,f,
                    symbol="SHS",session_day=DAY,
                )

    def test_ssi_date_based_sketch_refuses_unrequested_unix_windows(self):
        with self.assertRaises(ValueError):
            sketch_first_page_query(
                BarProduct.SSI_FASTCONNECT_INTRADAY_OHLC,Timeframe.M1,
                symbol="SHS",session_day=DAY,start_utc=START,end_utc=END
            )

    def test_dnse_m1_m5_m15_sketch_exact_resolution_and_utc_unix(self):
        for f,expected in ((Timeframe.M1,"1"),(Timeframe.M5,"5"),
                           (Timeframe.M15,"15")):
            with self.subTest(f=f):
                q=sketch_first_page_query(
                    BarProduct.DNSE_OPENAPI_OHLC,f,
                    symbol="SHS",session_day=DAY,
                    start_utc=START,end_utc=END
                )
                p=dict(q.parameter_pairs)
                self.assertEqual(p["symbol"],"SHS")
                self.assertEqual(p["type"],"STOCK")
                self.assertEqual(p["resolution"],expected)
                self.assertEqual(p["from"],int(START.timestamp()))
                self.assertEqual(p["to"],int(END.timestamp()))
                self.assertFalse(q.connected)
                self.assertFalse(q.retention_approved)
                self.assertFalse(q.actionable)

    def test_dnse_query_has_header_names_not_secret_values(self):
        q=sketch_first_page_query(
            BarProduct.DNSE_OPENAPI_OHLC,Timeframe.M5,
            symbol="SHS",session_day=DAY,start_utc=START,end_utc=END
        )
        self.assertEqual(q.required_auth_fields,
                         ("X-API-Key","X-Aux-Date","X-Signature"))
        data=repr(q)
        self.assertNotIn("Bearer ",data)
        self.assertNotIn("api_key_value",data)
        self.assertNotIn("secret_value",data)

    def test_dnse_needs_explicit_utc_range(self):
        for kw in (
            {"start_utc":START},
            {"end_utc":END},
            {},
        ):
            with self.subTest(kw=kw),self.assertRaises(ValueError):
                sketch_first_page_query(
                    BarProduct.DNSE_OPENAPI_OHLC,Timeframe.M1,
                    symbol="SHS",session_day=DAY,**kw
                )

    def test_dnse_refuses_naive_datetime_and_reverse_range(self):
        with self.assertRaises(ValueError):
            sketch_first_page_query(
                BarProduct.DNSE_OPENAPI_OHLC,Timeframe.M1,
                symbol="SHS",session_day=DAY,
                start_utc=START.replace(tzinfo=None),end_utc=END,
            )
        for s,e in ((END,START),(START,START)):
            with self.assertRaises(ValueError):
                sketch_first_page_query(
                    BarProduct.DNSE_OPENAPI_OHLC,Timeframe.M1,
                    symbol="SHS",session_day=DAY,start_utc=s,end_utc=e
                )

    def test_dnse_refuses_session_date_crossing(self):
        with self.assertRaises(ValueError):
            sketch_first_page_query(
                BarProduct.DNSE_OPENAPI_OHLC,Timeframe.M1,
                symbol="SHS",session_day=date(2026,10,13),
                start_utc=START,end_utc=END,
            )
        with self.assertRaises(ValueError):
            sketch_first_page_query(
                BarProduct.DNSE_OPENAPI_OHLC,Timeframe.M1,
                symbol="SHS",session_day=DAY,
                start_utc=START,
                end_utc=datetime(2026,10,14,17,0,tzinfo=timezone.utc),
            )

    def test_reject_d1_w1_and_untyped_timeframe(self):
        for bad in (Timeframe.D1,Timeframe.W1,"M1",None):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                candidate_native_bar_sources(bad)

    def test_reject_unsafe_symbol_and_implicit_session_time(self):
        for symbol in ("shs","SHS/../../TOKEN","SHS;BUY","", "SSI X"):
            with self.subTest(symbol=symbol),self.assertRaises(ValueError):
                sketch_first_page_query(
                    BarProduct.SSI_FASTCONNECT_INTRADAY_OHLC,Timeframe.M1,
                    symbol=symbol,session_day=DAY
                )
        with self.assertRaises(TypeError):
            sketch_first_page_query(
                BarProduct.SSI_FASTCONNECT_INTRADAY_OHLC,Timeframe.M1,
                symbol="SHS",session_day=START,
            )

    def test_invalid_product_is_not_a_generic_network_method(self):
        with self.assertRaises(TypeError):
            describe_bar_product("Market/IntradayOhlc")
        with self.assertRaises(TypeError):
            sketch_first_page_query(
                "DNSE_OPENAPI",Timeframe.M1,symbol="SHS",session_day=DAY,
                start_utc=START,end_utc=END
            )

    def test_no_approval_can_be_forged_with_dataclass_replace(self):
        c=candidate_native_bar_sources(Timeframe.M1)[2]
        q=sketch_first_page_query(
            BarProduct.SSI_FASTCONNECT_INTRADAY_OHLC,Timeframe.M1,
            symbol="SHS",session_day=DAY,
        )
        for obj,field in ((c,"entitled"),(c,"actionable"),
                          (q,"ready_to_send"),(q,"retention_approved")):
            with self.subTest(field=field),self.assertRaises(TypeError):
                replace(obj,**{field:True})
        with self.assertRaises(FrozenInstanceError):
            q.symbol="SCAM"


if __name__ == "__main__":
    unittest.main()
