"""Synthetic C2B test suite. No vendor rows, credentials, real price history or network."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import unittest

from swing_trading.incremental_cache import Provider
from swing_trading.c2_source_capability_audit import ConnectedEndpoint, DataNeed
from swing_trading.c2_fair_source_benchmark import (
    D1Target, CallerReportedProbe, EvidenceOrigin, PriceBasis, VolumeBasis,
    ComparisonStatus, ComparisonAxis, TransientD1Row,
    summarize_endpoint_probes, compare_transient_d1_pair,
    require_benchmark_source_authority,
)

T=datetime(2026,11,7,8,0,tzinfo=timezone.utc)
TARGET=D1Target("FPT","HOSE",date(2026,11,5),date(2026,11,6))
EP={Provider.SSI:ConnectedEndpoint.SSI_D1_DETAILED,
    Provider.DNSE:ConnectedEndpoint.DNSE_D1_HISTORY,
    Provider.VCBS:ConnectedEndpoint.VCBS_D1_WINDOW}

def probe(provider=Provider.SSI, ms=250, success=True, rows=2, common=2,
          scope="range=1d,toDate=06/11/2026", **kwargs):
    defaults=dict(provider=provider,endpoint=EP[provider],task=DataNeed.D1_OHLCV,
                  origin=EvidenceOrigin.SYNTHETIC,target=TARGET,observed_at_utc=T,
                  elapsed_ms=ms,success=success,returned_rows=rows,
                  common_target_rows=common,approximate_json_bytes=250,requested_scope=scope)
    defaults.update(kwargs)
    return CallerReportedProbe(**defaults)

def row(provider=Provider.SSI,session=date(2026,11,6),basis=PriceBasis.RAW,
        vol_basis=VolumeBasis.MATCHED,**kwargs):
    defaults=dict(provider=provider,target=TARGET,session=session,price_basis=basis,
                  volume_basis=vol_basis,o_vnd=Decimal('10000'),h_vnd=Decimal('10500'),
                  l_vnd=Decimal('9900'),c_vnd=Decimal('10100'),volume_shares=10000)
    defaults.update(kwargs)
    return TransientD1Row(**defaults)

class TestTargets(unittest.TestCase):
    def test_valid(self):self.assertEqual(TARGET.exchange,"HOSE")
    def test_lower_ticker(self):
        with self.assertRaises(ValueError):D1Target("fpt","HOSE",TARGET.first_session,TARGET.last_session)
    def test_venue(self):
        with self.assertRaises(ValueError):D1Target("FPT","NYSE",TARGET.first_session,TARGET.last_session)
    def test_order(self):
        with self.assertRaises(ValueError):D1Target("FPT","HOSE",TARGET.last_session,TARGET.first_session)
    def test_horizon(self):
        with self.assertRaises(ValueError):D1Target("FPT","HOSE",date(2025,1,1),date(2026,11,6))
    def test_datetime_not_date(self):
        with self.assertRaises(ValueError):D1Target("FPT","HOSE",T,T)

class TestProbes(unittest.TestCase):
    def test_valid_all_three(self):
        for p in Provider:self.assertEqual(probe(p).provider,p)
    def test_wrong_endpoint(self):
        with self.assertRaises(ValueError):probe(Provider.SSI,endpoint=EP[Provider.DNSE])
    def test_wrong_task(self):
        with self.assertRaises(ValueError):probe(task=DataNeed.MINUTE_OHLCV)
    def test_no_vcbs_minute(self):
        with self.assertRaises(ValueError):probe(Provider.VCBS,task=DataNeed.MINUTE_OHLCV,endpoint=ConnectedEndpoint.VCBS_INTRADAY_PRICE_POINTS)
    def test_ssi_minute(self):
        a=probe(task=DataNeed.MINUTE_OHLCV,endpoint=ConnectedEndpoint.SSI_INTRADAY_SESSION)
        self.assertEqual(a.task,DataNeed.MINUTE_OHLCV)
    def test_latest_not_minute(self):
        with self.assertRaises(ValueError):probe(task=DataNeed.MINUTE_OHLCV,endpoint=ConnectedEndpoint.SSI_INTRADAY_LATEST)
    def test_empty_success(self):
        with self.assertRaises(ValueError):probe(rows=0,common=0)
    def test_failure_zero_rows(self):self.assertFalse(probe(success=False,rows=0,common=0).success)
    def test_negative_elapsed(self):
        with self.assertRaises(ValueError):probe(ms=-1)
    def test_zero_elapsed(self):
        with self.assertRaises(ValueError):probe(ms=0)
    def test_bool_elapsed(self):
        with self.assertRaises(ValueError):probe(ms=True)
    def test_bad_row_count(self):
        with self.assertRaises(ValueError):probe(rows=1,common=2)
    def test_bad_bytes(self):
        with self.assertRaises(ValueError):probe(approximate_json_bytes=-1)
    def test_claimed_auth(self):
        with self.assertRaises(ValueError):probe(source_timestamp_authenticated=True)
    def test_claimed_rights(self):
        with self.assertRaises(ValueError):probe(rights_verified=True)
    def test_naive_clock(self):
        with self.assertRaises(ValueError):probe(observed_at_utc=datetime(2026,11,7))
    def test_clock_offset(self):
        with self.assertRaises(ValueError):probe(observed_at_utc=T.astimezone(timezone(timedelta(hours=7))))
    def test_invalid_task_enum(self):
        with self.assertRaises(TypeError):probe(task="D1")
    def test_unknown_scope(self):
        with self.assertRaises(ValueError):probe(scope="")
    def test_origin(self):
        self.assertEqual(probe(origin=EvidenceOrigin.CONNECTED_READ_ONLY_CALLER_REPORTED).origin,
                         EvidenceOrigin.CONNECTED_READ_ONLY_CALLER_REPORTED)

class TestTiming(unittest.TestCase):
    def test_less_than_five_is_not_statistic(self):
        result=summarize_endpoint_probes(tuple(probe(ms=100+i) for i in range(4)))
        self.assertIsNone(result[0].median_ms)
        self.assertIsNone(result[0].p95_ms)
    def test_five_reported_samples(self):
        result=summarize_endpoint_probes(tuple(probe(ms=m) for m in [100,200,300,400,900]))
        self.assertEqual(result[0].median_ms,300)
        self.assertEqual(result[0].p95_ms,900)
        self.assertFalse(result[0].authorized_for_router)
        self.assertFalse(result[0].comparable_cross_provider_latency)
    def test_no_sla_even_100(self):
        a=summarize_endpoint_probes(tuple(probe(ms=100) for _ in range(100)))[0]
        self.assertFalse(a.provider_sla_verified)
        self.assertFalse(a.verified_market_session_p95)
    def test_failed_samples_not_ranked(self):
        r=summarize_endpoint_probes(tuple(probe(ms=m,success=(i<4),rows=2 if i<4 else 0,common=2 if i<4 else 0) for i,m in enumerate([1,2,3,4,5])))[0]
        self.assertIsNone(r.p95_ms)
        self.assertEqual(r.failures,1)
    def test_five_success_with_failure(self):
        arr=[probe(ms=100+i) for i in range(5)]+[probe(success=False,rows=0,common=0)]
        r=summarize_endpoint_probes(tuple(arr))[0]
        self.assertEqual(r.failures,1)
        self.assertEqual(r.total,6)
    def test_separate_provider_metrics(self):
        arr=tuple(probe(p,ms=10+i,scope={Provider.SSI:"coarse",Provider.DNSE:"year",Provider.VCBS:"date"}[p]) for p in Provider for i in range(5))
        result=summarize_endpoint_probes(arr)
        self.assertEqual(len(result),3)
        self.assertTrue(all(not x.comparable_cross_provider_latency for x in result))
    def test_different_scope_same_provider(self):
        arr=tuple(probe(ms=100,scope=s) for s in ("short","long") for _ in range(5))
        self.assertEqual(len(summarize_endpoint_probes(arr)),2)
    def test_no_data(self):self.assertEqual(summarize_endpoint_probes(()),())
    def test_list_rejected(self):
        with self.assertRaises(TypeError):summarize_endpoint_probes([probe()])
    def test_min_samples_not_less_five(self):
        with self.assertRaises(ValueError):summarize_endpoint_probes((),minimum_samples=3)
    def test_bounded_count(self):
        with self.assertRaises(ValueError):summarize_endpoint_probes(tuple(probe() for _ in range(1001)))
    def test_group_by_target(self):
        other=D1Target("SZC","HOSE",TARGET.first_session,TARGET.last_session)
        arr=tuple([probe() for _ in range(5)]+[probe(target=other) for _ in range(5)])
        self.assertEqual(len(summarize_endpoint_probes(arr)),2)
    def test_payload_estimate_not_network(self):
        r=summarize_endpoint_probes(tuple(probe(approximate_json_bytes=123) for _ in range(5)))[0]
        self.assertEqual(r.median_payload_json_estimate,123)
        self.assertFalse(r.comparable_cross_provider_latency)

class TestRows(unittest.TestCase):
    def test_valid(self):self.assertEqual(row().c_vnd,Decimal('10100'))
    def test_bad_high(self):
        with self.assertRaises(ValueError):row(h_vnd=Decimal('9000'))
    def test_bad_low(self):
        with self.assertRaises(ValueError):row(l_vnd=Decimal('10200'))
    def test_non_decimal(self):
        with self.assertRaises(ValueError):row(o_vnd=10000)
    def test_nan(self):
        with self.assertRaises(ValueError):row(o_vnd=Decimal('NaN'))
    def test_zero(self):
        with self.assertRaises(ValueError):row(c_vnd=Decimal('0'))
    def test_negative_volume(self):
        with self.assertRaises(ValueError):row(volume_shares=-1)
    def test_bool_volume(self):
        with self.assertRaises(ValueError):row(volume_shares=True)
    def test_session_outside(self):
        with self.assertRaises(ValueError):row(session=date(2026,11,3))
    def test_provider_metadata_not_caller_approved(self):
        with self.assertRaises(ValueError):row(provider_metadata_authenticated=True)
    def test_exchange_closed_not_caller_approved(self):
        with self.assertRaises(ValueError):row(venue_session_finality_verified=True)
    def test_negative_price(self):
        with self.assertRaises(ValueError):row(o_vnd=Decimal('-2'))
    def test_provisional_allowed_but_not_compared(self):
        self.assertTrue(row(provisional=True).provisional)

class TestParity(unittest.TestCase):
    def test_matching_price(self):
        r=compare_transient_d1_pair((row(),),(row(Provider.VCBS),),axis=ComparisonAxis.PRICE)
        self.assertEqual(r.status,ComparisonStatus.COMPARABLE_REPORTED)
        self.assertEqual(r.equal_sessions,1)
        self.assertFalse(r.source_integrity_verified)
    def test_mismatched_price(self):
        r=compare_transient_d1_pair((row(),),(row(Provider.DNSE,c_vnd=Decimal('10200')),),axis=ComparisonAxis.PRICE)
        self.assertEqual(r.different_sessions,1)
        self.assertFalse(r.actionable)
    def test_mismatched_volume(self):
        r=compare_transient_d1_pair((row(),),(row(Provider.VCBS,volume_shares=11000),),axis=ComparisonAxis.VOLUME)
        self.assertEqual(r.different_sessions,1)
    def test_unknown_price_basis(self):
        r=compare_transient_d1_pair((row(),),(row(Provider.DNSE,basis=PriceBasis.UNVERIFIED),),axis=ComparisonAxis.PRICE)
        self.assertEqual(r.unknown_basis_excluded,1)
        self.assertEqual(r.status,ComparisonStatus.BLOCKED_BASIS)
    def test_raw_vs_adjusted(self):
        r=compare_transient_d1_pair((row(),),(row(Provider.VCBS,basis=PriceBasis.ADJUSTED),),axis=ComparisonAxis.PRICE)
        self.assertEqual(r.unknown_basis_excluded,1)
    def test_unknown_volume(self):
        r=compare_transient_d1_pair((row(),),(row(Provider.DNSE,vol_basis=VolumeBasis.UNVERIFIED),),axis=ComparisonAxis.VOLUME)
        self.assertEqual(r.status,ComparisonStatus.BLOCKED_VOLUME_SCOPE)
    def test_total_vs_matched(self):
        r=compare_transient_d1_pair((row(),),(row(Provider.VCBS,vol_basis=VolumeBasis.TOTAL_WITH_DEALS),),axis=ComparisonAxis.VOLUME)
        self.assertEqual(r.comparable_sessions,0)
    def test_provisional_excluded(self):
        r=compare_transient_d1_pair((row(provisional=True),),(row(Provider.VCBS),),axis=ComparisonAxis.PRICE)
        self.assertEqual(r.provisional_excluded,1)
    def test_different_days_no_overlap(self):
        r=compare_transient_d1_pair((row(session=date(2026,11,5)),),(row(Provider.DNSE),),axis=ComparisonAxis.PRICE)
        self.assertEqual(r.status,ComparisonStatus.BLOCKED_NO_OVERLAP)
    def test_two_days_one_mismatch(self):
        left=(row(session=date(2026,11,5)),row())
        right=(row(Provider.VCBS,session=date(2026,11,5)),row(Provider.VCBS,c_vnd=Decimal('10300')))
        r=compare_transient_d1_pair(left,right,axis=ComparisonAxis.PRICE)
        self.assertEqual((r.common_sessions,r.equal_sessions,r.different_sessions),(2,1,1))
    def test_same_provider_rejected(self):
        with self.assertRaises(ValueError):compare_transient_d1_pair((row(),),(row(),),axis=ComparisonAxis.PRICE)
    def test_different_target(self):
        other=D1Target("SZC","HOSE",TARGET.first_session,TARGET.last_session)
        with self.assertRaises(ValueError):compare_transient_d1_pair((row(),),(row(Provider.DNSE,target=other),),axis=ComparisonAxis.PRICE)
    def test_duplicate_dates_rejected(self):
        with self.assertRaises(ValueError):compare_transient_d1_pair((row(),row()),(row(Provider.DNSE),),axis=ComparisonAxis.PRICE)
    def test_provider_mixed_rejected(self):
        with self.assertRaises(ValueError):compare_transient_d1_pair((row(),row(Provider.DNSE)),(row(Provider.VCBS),),axis=ComparisonAxis.PRICE)
    def test_tuple_required(self):
        with self.assertRaises(TypeError):compare_transient_d1_pair([row()],(row(Provider.DNSE),),axis=ComparisonAxis.PRICE)
    def test_bounded(self):
        with self.assertRaises(ValueError):compare_transient_d1_pair(tuple(row() for _ in range(501)),(row(Provider.DNSE),),axis=ComparisonAxis.PRICE)
    def test_no_values_in_report(self):
        r=compare_transient_d1_pair((row(),),(row(Provider.DNSE),),axis=ComparisonAxis.PRICE)
        self.assertFalse(any(k in r.__dict__ for k in ('o_vnd','volume_shares','session','c_vnd')))
    def test_release_denied(self):
        with self.assertRaises(PermissionError):require_benchmark_source_authority(None)
    def test_untyped_axis(self):
        with self.assertRaises(TypeError):compare_transient_d1_pair((row(),),(row(Provider.VCBS),),axis='PRICE')

if __name__=='__main__':unittest.main()
