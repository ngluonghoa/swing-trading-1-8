"""P0.16 end-to-end synthetic SSI/DNSE MCP envelope and cache-isolation tests."""
import json
import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

from swing_trading.d1_mcp_transport_bridge import (
    ReadOnlyMcpD1Bridge, ProviderSeparatedReferenceCache,
    ReceiptState, BridgeRun, SourceFetchReceipt,
)
from swing_trading.dnse_d1_reference_fallback import D1ReadState, D1Provider
from swing_trading.market_data import Timeframe, PriceBasis
from test_dnse_d1_reference_fallback import request, NOW, LABEL


def ssi_payload(date_text="13/10/2026", volume="5177600"):
    return {"status":"ok","error":None,"data":{"stocks":[
        {"symbol":"SHS","trading_date":date_text,
         "open":"11600","high":"11900","low":"11500","close":"11700",
         "total_match_volume":volume},
        {"symbol":"SHS","trading_date":"12/10/2026",
         "open":"11600","high":"12000","low":"11300","close":"11600",
         "total_match_volume":"4050300"},
    ]},"meta":{"asOfUtc":"2026-11-06T09:45:00Z"}}


def dnse_payload(volume=5177600):
    return {"data":{
        "t":[LABEL-86400,LABEL,LABEL+86400],
        "o":[11.5,11.6,11.7],"h":[12,11.9,12.1],
        "l":[11.3,11.5,11.6],"c":[11.6,11.7,12],
        "v":[4050300,volume,10160800],"nextTime":0,
    },"responseFormat":"COMPACT","disclaimer":"reference-only"}


def bridge(ssi_response=None,dnse_response=None,now=None,cache=None):
    calls=[]
    def ssi_call(args):
        calls.append(("SSI",args))
        return ssi_payload() if ssi_response is None else (
            ssi_response(args) if callable(ssi_response) else ssi_response
        )
    def dnse_call(args):
        calls.append(("DNSE",args))
        return dnse_payload() if dnse_response is None else (
            dnse_response(args) if callable(dnse_response) else dnse_response
        )
    return (ReadOnlyMcpD1Bridge(
        ssi_call,dnse_call,lambda: now or NOW-timedelta(minutes=1),
        cache or ProviderSeparatedReferenceCache(),
    ),calls)


class D1McpBridgeTests(unittest.TestCase):
    def test_primary_ssi_parses_actual_envelope_and_skips_dnse(self):
        b,calls=bridge()
        r=b.run(request())
        self.assertEqual([x[0] for x in calls],["SSI"])
        self.assertEqual(calls[0][1],{
            "symbol":"SHS","range":"1d","toDate":"13/10/2026",
            "pageSize":5,"pageIndex":1,
        })
        self.assertEqual(r.audit.state,D1ReadState.PRIMARY_SSI_REFERENCE_ONLY)
        self.assertEqual(r.audit.reference_quote.vnd_prices()[3],11700)
        self.assertEqual(r.audit.reference_quote.price_basis,PriceBasis.UNKNOWN)
        self.assertEqual(r.audit.reference_quote.volume,5177600)
        self.assertEqual(r.receipts[0].state,ReceiptState.FETCHED)
        self.assertEqual(len(r.receipts[0].raw_payload_digest_sha256),64)
        self.assertFalse(r.actionable)
        self.assertFalse(r.historical_backtest_qualified)

    def test_explicit_ssi_downstream_error_triggers_dnse_and_tracks_both(self):
        payload={"status":"error","data":None,"error":{"code":"DOWNSTREAM_UNAVAILABLE"}}
        b,calls=bridge(ssi_response=payload)
        r=b.run(request())
        self.assertEqual([c[0] for c in calls],["SSI","DNSE"])
        self.assertEqual(calls[1][1],{"symbol":"SHS"})
        self.assertEqual(r.audit.state,D1ReadState.FALLBACK_DNSE_REFERENCE_ONLY)
        self.assertEqual(tuple(x.provider for x in r.receipts),
                         (D1Provider.SSI,D1Provider.DNSE))
        self.assertEqual(r.receipts[0].state,ReceiptState.UNAVAILABLE)
        self.assertEqual(r.receipts[1].state,ReceiptState.FETCHED)
        self.assertEqual(r.audit.reference_quote.vnd_prices(),
                         tuple(map(int,("11600","11900","11500","11700"))))
        self.assertEqual(r.audit.reference_quote.volume,5177600)
        self.assertFalse(r.audit.eligible_for_indicators)
        self.assertFalse(r.audit.eligible_for_backtest)

    def test_missing_exact_day_triggers_dnse_not_adjacent_ssi_day(self):
        p=ssi_payload()
        p["data"]["stocks"]=p["data"]["stocks"][1:]
        b,calls=bridge(ssi_response=p)
        r=b.run(request())
        self.assertEqual(r.audit.state,D1ReadState.FALLBACK_DNSE_REFERENCE_ONLY)
        self.assertEqual(r.receipts[0].state,ReceiptState.TARGET_DATE_ABSENT)

    def test_unrecognized_ssi_error_fails_closed_not_dnse(self):
        for error in ({"code":"PERMISSION_DENIED"},"RATE_LIMIT",
                      {"code":"INVALID_REQUEST"},None):
            p={"status":"error","data":None,"error":error}
            b,calls=bridge(ssi_response=p)
            with self.subTest(error=error),self.assertRaises(ValueError):
                b.run(request())
            self.assertEqual([c[0] for c in calls],["SSI"])

    def test_invalid_ssi_quote_blocks_without_using_dnse(self):
        for bad in ("wrong_symbol","missing_daily_volume","non_numeric_price",
                    "duplicate_date","wrong_data_shape"):
            p=ssi_payload()
            if bad=="wrong_symbol":
                p["data"]["stocks"][0]["symbol"]="SSI"
            elif bad=="missing_daily_volume":
                p["data"]["stocks"][0].pop("total_match_volume")
            elif bad=="non_numeric_price":
                p["data"]["stocks"][0]["close"]="NaN"
            elif bad=="duplicate_date":
                p["data"]["stocks"].append(dict(p["data"]["stocks"][0]))
            else:
                p["data"]=None
            b,calls=bridge(ssi_response=p)
            with self.subTest(case=bad),self.assertRaises(ValueError):
                b.run(request())
            self.assertEqual(len(calls),1)
            self.assertEqual(calls[0][0],"SSI")

    def test_no_provider_access_for_intraday_or_same_day(self):
        b,calls=bridge()
        for tf in (Timeframe.M1,Timeframe.M5,Timeframe.M15,Timeframe.H1,Timeframe.W1):
            self.assertEqual(b.run(request(tf=tf)).audit.reason,
                             "NO_DNSE_INTRADAY_SUBSTITUTION")
        self.assertEqual(b.run(request(day=date(2026,11,6))).audit.reason,
                         "SAME_DAY_D1_CLOSE_NOT_INDEPENDENTLY_KNOWN")
        self.assertEqual(calls,[])

    def test_dnse_payload_json_string_is_accepted(self):
        p={"status":"error","error":"DOWNSTREAM_UNAVAILABLE"}
        b,calls=bridge(ssi_response=json.dumps(p),
                       dnse_response=json.dumps(dnse_payload()))
        r=b.run(request())
        self.assertEqual(r.audit.state,D1ReadState.FALLBACK_DNSE_REFERENCE_ONLY)

    def test_malformed_dnse_is_blocked_with_reason_without_approving(self):
        for corrupt in ("bad_t","bad_ohlc","bad_data","wrong_unit","duplicate_t"):
            p=dnse_payload()
            if corrupt=="bad_t":
                p["data"]["t"][1]+=3600
            elif corrupt=="bad_ohlc":
                p["data"]["h"][1]=-1
            elif corrupt=="bad_data":
                p["data"]=None
            elif corrupt=="wrong_unit":
                p["data"]["v"][1]="5,177,600"
            else:
                p["data"]["t"][1]=p["data"]["t"][0]
            b,calls=bridge(ssi_response={"status":"error","error":"DOWNSTREAM_UNAVAILABLE"},
                           dnse_response=p)
            if corrupt=="bad_data":
                with self.subTest(case=corrupt),self.assertRaises(ValueError):
                    b.run(request())
            else:
                with self.subTest(case=corrupt):
                    r=b.run(request())
                    self.assertEqual(r.audit.state,D1ReadState.BLOCKED)
                    self.assertEqual(r.audit.reason,"DNSE_D1_HISTORY_INVALID")
                    self.assertEqual(b.cache.count(D1Provider.DNSE),0)

    def test_target_day_absent_in_dnse_is_blocked(self):
        p=dnse_payload()
        p["data"]["t"]=[x+86400*30 for x in p["data"]["t"]]
        b,calls=bridge(ssi_response={"status":"error","error":"DOWNSTREAM_UNAVAILABLE"},
                       dnse_response=p)
        r=b.run(request())
        self.assertEqual(r.audit.reason,"DNSE_TARGET_D1_NOT_IN_SNAPSHOT")
        self.assertEqual(b.cache.count(D1Provider.DNSE),0)

    def test_retrospective_replay_does_not_treat_today_ingestion_as_past(self):
        b,calls=bridge(ssi_response={"status":"error","error":"DOWNSTREAM_UNAVAILABLE"})
        old=request(asof=datetime(2026,10,14,9,0,tzinfo=timezone.utc))
        r=b.run(old)
        self.assertEqual(r.audit.reason,"DNSE_SNAPSHOT_NOT_KNOWN_AT_AUDIT_CLOCK")
        self.assertEqual(b.cache.count(D1Provider.DNSE),0)

    def test_clock_after_audit_prevents_primary_and_no_dnse(self):
        b,calls=bridge(now=NOW+timedelta(minutes=2))
        r=b.run(request())
        self.assertEqual(r.audit.reason,"SSI_RECEIPT_NOT_KNOWN_AT_AUDIT_CLOCK")
        self.assertEqual([c[0] for c in calls],["SSI"])

    def test_clock_must_be_utc(self):
        b,calls=bridge(now=NOW.replace(tzinfo=None))
        with self.assertRaises(ValueError):
            b.run(request())

    def test_cache_segregates_providers_and_is_not_live_source(self):
        shared=ProviderSeparatedReferenceCache()
        b1,_=bridge(cache=shared)
        a=b1.run(request())
        b2,_=bridge(ssi_response={"status":"error","error":"DOWNSTREAM_UNAVAILABLE"},
                    cache=shared)
        b=b2.run(request())
        self.assertEqual(shared.count(D1Provider.SSI),1)
        self.assertEqual(shared.count(D1Provider.DNSE),1)
        s=a.audit.reference_quote
        d=b.audit.reference_quote
        self.assertEqual(s.symbol,d.symbol)
        self.assertNotEqual(s.provider,d.provider)
        self.assertIsNone(shared.get(D1Provider.DNSE,s.symbol,s.exchange,
                                     s.session_date_local,s.source_snapshot_id))
        self.assertIsNone(shared.get(D1Provider.SSI,d.symbol,d.exchange,
                                     d.session_date_local,d.source_snapshot_id))
        self.assertIs(shared.get(D1Provider.SSI,s.symbol,s.exchange,
                                 s.session_date_local,s.source_snapshot_id),s)
        self.assertIs(shared.get(D1Provider.DNSE,d.symbol,d.exchange,
                                 d.session_date_local,d.source_snapshot_id),d)
        with self.assertRaises(TypeError):
            shared.get("SSI","SHS","HNX",s.session_date_local,s.source_snapshot_id)

    def test_no_cache_population_when_no_source_available(self):
        cache=ProviderSeparatedReferenceCache()
        b,c=bridge(ssi_response={"status":"error","error":"DOWNSTREAM_UNAVAILABLE"},
                   dnse_response={"data":{}},cache=cache)
        out=b.run(request())
        self.assertEqual(out.audit.state,D1ReadState.BLOCKED)
        self.assertEqual(cache.count(D1Provider.SSI),0)
        self.assertEqual(cache.count(D1Provider.DNSE),0)

    def test_digest_is_stable_and_payload_not_copied_into_audit(self):
        b,_=bridge()
        a=b.run(request());c=b.run(request())
        self.assertEqual(a.receipts[0].raw_payload_digest_sha256,
                         c.receipts[0].raw_payload_digest_sha256)
        self.assertFalse(hasattr(a.receipts[0],"raw_payload"))
        self.assertFalse(hasattr(a.receipts[0],"api_key"))
        self.assertEqual(a.receipts[0].endpoint,"marketdata_list_daily_stock_infor")

    def test_digest_changes_with_provider_revision(self):
        b1,_=bridge()
        b2,_=bridge(ssi_response=ssi_payload(volume="5177601"))
        x=b1.run(request()).receipts[0].raw_payload_digest_sha256
        y=b2.run(request()).receipts[0].raw_payload_digest_sha256
        self.assertNotEqual(x,y)

    def test_no_forged_production_or_trading_flags(self):
        x=bridge()[0].run(request())
        for field in ("live_adapter_deployed","actionable","historical_backtest_qualified"):
            with self.subTest(field=field),self.assertRaises(ValueError):
                replace(x,**{field:True})
        with self.assertRaises(ValueError):
            replace(x,reference_only=False)

    def test_reject_wrong_provider_receipt_and_bad_digest(self):
        x=bridge()[0].run(request()).receipts[0]
        with self.assertRaises(TypeError):
            replace(x,provider="SSI")
        with self.assertRaises(ValueError):
            replace(x,raw_payload_digest_sha256="NOT_A_SHA")
        with self.assertRaises(ValueError):
            BridgeRun(bridge()[0].run(request()).audit,("untyped",))

    def test_other_provider_cache_has_no_fallback_without_transport(self):
        cache=ProviderSeparatedReferenceCache()
        bridge(ssi_response={"status":"error","error":"DOWNSTREAM_UNAVAILABLE"},
               cache=cache)[0].run(request())
        b,calls=bridge(ssi_response={"status":"error","error":"DOWNSTREAM_UNAVAILABLE"},
                       dnse_response={"data":{"t":[],"o":[],"h":[],"l":[],"c":[],"v":[]}},
                       cache=cache)
        out=b.run(request())
        self.assertEqual(out.audit.state,D1ReadState.BLOCKED)
        self.assertEqual(out.audit.reason,"DNSE_D1_HISTORY_INVALID")
        self.assertEqual([x[0] for x in calls],["SSI","DNSE"])


if __name__=="__main__":
    unittest.main()
