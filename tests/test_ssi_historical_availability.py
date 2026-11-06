"""P0.14 SSI historical empty-vs-positive-daily diagnostic tests."""
import unittest
from dataclasses import replace
from datetime import date, timedelta

from swing_trading.ssi_historical_availability import (
    HistoricalAvailabilityState, HistoricalAvailabilityReview,
    review_ssi_historical_day,
)
from swing_trading.ssi_volume_parity import SsiTimestampLayout
from test_ssi_volume_parity import AS_OF, fixture


def probe(intraday=None, daily=None):
    i,d=fixture()
    return review_ssi_historical_day(i if intraday is None else intraday,
                                      d if daily is None else daily,
                                      as_of_utc=AS_OF)


class SsiHistoricalAvailabilityTests(unittest.TestCase):
    def test_nonempty_matched_is_just_uncertified(self):
        r=probe()
        self.assertEqual(r.state,HistoricalAvailabilityState.NONEMPTY_MATCHED_UNCERTIFIED)
        self.assertEqual((r.intraday_count,r.intraday_total,r.daily_matched_volume),
                         (3,4100,4100))
        self.assertFalse(r.source_entitlement_certified)
        self.assertFalse(r.complete_m1_history_certified)
        self.assertFalse(r.retention_limit_verified)
        self.assertFalse(r.actionable)

    def test_positive_daily_with_empty_intraday_is_availability_gap(self):
        i,d=fixture()
        r=probe(intraday=replace(i,rows=()))
        self.assertEqual(r.state,
                         HistoricalAvailabilityState.INTRADAY_EMPTY_DAILY_TRADES_UNCERTIFIED)
        self.assertEqual(r.intraday_count,0)
        self.assertIsNone(r.intraday_total)
        self.assertEqual(r.daily_matched_volume,4100)
        self.assertFalse(r.retention_limit_verified)

    def test_empty_both_is_not_proof_of_nontrading(self):
        i,d=fixture()
        r=probe(intraday=replace(i,rows=()),daily=replace(d,total_match_volume=0))
        self.assertEqual(r.state,HistoricalAvailabilityState.BLOCKED)
        self.assertEqual(r.reason,"BOTH_ZERO_OR_EMPTY_DOES_NOT_PROVE_OFFICIAL_NONTRADING_DAY")

    def test_daily_not_found_blocks(self):
        i,d=fixture()
        self.assertEqual(probe(daily=replace(d,total_match_volume=None)).reason,
                         "DAILY_MATCHED_VOLUME_MISSING")

    def test_incorrect_provider_clock_layout_blocks_nonempty(self):
        i,d=fixture()
        i=replace(i,date_layout=SsiTimestampLayout.UNKNOWN)
        r=probe(intraday=i)
        self.assertEqual(r.state,HistoricalAvailabilityState.BLOCKED)
        self.assertEqual(r.reason,"INTRADAY_PARITY_PROVIDER_DATE_LAYOUT_UNRESOLVED")

    def test_mismatched_symbol_venue_day(self):
        i,d=fixture()
        for changed in (replace(d,symbol="OTHER"),replace(d,exchange="HOSE"),
                        replace(d,trading_date=date(2026,10,12))):
            with self.subTest(changed=changed):
                r=probe(daily=changed)
                self.assertEqual(r.reason,"INSTRUMENT_VENUE_DATE_MISMATCH")

    def test_future_fetched_data_never_qualifies(self):
        i,d=fixture()
        r=probe(intraday=replace(i,rows=(),fetched_at_utc=AS_OF+timedelta(seconds=1)))
        self.assertEqual(r.reason,"SOURCE_RECEIPT_AFTER_AUDIT_CLOCK")

    def test_volume_mismatch_retains_diagnostic_total(self):
        i,d=fixture()
        r=probe(daily=replace(d,total_match_volume=4102))
        self.assertEqual(r.state,HistoricalAvailabilityState.BLOCKED)
        self.assertEqual(r.intraday_total,4100)
        self.assertEqual(r.reason,"INTRADAY_PARITY_INTRADAY_DAILY_MATCHED_VOLUME_MISMATCH")

    def test_no_approval_flags_even_after_match(self):
        r=probe()
        for field in ("retention_limit_verified","provider_clock_certified",
                      "complete_m1_history_certified","source_entitlement_certified",
                      "actionable"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                replace(r,**{field:True})

    def test_reject_untyped_receipt(self):
        i,d=fixture()
        with self.assertRaises(TypeError):
            review_ssi_historical_day(i,"daily",as_of_utc=AS_OF)


if __name__=="__main__":
    unittest.main()
