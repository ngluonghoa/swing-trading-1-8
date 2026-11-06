"""P0.13 cross-venue diagnostic matrix synthetic unit and negative paths."""
import unittest
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

from swing_trading.ssi_multivenue_review import (
    MatrixState, SsiMatrixReview, SsiVenueSample, evaluate_ssi_venue_matrix,
)
from test_ssi_volume_parity import AS_OF, fixture


def make_sample(symbol="SHS", exchange="HNX", day=date(2026,10,13),
                day_label="13/10/2026"):
    intraday, daily = fixture(day, day_label)
    rows=tuple(replace(row,symbol=symbol) for row in intraday.rows)
    return SsiVenueSample(
        replace(intraday, symbol=symbol, exchange=exchange, rows=rows),
        replace(daily, symbol=symbol, exchange=exchange),
    )


def full_matrix():
    return (
        make_sample("SHS","HNX"),
        make_sample("SSI","HOSE"),
        make_sample("VGI","UPCOM"),
    )


class SsiMultiVenueTests(unittest.TestCase):
    def test_all_venues_sampled_is_still_uncertified(self):
        result=evaluate_ssi_venue_matrix(full_matrix(),as_of_utc=AS_OF)
        self.assertEqual(result.state,MatrixState.ALL_VENUES_OBSERVED_UNCERTIFIED)
        self.assertEqual(result.sample_count,3)
        self.assertEqual(result.matched_count,3)
        self.assertEqual(result.counts_by_venue,
                         (("HOSE",1),("HNX",1),("UPCOM",1)))
        self.assertEqual(result.blocked_samples,())
        for name in ("provider_independent","timestamp_semantics_certified",
                     "full_minutes_certified","source_entitlement_certified",
                     "suitable_for_rvol_tod","actionable"):
            self.assertFalse(getattr(result,name))

    def test_missing_venue_is_partial_not_a_certification(self):
        result=evaluate_ssi_venue_matrix(full_matrix()[:2],as_of_utc=AS_OF)
        self.assertEqual(result.state,MatrixState.PARTIAL_UNCERTIFIED)
        self.assertEqual(result.counts_by_venue,
                         (("HOSE",1),("HNX",1),("UPCOM",0)))

    def test_no_samples_is_blocked(self):
        r=evaluate_ssi_venue_matrix((),as_of_utc=AS_OF)
        self.assertEqual(r.state,MatrixState.BLOCKED)
        self.assertEqual(r.reason,"NO_OBSERVED_SSI_SAMPLES")

    def test_duplicate_symbol_venue_date_is_never_double_counted(self):
        x=full_matrix()
        result=evaluate_ssi_venue_matrix(x+(x[0],),as_of_utc=AS_OF)
        self.assertEqual(result.state,MatrixState.BLOCKED)
        self.assertEqual(result.matched_count,3)
        self.assertEqual(result.blocked_samples[0][-1],
                         "DUPLICATE_SYMBOL_VENUE_DATE_SAMPLE")

    def test_same_symbol_with_different_date_is_independent_sample(self):
        x=full_matrix()
        extra=make_sample("SHS","HNX",date(2026,10,14),"14/10/2026")
        result=evaluate_ssi_venue_matrix(x+(extra,),as_of_utc=AS_OF)
        self.assertEqual(result.state,MatrixState.ALL_VENUES_OBSERVED_UNCERTIFIED)
        self.assertEqual(result.matched_count,4)
        self.assertEqual(result.counts_by_venue,(("HOSE",1),("HNX",2),("UPCOM",1)))

    def test_non_matching_total_blocks_entire_matrix(self):
        rows=list(full_matrix())
        rows[1]=replace(rows[1],daily=replace(rows[1].daily,total_match_volume=3))
        result=evaluate_ssi_venue_matrix(tuple(rows),as_of_utc=AS_OF)
        self.assertEqual(result.state,MatrixState.BLOCKED)
        self.assertEqual(result.matched_count,2)
        self.assertEqual(result.blocked_samples[0][-1],
                         "INTRADAY_DAILY_MATCHED_VOLUME_MISMATCH")

    def test_unknown_ssi_date_layout_blocks_full_matrix(self):
        from swing_trading.ssi_volume_parity import SsiTimestampLayout
        rows=list(full_matrix())
        rows[0]=replace(rows[0],intraday=replace(rows[0].intraday,
                                                 date_layout=SsiTimestampLayout.UNKNOWN))
        r=evaluate_ssi_venue_matrix(tuple(rows),as_of_utc=AS_OF)
        self.assertEqual(r.state,MatrixState.BLOCKED)
        self.assertEqual(r.blocked_samples[0][-1],"PROVIDER_DATE_LAYOUT_UNRESOLVED")

    def test_unavailable_provider_endpoint_is_not_accepted_as_data(self):
        rows=list(full_matrix())
        bad=replace(rows[1].intraday,rows=())
        rows[1]=replace(rows[1],intraday=bad)
        r=evaluate_ssi_venue_matrix(tuple(rows),as_of_utc=AS_OF)
        self.assertEqual(r.state,MatrixState.BLOCKED)
        self.assertEqual(r.blocked_samples[0][-1],
                         "EMPTY_INTRADAY_IS_NOT_ZERO_VOLUME_OR_CLOSED_SESSION")

    def test_unsupported_exchange_is_not_silently_mapped(self):
        rows=list(full_matrix())
        i=replace(rows[2].intraday,exchange="OTHER")
        d=replace(rows[2].daily,exchange="OTHER")
        rows[2]=SsiVenueSample(i,d)
        r=evaluate_ssi_venue_matrix(tuple(rows),as_of_utc=AS_OF)
        self.assertEqual(r.state,MatrixState.BLOCKED)
        self.assertEqual(r.blocked_samples[0][-1],
                         "UNSUPPORTED_OR_UNVERIFIED_EXCHANGE")

    def test_bad_timestamp_future_source_blocks_whole_matrix(self):
        rows=list(full_matrix())
        rows[1]=replace(rows[1],intraday=replace(rows[1].intraday,
                                                  fetched_at_utc=AS_OF+timedelta(minutes=1)))
        r=evaluate_ssi_venue_matrix(tuple(rows),as_of_utc=AS_OF)
        self.assertEqual(r.state,MatrixState.BLOCKED)
        self.assertEqual(r.blocked_samples[0][-1],"ENDPOINT_SAMPLE_NOT_KNOWN_AT_AS_OF")

    def test_input_is_typed_immutable_and_clocks_utc(self):
        with self.assertRaises(TypeError):
            evaluate_ssi_venue_matrix(list(full_matrix()),as_of_utc=AS_OF)
        with self.assertRaises(TypeError):
            evaluate_ssi_venue_matrix((full_matrix()[0], 3),as_of_utc=AS_OF)
        with self.assertRaises(ValueError):
            evaluate_ssi_venue_matrix(full_matrix(),
                                      as_of_utc=AS_OF.replace(tzinfo=None))

    def test_no_forged_approval_in_result(self):
        r=evaluate_ssi_venue_matrix(full_matrix(),as_of_utc=AS_OF)
        with self.assertRaises(ValueError):
            replace(r,source_entitlement_certified=True)
        with self.assertRaises(ValueError):
            replace(r,suitable_for_rvol_tod=True)
        with self.assertRaises(ValueError):
            replace(r,actionable=True)


if __name__=="__main__":
    unittest.main()
