"""Offline regression for C2C; all inputs are invented metadata fixtures."""
import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

from swing_trading.incremental_cache import Provider
from swing_trading.c2_source_capability_audit import ConnectedEndpoint, DataNeed
from swing_trading.c2_session_probe_readiness import (
    ByteMeasurement, EvidenceKind, ProbeError, SessionPhase, SessionProbe,
    require_authorized_session_metrics, session_coverage, summarize_session_probes,
)

DAY = date(2026, 11, 9)
CLOCK = datetime(2026, 11, 9, 3, 0, tzinfo=timezone.utc)

def probe(**overrides):
    kwargs = dict(provider=Provider.SSI, endpoint=ConnectedEndpoint.SSI_INTRADAY_SESSION,
                  need=DataNeed.MINUTE_OHLCV, target_symbol="FPT", venue="HOSE",
                  requested_scope="range=1d", session_date=DAY,
                  phase=SessionPhase.CONTINUOUS_AM, origin=EvidenceKind.SYNTHETIC,
                  observed_at_utc=CLOCK, client_monotonic_elapsed_ns=120_000_000,
                  success=True, error=ProbeError.NONE, returned_rows=12)
    kwargs.update(overrides)
    return SessionProbe(**kwargs)

class TestSingleProbe(unittest.TestCase):
    def test_accepted(self):
        self.assertEqual(probe().elapsed_ms, 120)
    def test_wrong_provider(self):
        with self.assertRaises(ValueError): probe(provider=Provider.DNSE)
    def test_wrong_task(self):
        with self.assertRaises(ValueError): probe(need=DataNeed.D1_OHLCV)
    def test_wrong_endpoint(self):
        with self.assertRaises(ValueError): probe(endpoint=ConnectedEndpoint.VCBS_INTRADAY_PRICE_POINTS)
    def test_no_price_only_minute_bar_substitution(self):
        with self.assertRaises(ValueError): probe(endpoint=ConnectedEndpoint.VCBS_INTRADAY_PRICE_POINTS,provider=Provider.VCBS)
    def test_no_d1_task_for_minute(self):
        with self.assertRaises(ValueError): probe(endpoint=ConnectedEndpoint.DNSE_D1_HISTORY, provider=Provider.DNSE)
    def test_dnse_d1_allowed_but_not_proved(self):
        p=probe(provider=Provider.DNSE,endpoint=ConnectedEndpoint.DNSE_D1_HISTORY,need=DataNeed.D1_OHLCV)
        self.assertFalse(p.source_authenticated)
    def test_venue_required(self):
        with self.assertRaises(ValueError): probe(venue="NYSE")
    def test_normalized_symbol_required(self):
        with self.assertRaises(ValueError): probe(target_symbol="fpt")
    def test_nonempty_request_scope(self):
        with self.assertRaises(ValueError): probe(requested_scope="")
    def test_local_day_mismatch(self):
        with self.assertRaises(ValueError): probe(session_date=DAY+timedelta(days=1))
    def test_naive_clock(self):
        with self.assertRaises(ValueError): probe(observed_at_utc=datetime(2026,11,9,3))
    def test_non_utc(self):
        with self.assertRaises(ValueError): probe(observed_at_utc=CLOCK.astimezone(timezone(timedelta(hours=7))))
    def test_zero_elapsed(self):
        with self.assertRaises(ValueError): probe(client_monotonic_elapsed_ns=0)
    def test_bool_elapsed(self):
        with self.assertRaises(ValueError): probe(client_monotonic_elapsed_ns=True)
    def test_explicit_error(self):
        with self.assertRaises(ValueError): probe(success=False,error=ProbeError.NONE,returned_rows=0)
    def test_failed_with_data(self):
        with self.assertRaises(ValueError): probe(success=False,error=ProbeError.TIMEOUT)
    def test_failed_empty_ok(self):
        p=probe(success=False,error=ProbeError.TIMEOUT,returned_rows=0)
        self.assertFalse(p.success)
    def test_empty_success_is_unverified(self):
        self.assertEqual(probe(returned_rows=0).returned_rows,0)
    def test_negative_rows(self):
        with self.assertRaises(ValueError): probe(returned_rows=-1)
    def test_boolean_rows(self):
        with self.assertRaises(ValueError): probe(returned_rows=True)
    def test_provisional_out_of_bounds(self):
        with self.assertRaises(ValueError): probe(provisional_rows=13)
    def test_corrections_out_of_bounds(self):
        with self.assertRaises(ValueError): probe(changed_closed_rows_reported=13)
    def test_no_fake_wire_bytes(self):
        with self.assertRaises(ValueError): probe(measured_bytes=200)
    def test_no_negative_real_bytes(self):
        with self.assertRaises(ValueError): probe(byte_measurement=ByteMeasurement.NETWORK_WIRE_TOTAL,measured_bytes=-1)
    def test_response_body_not_wire(self):
        p=probe(byte_measurement=ByteMeasurement.HTTP_RESPONSE_BODY,measured_bytes=200)
        self.assertIsNot(p.byte_measurement,ByteMeasurement.NETWORK_WIRE_TOTAL)
    def test_estimate_cannot_be_negative(self):
        with self.assertRaises(ValueError): probe(estimated_serialized_json_bytes=-1)
    def test_older_source_timestamp_is_caller_report(self):
        p=probe(reported_provider_timestamp_utc=CLOCK-timedelta(minutes=10))
        self.assertFalse(p.source_authenticated)
    def test_future_source_clock(self):
        with self.assertRaises(ValueError): probe(reported_provider_timestamp_utc=CLOCK+timedelta(seconds=1))
    def test_fake_calendar_authority(self):
        with self.assertRaises(ValueError): probe(calendar_verified=True)
    def test_fake_source_authority(self):
        with self.assertRaises(ValueError): probe(source_authenticated=True)
    def test_fake_retention_rights(self):
        with self.assertRaises(ValueError): probe(retention_authorized=True)

class TestSummary(unittest.TestCase):
    def test_five_samples_descriptive_only(self):
        x=summarize_session_probes(tuple(probe(client_monotonic_elapsed_ns=m*1_000_000)
                                        for m in (50,100,120,300,900)))[0]
        self.assertEqual(x.median_elapsed_ms,120)
        self.assertEqual(x.p95_elapsed_ms,900)
        self.assertFalse(x.provider_sla_verified)
        self.assertFalse(x.router_eligible)
        self.assertFalse(x.cache_rights_verified)
    def test_four_samples_have_no_percentiles(self):
        x=summarize_session_probes(tuple(probe() for _ in range(4)))[0]
        self.assertIsNone(x.p95_elapsed_ms)
    def test_empty_success_does_not_count_for_percentiles(self):
        x=summarize_session_probes(tuple([probe() for _ in range(4)]+[probe(returned_rows=0)]))[0]
        self.assertEqual(x.empty_successes,1)
        self.assertIsNone(x.p95_elapsed_ms)
    def test_failed_samples_do_not_enter_percentiles(self):
        x=summarize_session_probes(tuple([probe() for _ in range(4)]+[probe(success=False,error=ProbeError.TIMEOUT,returned_rows=0)]))[0]
        self.assertEqual(x.failed,1)
        self.assertIsNone(x.p95_elapsed_ms)
    def test_different_source_separate(self):
        arr=tuple([probe() for _ in range(5)]+[
            probe(provider=Provider.DNSE,endpoint=ConnectedEndpoint.DNSE_D1_HISTORY,
                  need=DataNeed.D1_OHLCV, requested_scope="entire-history") for _ in range(5)])
        self.assertEqual(len(summarize_session_probes(arr)),2)
    def test_scope_and_phase_separate(self):
        arr=tuple([probe() for _ in range(5)]+[probe(requested_scope="latest") for _ in range(5)]
                  +[probe(phase=SessionPhase.ATC) for _ in range(5)])
        self.assertEqual(len(summarize_session_probes(arr)),3)
    def test_venue_and_symbol_separate(self):
        arr=tuple([probe() for _ in range(5)]+[probe(venue="HNX") for _ in range(5)]
                  +[probe(target_symbol="SHS") for _ in range(5)])
        self.assertEqual(len(summarize_session_probes(arr)),3)
    def test_estimated_bytes_do_not_establish_wire(self):
        x=summarize_session_probes(tuple(probe(estimated_serialized_json_bytes=1000) for _ in range(5)))[0]
        self.assertIsNone(x.median_network_wire_bytes)
        self.assertEqual(x.measured_network_wire_samples,0)
    def test_http_body_not_wire(self):
        x=summarize_session_probes(tuple(probe(byte_measurement=ByteMeasurement.HTTP_RESPONSE_BODY,
                                              measured_bytes=1000) for _ in range(5)))[0]
        self.assertEqual(x.measured_network_wire_samples,0)
    def test_five_measured_wires_descriptive(self):
        x=summarize_session_probes(tuple(probe(byte_measurement=ByteMeasurement.NETWORK_WIRE_TOTAL,
                                              measured_bytes=n) for n in (100,200,300,400,500)))[0]
        self.assertEqual(x.median_network_wire_bytes,300)
        self.assertFalse(x.network_delta_supported)
    def test_reported_stale_source_is_not_authenticity(self):
        x=summarize_session_probes(tuple(probe(reported_provider_timestamp_utc=CLOCK-timedelta(minutes=6))
                                        for _ in range(5)))[0]
        self.assertEqual(x.reported_source_older_than_5m,5)
        self.assertFalse(x.independent_source_freshness_verified)
    def test_provisional_correction_metadata_counts(self):
        x=summarize_session_probes(tuple(probe(provisional_rows=1,
                                        changed_closed_rows_reported=2) for _ in range(5)))[0]
        self.assertEqual(x.reported_provisional_rows,5)
        self.assertEqual(x.reported_corrections,10)
    def test_no_output_quotes_or_symbol(self):
        x=summarize_session_probes(tuple(probe() for _ in range(5)))[0]
        self.assertNotIn("target_symbol",vars(x))
        self.assertNotIn("price",vars(x))
        self.assertNotIn("requested_scope",vars(x))
    def test_tuple_only(self):
        with self.assertRaises(TypeError): summarize_session_probes([probe()])
    def test_minimum_five(self):
        with self.assertRaises(ValueError): summarize_session_probes((),min_successes=4)
    def test_bound_samples(self):
        with self.assertRaises(ValueError): summarize_session_probes(tuple(probe() for _ in range(2001)))

class TestCoverage(unittest.TestCase):
    def test_single_weekday_has_gaps(self):
        r=session_coverage((probe(),))[0]
        self.assertIn("MULTIPLE_WEEKDAY_SESSIONS_MISSING",r.missing_review_gates)
        self.assertIn("AUCTION_PHASE_MISSING",r.missing_review_gates)
        self.assertFalse(r.validated_market_session)
    def test_weekend_not_valid_session(self):
        saturday=datetime(2026,11,7,3,tzinfo=timezone.utc)
        r=session_coverage((probe(observed_at_utc=saturday,session_date=date(2026,11,7)),))[0]
        self.assertEqual(r.weekend_observations,1)
        self.assertEqual(r.observed_dates,0)
    def test_weekdays_auction_and_wire_still_unverified(self):
        tuesday=CLOCK+timedelta(days=1)
        r=session_coverage(tuple([probe()]+[probe(observed_at_utc=tuesday,session_date=date(2026,11,10),
                                      phase=SessionPhase.ATC,byte_measurement=ByteMeasurement.NETWORK_WIRE_TOTAL,
                                      measured_bytes=700)]))[0]
        self.assertEqual(r.observed_dates,2)
        self.assertEqual(r.auction_observations,1)
        self.assertEqual(r.measured_wire_observations,1)
        self.assertEqual(len(r.missing_review_gates),3)
        self.assertFalse(r.authorized_for_router)
    def test_source_scope_coverage_is_not_an_sla(self):
        c=session_coverage(tuple(probe() for _ in range(10)))[0]
        self.assertFalse(c.validated_market_session)
    def test_groups_by_venue(self):
        self.assertEqual(len(session_coverage((probe(),probe(venue="HNX")))),2)
    def test_tuple_only(self):
        with self.assertRaises(TypeError):session_coverage([probe()])
    def test_no_promotion(self):
        with self.assertRaises(PermissionError):require_authorized_session_metrics()

if __name__=="__main__":
    unittest.main()
