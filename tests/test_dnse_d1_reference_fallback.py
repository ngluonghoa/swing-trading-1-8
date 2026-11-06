"""P0.15 synthetic SSI→DNSE daily-reference fallback tests, no trade authority."""
import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from swing_trading.dnse_d1_reference_fallback import (
    D1Provider, D1PriceUnit, D1ReadState, D1ComparisonState, D1SourceUnavailable,
    D1ProviderQuote, D1ReferenceRequest, DNSEHistorySnapshot,
    select_dnse_d1_from_history, route_d1_reference, compare_ssi_dnse_d1,
)
from swing_trading.market_data import Timeframe, PriceBasis


UTC = timezone.utc
NOW = datetime(2026, 11, 6, 10, 0, tzinfo=UTC)
DAY = date(2026, 10, 13)
LABEL = 1791856800  # 13 Oct 2026 02:00Z = 09:00 VN local, NOT D1 close.


def request(tf=Timeframe.D1, day=DAY, asof=NOW):
    return D1ReferenceRequest("SHS", "HNX", tf, day, asof)


def ssi(day=DAY, volume=5177600, price_basis=PriceBasis.ADJUSTED):
    return D1ProviderQuote(
        D1Provider.SSI, "SHS", "HNX", day,
        NOW-timedelta(minutes=5), "ssi-call-receipt-test", "marketdata_list_daily_stock_infor",
        D1PriceUnit.VND, price_basis,
        Decimal("11600"), Decimal("11900"), Decimal("11500"), Decimal("11700"),
        volume,
    )


def history(label=LABEL, volume=5177600):
    return DNSEHistorySnapshot(
        {"t": [label-86400, label, label+86400],
         "o": [11.5, 11.6, 11.7],
         "h": [12.0, 11.9, 12.1],
         "l": [11.1, 11.5, 11.6],
         "c": [11.6, 11.7, 12.0],
         "v": [4050300, volume, 10160800],
         "nextTime": 0},
        NOW-timedelta(minutes=2), "dnse-call-receipt-test",
    )


def route(ssi_callback=None, dnse_callback=None, req=None):
    return route_d1_reference(
        req or request(),
        ssi_callback or (lambda req: None),
        dnse_callback or (lambda req: history()),
    )


class DNSEFallbackTests(unittest.TestCase):
    def test_dnse_selected_only_if_ssi_missing(self):
        out=route()
        self.assertEqual(out.state,D1ReadState.FALLBACK_DNSE_REFERENCE_ONLY)
        self.assertEqual(out.source,D1Provider.DNSE)
        self.assertTrue(out.primary_attempted)
        self.assertTrue(out.fallback_attempted)
        self.assertEqual(out.reference_quote.vnd_prices(),
                         tuple(map(Decimal,("11600","11900","11500","11700"))))
        self.assertEqual(out.reference_quote.volume,5177600)
        self.assertEqual(out.reference_quote.price_basis,PriceBasis.UNKNOWN)
        self.assertEqual(out.reference_quote.session_label_utc,
                         datetime(2026,10,13,2,0,tzinfo=UTC))
        for key in ("data_certified","market_calendar_certified",
                    "source_rights_verified","first_known_for_history_verified",
                    "eligible_for_indicators","eligible_for_backtest","actionable"):
            self.assertFalse(getattr(out,key))

    def test_ssi_primary_is_not_replaced_or_silently_cross_mixed(self):
        called=[]
        def s(req):
            called.append("SSI")
            return ssi()
        def d(req):
            called.append("DNSE")
            return history()
        out=route(s,d)
        self.assertEqual(out.state,D1ReadState.PRIMARY_SSI_REFERENCE_ONLY)
        self.assertEqual(called,["SSI"])
        self.assertEqual(out.source,D1Provider.SSI)
        self.assertFalse(out.fallback_attempted)
        self.assertEqual(out.reference_quote.unit,D1PriceUnit.VND)

    def test_adapter_explicit_source_error_triggers_fallback(self):
        def fail(req):
            raise D1SourceUnavailable("upstream error")
        out=route(fail,lambda req: history())
        self.assertEqual(out.state,D1ReadState.FALLBACK_DNSE_REFERENCE_ONLY)

    def test_unknown_programming_error_not_masked_as_upstream(self):
        def fail(req):
            raise RuntimeError("bug: unexpected adapter exception")
        with self.assertRaises(RuntimeError):
            route(fail,lambda req: history())

    def test_never_invokes_sources_for_intraday(self):
        seen=[]
        def count(req):
            seen.append(req.timeframe)
            return None
        for tf in (Timeframe.M1,Timeframe.M5,Timeframe.M15,Timeframe.M30,Timeframe.H1):
            out=route(count,count,request(tf))
            self.assertEqual(out.state,D1ReadState.BLOCKED)
            self.assertEqual(out.reason,"NO_DNSE_INTRADAY_SUBSTITUTION")
        self.assertEqual(seen,[])

    def test_same_day_and_future_daily_block_even_after_vn_close(self):
        current=date(2026,11,6)
        out=route(req=request(day=current))
        self.assertEqual(out.state,D1ReadState.BLOCKED)
        self.assertEqual(out.reason,"SAME_DAY_D1_CLOSE_NOT_INDEPENDENTLY_KNOWN")
        self.assertFalse(out.primary_attempted)
        self.assertFalse(out.fallback_attempted)
        tomorrow=date(2026,11,7)
        self.assertEqual(route(req=request(day=tomorrow)).state,D1ReadState.BLOCKED)

    def test_ssi_timestamp_after_asof_blocks_not_calls_dnse(self):
        calls=[]
        q=replace(ssi(),observed_at_utc=NOW+timedelta(seconds=1))
        out=route(lambda req:q,lambda req:calls.append("dnse") or history())
        self.assertEqual(out.reason,"SSI_RECEIPT_NOT_KNOWN_AT_AUDIT_CLOCK")
        self.assertEqual(calls,[])

    def test_dnse_snapshot_after_asof_refused(self):
        out=route(dnse_callback=lambda req:replace(history(),
                                                   observed_at_utc=NOW+timedelta(seconds=1)))
        self.assertEqual(out.reason,"DNSE_SNAPSHOT_NOT_KNOWN_AT_AUDIT_CLOCK")

    def test_retroactive_historical_fetch_not_replayed_at_prior_clock(self):
        past=datetime(2026,10,20,10,0,tzinfo=UTC)
        out=route(req=request(asof=past))
        self.assertEqual(out.reason,"DNSE_SNAPSHOT_NOT_KNOWN_AT_AUDIT_CLOCK")
        self.assertFalse(out.eligible_for_backtest)

    def test_dnse_not_in_target_day_never_use_latest_instead(self):
        out=route(req=request(day=date(2026,10,12)))
        self.assertEqual(out.state,D1ReadState.FALLBACK_DNSE_REFERENCE_ONLY)
        absent=route(req=request(day=date(2026,10,1)))
        self.assertEqual(absent.reason,"DNSE_TARGET_D1_NOT_IN_SNAPSHOT")
        self.assertIsNone(absent.reference_quote)

    def test_both_providers_unavailable_or_empty(self):
        out=route(dnse_callback=lambda req:None)
        self.assertEqual(out.reason,"BOTH_D1_ENDPOINTS_EMPTY_OR_UNAVAILABLE")
        def fail(req):
            raise D1SourceUnavailable("No DNSE")
        out=route(dnse_callback=fail)
        self.assertEqual(out.state,D1ReadState.BLOCKED)

    def test_wrong_primary_symbol_date_exchange_does_not_fallback(self):
        for bad in (replace(ssi(),symbol="SSI"),
                    replace(ssi(),exchange="HOSE"),
                    replace(ssi(),session_date_local=date(2026,10,12))):
            with self.subTest(bad=bad):
                r=route(ssi_callback=lambda req:bad)
                self.assertEqual(r.reason,"SSI_IDENTITY_OR_DATE_MISMATCH")
                self.assertFalse(r.fallback_attempted)

    def test_wrong_source_or_invalid_adapter_response_blocks(self):
        out=route(ssi_callback=lambda req:"some response")
        self.assertEqual(out.reason,"INVALID_SSI_ADAPTER_TYPE")
        out=route(dnse_callback=lambda req:"some payload")
        self.assertEqual(out.reason,"INVALID_DNSE_ADAPTER_TYPE")
        with self.assertRaises(TypeError):
            route_d1_reference(request(),None,None)

    def test_parallel_arrays_are_mandatory(self):
        for field in ("t","o","h","l","c","v"):
            missing=history()
            d=dict(missing.data);d.pop(field)
            out=route(dnse_callback=lambda req:replace(missing,data=d))
            self.assertEqual(out.reason,"DNSE_D1_HISTORY_INVALID")
        h=history()
        d=dict(h.data);d["c"]=d["c"][:-1]
        self.assertEqual(route(dnse_callback=lambda req:replace(h,data=d)).reason,
                         "DNSE_D1_HISTORY_INVALID")

    def test_duplicate_out_of_order_timestamp_blocks(self):
        h=history()
        for t in ([LABEL-86400,LABEL,LABEL],
                  [LABEL,LABEL-86400,LABEL+86400]):
            d=dict(h.data);d["t"]=t
            with self.subTest(t=t):
                self.assertEqual(route(dnse_callback=lambda req:replace(h,data=d)).reason,
                                 "DNSE_D1_HISTORY_INVALID")

    def test_label_is_not_close_time_and_clock_must_match(self):
        h=history()
        d=dict(h.data);d["t"]=[x+3600 for x in d["t"]]
        out=route(dnse_callback=lambda req:replace(h,data=d))
        self.assertEqual(out.reason,"DNSE_D1_HISTORY_INVALID")

    def test_volume_bools_floats_and_negative_fail_closed(self):
        h=history()
        for bad in (True,False,123.5,-1,"1,000",None):
            with self.subTest(bad=bad):
                d=dict(h.data);v=list(d["v"]);v[1]=bad;d["v"]=v
                out=route(dnse_callback=lambda req:replace(h,data=d))
                self.assertEqual(out.reason,"DNSE_D1_HISTORY_INVALID")

    def test_price_nonfinite_nonpositive_or_invalid_ohlc_rejected(self):
        h=history()
        for field,value in (("o","NaN"),("c",0),("h",-1),("l","Infinity"),
                            ("h",1),("l",999)):
            d=dict(h.data);arr=list(d[field]);arr[1]=value;d[field]=arr
            with self.subTest(field=field,value=value):
                self.assertEqual(route(dnse_callback=lambda req:replace(h,data=d)).reason,
                                 "DNSE_D1_HISTORY_INVALID")

    def test_provider_price_unit_and_basis_cannot_be_forged(self):
        src=route().reference_quote
        with self.assertRaises(ValueError):
            replace(src,unit=D1PriceUnit.VND)
        with self.assertRaises(ValueError):
            replace(src,price_basis=PriceBasis.ADJUSTED)
        with self.assertRaises(ValueError):
            replace(ssi(),unit=D1PriceUnit.THOUSAND_VND)
        with self.assertRaises(ValueError):
            replace(src,session_label_utc=src.session_label_utc+timedelta(hours=1))

    def test_exact_volume_and_prices_still_unknown_basis(self):
        d=route().reference_quote
        audit=compare_ssi_dnse_d1(ssi(),d)
        self.assertEqual(audit.state,D1ComparisonState.VOLUME_EQUAL_PRICE_BASIS_UNVERIFIED)
        self.assertTrue(audit.volume_equal)
        self.assertTrue(audit.normalized_ohlc_equal)
        self.assertFalse(audit.price_basis_qualified)
        self.assertFalse(audit.source_independent)
        self.assertFalse(audit.data_certified)
        self.assertFalse(audit.actionable)

    def test_old_adjusted_prices_rounding_is_not_silent_parity(self):
        d=route().reference_quote
        s=replace(ssi(),close=Decimal("11700.30"),high=Decimal("11900.30"))
        audit=compare_ssi_dnse_d1(s,d)
        self.assertTrue(audit.volume_equal)
        self.assertFalse(audit.normalized_ohlc_equal)
        self.assertEqual(audit.state,D1ComparisonState.VOLUME_EQUAL_PRICE_BASIS_UNVERIFIED)

    def test_volume_disagreement_is_source_conflict(self):
        audit=compare_ssi_dnse_d1(ssi(volume=5177601),route().reference_quote)
        self.assertEqual(audit.state,D1ComparisonState.SOURCE_VOLUME_OR_PRICE_CONFLICT)
        self.assertFalse(audit.volume_equal)

    def test_cross_symbol_venue_date_identity_rejected(self):
        d=route().reference_quote
        for changed in (replace(ssi(),symbol="OTHER"),
                        replace(ssi(),exchange="UPCOM"),
                        replace(ssi(),session_date_local=date(2026,10,12))):
            audit=compare_ssi_dnse_d1(changed,d)
            self.assertEqual(audit.state,D1ComparisonState.BLOCKED)

    def test_inconsistent_raw_source_and_uncertified_flags(self):
        d=route().reference_quote
        with self.assertRaises(ValueError):
            replace(route(),eligible_for_indicators=True)
        with self.assertRaises(ValueError):
            replace(route(),eligible_for_backtest=True)
        with self.assertRaises(ValueError):
            replace(route(),actionable=True)
        with self.assertRaises(ValueError):
            replace(compare_ssi_dnse_d1(ssi(),d),data_certified=True)

    def test_date_and_clock_inputs_cannot_be_guessed(self):
        with self.assertRaises(TypeError):
            request(day="13/10/2026")
        with self.assertRaises(TypeError):
            request(tf="D1")
        with self.assertRaises(ValueError):
            request(asof=NOW.replace(tzinfo=None))


if __name__ == "__main__":
    unittest.main()
