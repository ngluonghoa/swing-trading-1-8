"""GĐ4/P0.22: offline MCP envelope conformance, WAL-only-source rejection."""
from dataclasses import FrozenInstanceError, replace
from datetime import date, timedelta
import json
import unittest

from swing_trading.reference_host_dryrun import (
    StaticMcpFixture, FixtureOnlyD1HostHarness,
)
from swing_trading.dnse_d1_reference_fallback import D1Provider, D1ReadState
from swing_trading.market_data import Timeframe
from test_dnse_d1_reference_fallback import request, NOW
from test_d1_mcp_transport_bridge import ssi_payload, dnse_payload


def fixture(provider, data):
    endpoint = ("marketdata_list_daily_stock_infor" if provider is D1Provider.SSI
                else "price_get_history")
    return StaticMcpFixture.from_payload(provider, endpoint, data)


class FixtureOnlyHostConformanceTests(unittest.TestCase):
    def setUp(self):
        self.ssi = fixture(D1Provider.SSI, ssi_payload())
        self.dnse = fixture(D1Provider.DNSE, dnse_payload())

    def harness(self, ssi=None, dnse=None, now=None):
        return FixtureOnlyD1HostHarness(
            ssi=self.ssi if ssi is None else ssi,
            dnse=self.dnse if dnse is None else dnse,
            clock_utc=NOW-timedelta(minutes=1) if now is None else now
        )

    def test_ssi_primary_invoked_once_without_dnse(self):
        got=self.harness().run_once(request())
        self.assertEqual(got.endpoint_order, ("SSI.marketdata_list_daily_stock_infor",))
        self.assertEqual(got.run.audit.state, D1ReadState.PRIMARY_SSI_REFERENCE_ONLY)
        self.assertEqual(got.run.audit.reference_quote.provider, D1Provider.SSI)
        self.assertTrue(got.fixture_only)
        self.assertFalse(got.live_mcp_deployed)
        self.assertFalse(got.production_authorized)
        self.assertFalse(got.data_rights_verified)
        self.assertFalse(got.actionable)
        self.assertFalse(got.run.actionable)

    def test_dnse_only_fallback_after_allowed_ssi_error(self):
        ssi=fixture(D1Provider.SSI,{
            "status":"error","error":"DOWNSTREAM_UNAVAILABLE",
        })
        out=self.harness(ssi=ssi).run_once(request())
        self.assertEqual(out.endpoint_order,(
            "SSI.marketdata_list_daily_stock_infor","DNSE.price_get_history",
        ))
        self.assertEqual(out.run.audit.state,D1ReadState.FALLBACK_DNSE_REFERENCE_ONLY)
        self.assertEqual(out.run.audit.reference_quote.provider,D1Provider.DNSE)
        self.assertFalse(out.run.historical_backtest_qualified)

    def test_missing_dnse_provision_does_not_silently_reuse_ssi(self):
        ssi=fixture(D1Provider.SSI,{
            "status":"error","error":"DOWNSTREAM_UNAVAILABLE",
        })
        session=FixtureOnlyD1HostHarness(
            ssi=ssi,dnse=None,clock_utc=NOW-timedelta(minutes=1)
        )
        with self.assertRaises(PermissionError):
            session.run_once(request())
        with self.assertRaises(PermissionError):
            session.run_once(request())

    def test_unapproved_ssi_error_does_not_trigger_fallback(self):
        ssi=fixture(D1Provider.SSI,{
            "status":"error","error":"PERMISSION_DENIED"
        })
        with self.assertRaises(ValueError):
            self.harness(ssi=ssi).run_once(request())

    def test_no_intraday_or_current_day_transport(self):
        for tf in (Timeframe.M1,Timeframe.M5,Timeframe.M15):
            got=self.harness().run_once(request(tf=tf))
            self.assertEqual(got.endpoint_order,())
            self.assertEqual(got.run.audit.reason,"NO_DNSE_INTRADAY_SUBSTITUTION")
        today=self.harness().run_once(request(day=date(2026,11,6)))
        self.assertEqual(today.endpoint_order,())
        self.assertEqual(today.run.audit.reason,
                         "SAME_DAY_D1_CLOSE_NOT_INDEPENDENTLY_KNOWN")

    def test_one_shot_and_fixture_immutability(self):
        session=self.harness()
        session.run_once(request())
        with self.assertRaises(PermissionError):
            session.run_once(request())
        with self.assertRaises(FrozenInstanceError):
            self.ssi.endpoint="something_else"

    def test_freeze_payload_no_aliasing_or_mutation(self):
        payload=ssi_payload()
        f=fixture(D1Provider.SSI,payload)
        payload["data"]["stocks"][0]["open"]="9999999"
        parsed=f.parsed()
        self.assertNotEqual(parsed["data"]["stocks"][0]["open"],"9999999")
        parsed["data"]["stocks"][0]["open"]="4321"
        self.assertNotEqual(f.parsed()["data"]["stocks"][0]["open"],"4321")

    def test_wrong_endpoint_provider_and_callable_rejected(self):
        with self.assertRaises(ValueError):
            StaticMcpFixture.from_payload(
                D1Provider.SSI,"price_get_history", ssi_payload())
        with self.assertRaises(TypeError):
            StaticMcpFixture.from_payload(
                D1Provider.SSI,"marketdata_list_daily_stock_infor", lambda: {})
        with self.assertRaises(TypeError):
            FixtureOnlyD1HostHarness(
                ssi=self.dnse,dnse=self.ssi,clock_utc=NOW
            )

    def test_credentials_rejected_recursively(self):
        for value in (
            {"Authorization":"secret"},
            {"nested":{"access-token":"top-secret"}},
            {"rows":[{"api_key":"not-allowed"}]},
            {"Cookie":"a=b"},
        ):
            with self.subTest(value=value),self.assertRaises(ValueError):
                fixture(D1Provider.SSI,value)

    def test_response_size_and_noncanonical_json_rejected(self):
        with self.assertRaises(ValueError):
            fixture(D1Provider.SSI, {"padding":"x"*(128*1024)})
        with self.assertRaises(ValueError):
            StaticMcpFixture(D1Provider.SSI,
                "marketdata_list_daily_stock_infor", '{"z":1, "a":2}')
        with self.assertRaises(ValueError):
            StaticMcpFixture(D1Provider.SSI,
                "marketdata_list_daily_stock_infor", "[]")

    def test_clock_outside_asof_blocks_not_promotes_quote(self):
        result=self.harness(now=NOW+timedelta(seconds=1)).run_once(request())
        self.assertEqual(result.run.audit.reason,
                         "SSI_RECEIPT_NOT_KNOWN_AT_AUDIT_CLOCK")
        self.assertFalse(result.run.actionable)

    def test_missing_or_malformed_data_cannot_create_reference(self):
        bad=fixture(D1Provider.SSI,{"status":"ok","data":None})
        with self.assertRaises(ValueError):
            self.harness(ssi=bad).run_once(request())
        with self.assertRaises(TypeError):
            self.harness().run_once({"symbol":"SHS"})

    def test_no_ambient_connector_or_storage_attributes(self):
        obj=self.harness()
        self.assertFalse(hasattr(obj,"api_key"))
        self.assertFalse(hasattr(obj,"mcp_client"))
        self.assertFalse(hasattr(obj,"database_path"))
        out=obj.run_once(request())
        self.assertFalse(hasattr(out,"persistent_database"))


if __name__=="__main__":
    unittest.main()
