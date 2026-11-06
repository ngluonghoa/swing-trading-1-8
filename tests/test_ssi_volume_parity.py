"""P0.12 read-only SSI daily/intraday volume reconciliation synthetic tests."""
import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

from swing_trading.ssi_volume_parity import (
    IntradayMinuteVolume, ParityState, SsiDailyMatchedReceipt,
    SsiIntradaySample, SsiTimestampLayout, SsiVolumeParityAudit,
    audit_ssi_intraday_daily_volume, normalize_ssi_volume,
    parse_ssi_local_timestamp,
)


UTC = timezone.utc
AS_OF = datetime(2026, 11, 6, 9, 0, tzinfo=UTC)
FETCHED = datetime(2026, 11, 6, 8, 58, tzinfo=UTC)


def fixture(date_value=date(2026,10,13), date_label="13/10/2026"):
    intraday = SsiIntradaySample(
        "SHS", "HNX", date_value, SsiTimestampLayout.DAY_MONTH_YEAR,
        "marketdata_list_intraday_stock_infor", FETCHED,
        (IntradayMinuteVolume("SHS", date_label + " 09:00:00", 1_500),
         IntradayMinuteVolume("SHS", date_label + " 09:01:00", 2_000),
         IntradayMinuteVolume("SHS", date_label + " 14:45:00", 600)),
        "synthetic-intraday-20261106",
    )
    daily = SsiDailyMatchedReceipt(
        "SHS", "HNX", date_value, 4_100,
        "marketdata_list_daily_stock_infor",
        FETCHED, "synthetic-daily-20261106",
    )
    return intraday, daily


def run(intraday=None,daily=None,asof=AS_OF):
    a,b=fixture()
    return audit_ssi_intraday_daily_volume(
        a if intraday is None else intraday,
        b if daily is None else daily,
        as_of_utc=asof,
    )


class SsiDailyIntradayParityTests(unittest.TestCase):
    def test_equal_totals_are_only_uncertified(self):
        result=run()
        self.assertEqual(result.state,ParityState.MATCH_UNCERTIFIED)
        self.assertEqual(result.reason,"TOTAL_MATCH_EQUAL_BUT_MINUTE_COVERAGE_UNCERTIFIED")
        self.assertEqual(result.summed_intraday_matched_volume,4100)
        self.assertEqual(result.daily_matched_volume,4100)
        self.assertEqual(result.source_row_count,3)
        self.assertFalse(result.timestamp_semantics_certified)
        self.assertFalse(result.minute_coverage_certified)
        self.assertFalse(result.cumulative_volume_certified)
        self.assertFalse(result.market_source_certified)
        self.assertFalse(result.actionable)

    def test_intraday_daily_volume_mismatch_is_blocked(self):
        a,b=fixture()
        result=run(daily=replace(b,total_match_volume=4101))
        self.assertEqual(result.state,ParityState.BLOCKED)
        self.assertEqual(result.reason,"INTRADAY_DAILY_MATCHED_VOLUME_MISMATCH")
        self.assertEqual(result.summed_intraday_matched_volume,4100)

    def test_none_daily_volume_is_not_treated_as_zero(self):
        a,b=fixture()
        self.assertEqual(run(daily=replace(b,total_match_volume=None)).reason,
                         "MISSING_DAILY_MATCHED_VOLUME")

    def test_empty_intraday_does_not_prove_nontrading_or_zero(self):
        a,b=fixture()
        a=replace(a,rows=())
        b=replace(b,total_match_volume=0)
        self.assertEqual(run(intraday=a,daily=b).reason,
                         "EMPTY_INTRADAY_IS_NOT_ZERO_VOLUME_OR_CLOSED_SESSION")

    def test_zero_minute_volume_is_valid(self):
        a,b=fixture()
        a=replace(a,rows=(replace(a.rows[0],matched_volume=0),)+a.rows[1:])
        b=replace(b,total_match_volume=2600)
        out=run(intraday=a,daily=b)
        self.assertEqual(out.state,ParityState.MATCH_UNCERTIFIED)
        self.assertEqual(out.summed_intraday_matched_volume,2600)

    def test_provider_date_order_is_never_guessed(self):
        a,b=fixture()
        a=replace(a,date_layout=SsiTimestampLayout.UNKNOWN)
        self.assertEqual(run(intraday=a).reason,"PROVIDER_DATE_LAYOUT_UNRESOLVED")
        a,b=fixture()
        a=replace(a,date_layout=SsiTimestampLayout.MONTH_DAY_YEAR)
        self.assertEqual(run(intraday=a).reason,
                         "BAD_OR_MISMATCHED_PROVIDER_DATE_LAYOUT")

    def test_october_12_is_ambiguous_without_declared_policy(self):
        a,b=fixture(date_value=date(2026,10,12),date_label="12/10/2026")
        self.assertEqual(run(intraday=a,daily=b).state,
                         ParityState.MATCH_UNCERTIFIED)
        a=replace(a,date_layout=SsiTimestampLayout.MONTH_DAY_YEAR)
        self.assertEqual(run(intraday=a,daily=b).reason,
                         "INTRADAY_TIMESTAMP_NOT_REQUESTED_TRADING_DATE")

    def test_future_sample_fetch_is_not_visible_at_asof(self):
        a,b=fixture()
        a=replace(a,fetched_at_utc=AS_OF+timedelta(minutes=1))
        self.assertEqual(run(intraday=a).reason,"ENDPOINT_SAMPLE_NOT_KNOWN_AT_AS_OF")

    def test_symbol_exchange_date_identity_are_strict(self):
        a,b=fixture()
        self.assertEqual(run(daily=replace(b,symbol="SSI")).reason,
                         "SYMBOL_EXCHANGE_OR_TRADING_DATE_MISMATCH")
        self.assertEqual(run(daily=replace(b,exchange="HOSE")).state,
                         ParityState.BLOCKED)
        self.assertEqual(run(daily=replace(b,trading_date=date(2026,10,12))).state,
                         ParityState.BLOCKED)

    def test_row_symbol_mismatch_blocks(self):
        a,b=fixture()
        a=replace(a,rows=(replace(a.rows[0],symbol="OTHER"),)+a.rows[1:])
        self.assertEqual(run(intraday=a).reason,"INTRADAY_SYMBOL_MISMATCH")

    def test_duplicate_minute_timestamps_do_not_double_count(self):
        a,b=fixture()
        a=replace(a,rows=a.rows[:2]+(replace(a.rows[-1],
                                                provider_local_timestamp=a.rows[0].provider_local_timestamp),))
        self.assertEqual(run(intraday=a).reason,"DUPLICATE_INTRADAY_TIME_SLOT")

    def test_unordered_descending_rows_are_accepted_without_changing_sums(self):
        a,b=fixture()
        out=run(intraday=replace(a,rows=tuple(reversed(a.rows))))
        self.assertEqual(out.state,ParityState.MATCH_UNCERTIFIED)
        self.assertLess(out.observed_first_utc,out.observed_last_utc)
        self.assertEqual(out.observed_first_utc.hour,2)

    def test_mismatched_provider_day_is_not_silently_remapped(self):
        a,b=fixture()
        a=replace(a,rows=(replace(a.rows[0],
                      provider_local_timestamp="12/10/2026 09:00:00"),)+a.rows[1:])
        self.assertEqual(run(intraday=a).reason,
                         "INTRADAY_TIMESTAMP_NOT_REQUESTED_TRADING_DATE")

    def test_bad_or_noncanonical_timestamp_blocked(self):
        a,b=fixture()
        for stamp in ("2026-10-13 09:00:00","13/10/2026 25:00:00",
                      "13/10/2026 09:00","3/10/2026 09:00:00"):
            with self.subTest(stamp=stamp):
                bad=replace(a,rows=(replace(a.rows[0],provider_local_timestamp=stamp),)+a.rows[1:])
                self.assertEqual(run(intraday=bad).reason,
                                 "BAD_OR_MISMATCHED_PROVIDER_DATE_LAYOUT")

    def test_future_market_timestamp_is_not_accepted(self):
        # Deliberately pretend current as_of is before the first source bar.
        a,b=fixture()
        asof=datetime(2026,10,13,1,30,tzinfo=UTC)
        a=replace(a,fetched_at_utc=asof-timedelta(minutes=2))
        b=replace(b,fetched_at_utc=asof-timedelta(minutes=1))
        self.assertEqual(run(intraday=a,daily=b,asof=asof).reason,
                         "FUTURE_MARKET_TIMESTAMP")

    def test_only_supported_endpoint_names_and_immutable_types(self):
        a,b=fixture()
        with self.assertRaises(ValueError):
            replace(a,endpoint="marketdata_list_stock_infor")
        with self.assertRaises(ValueError):
            replace(b,endpoint="marketdata_list_stock_daily_data")
        with self.assertRaises(TypeError):
            replace(a,rows=list(a.rows))
        with self.assertRaises(TypeError):
            audit_ssi_intraday_daily_volume(a,123,as_of_utc=AS_OF)

    def test_invalid_volume_and_future_approval_flags(self):
        a,b=fixture()
        with self.assertRaises(ValueError):
            replace(a.rows[0],matched_volume=True)
        with self.assertRaises(ValueError):
            replace(a.rows[0],matched_volume=-1)
        with self.assertRaises(ValueError):
            replace(b,total_match_volume=-1)
        with self.assertRaises(ValueError):
            SsiVolumeParityAudit(ParityState.MATCH_UNCERTIFIED,"fixture",2,5,5,None,None,
                                 market_source_certified=True)
        with self.assertRaises(ValueError):
            SsiVolumeParityAudit(ParityState.MATCH_UNCERTIFIED,"fixture",2,5,8,None,None)
        with self.assertRaises(ValueError):
            run(asof=AS_OF.replace(tzinfo=None))

    def test_volume_normalizer_rejects_float_and_locale_guessing(self):
        for v in ("0","1200",1200,0):
            self.assertEqual(normalize_ssi_volume(v),int(v))
        for v in ("1,200","1.5",-1,True,False,None,1.2,""," 1","-5"):
            with self.subTest(v=v), self.assertRaises(ValueError):
                normalize_ssi_volume(v)

    def test_explicit_vietnam_local_clock_from_utc(self):
        dt=parse_ssi_local_timestamp("13/10/2026 09:00:00",SsiTimestampLayout.DAY_MONTH_YEAR)
        self.assertEqual(dt,datetime(2026,10,13,2,0,tzinfo=UTC))
        with self.assertRaises(ValueError):
            parse_ssi_local_timestamp("13/10/2026 09:00:00",
                                      SsiTimestampLayout.UNKNOWN)


if __name__=="__main__":
    unittest.main()
