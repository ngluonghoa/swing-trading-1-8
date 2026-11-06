"""P0.5 contract tests; deliberately offline. Values are sample fixtures, not source certification."""
import unittest
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal

from swing_trading.market_data import PriceBasis
from swing_trading.ssi_source_qualification import (
    DateOrder, EndpointTimestampPolicy, SourceCoverageObservation,
    DailyFirstRecordParity, ParityState, RecordAvailability, SourceGate,
    inspect_timestamp, cross_timeframe_price_basis,
)

DAY = date(2026, 11, 4)
OCT = date(2026, 10, 13)
NOW = datetime(2026, 11, 6, 4, 55, tzinfo=timezone.utc)


def policy(documented=DateOrder.MONTH_FIRST, observed=DateOrder.DAY_FIRST,
           approved=False, clock=False):
    return EndpointTimestampPolicy(
        "ssi.mcp.intraday", "fixture-contract-v1", documented, observed,
        approved, clock,
    )


class SSISourceQualificationTests(unittest.TestCase):
    def test_unambiguous_day_first_record_conflicts_with_month_first_description(self):
        p = policy()
        result = inspect_timestamp("13/10/2026 09:00:00", OCT, p, intraday=True)
        self.assertEqual(result.date_candidates, (OCT,))
        self.assertEqual(result.reason_code, "DATE_ORDER_CONFLICT_OR_UNKNOWN")
        self.assertFalse(result.usable_for_market_time)
        self.assertIsNone(result.interpreted_time_utc)

    def test_ambiguous_record_never_auto_guesses_day_or_month(self):
        result = inspect_timestamp("04/11/2026 09:00:00", DAY, policy(), intraday=True)
        self.assertEqual(len(result.date_candidates), 2)
        self.assertIn(DAY, result.date_candidates)
        self.assertIsNone(result.interpreted_time_utc)

    def test_agreeing_convention_without_independent_confirmation_is_blocked(self):
        p = policy(documented=DateOrder.DAY_FIRST, approved=False)
        result = inspect_timestamp("13/10/2026 09:00:00", OCT, p, intraday=True)
        self.assertEqual(result.reason_code, "DATE_ORDER_NOT_INDEPENDENTLY_CONFIRMED")
        self.assertIsNone(result.interpreted_time_utc)

    def test_approved_date_without_approved_clock_label_is_still_blocked(self):
        p = policy(documented=DateOrder.DAY_FIRST, approved=True)
        result = inspect_timestamp("13/10/2026 09:00:00", OCT, p, intraday=True)
        self.assertEqual(result.reason_code, "INTRADAY_CLOCK_LABEL_NOT_CONFIRMED")
        self.assertIsNone(result.interpreted_time_utc)

    def test_only_both_independently_approved_conditions_allow_utc_translation(self):
        p = policy(documented=DateOrder.DAY_FIRST, approved=True, clock=True)
        result = inspect_timestamp("13/10/2026 09:00:00", OCT, p, intraday=True)
        self.assertEqual(result.reason_code, "DATE_AND_CLOCK_SEMANTICS_VERIFIED")
        self.assertTrue(result.usable_for_market_time)
        self.assertEqual(result.interpreted_time_utc,
                         datetime(2026, 10, 13, 2, tzinfo=timezone.utc))

    def test_unverified_daily_date_does_not_create_market_session_instant(self):
        p = policy(documented=DateOrder.DAY_FIRST, approved=True, clock=True)
        result = inspect_timestamp("04/11/2026", DAY, p, intraday=False)
        self.assertEqual(result.reason_code, "DAILY_DATE_ONLY_NO_MARKET_CUTOFF")
        self.assertFalse(result.usable_for_market_time)
        self.assertIsNone(result.interpreted_time_utc)

    def test_clock_parsing_is_strict(self):
        p = policy(documented=DateOrder.DAY_FIRST, approved=True, clock=True)
        self.assertEqual(inspect_timestamp("13/10/2026 25:00:00", OCT, p,
                         intraday=True).reason_code, "INVALID_SESSION_CLOCK")
        self.assertEqual(inspect_timestamp("31/02/2026 09:00:00", OCT, p,
                         intraday=True).reason_code, "INVALID_CALENDAR_DATE")
        self.assertEqual(inspect_timestamp("13-10-2026 09:00:00", OCT, p,
                         intraday=True).reason_code, "INVALID_DATE_SHAPE")
        self.assertEqual(inspect_timestamp("13/10/2026 09:00:00",
                         DAY, p, intraday=True).reason_code,
                         "DATE_DOES_NOT_MATCH_QUERY")

    def test_unknown_date_order_rejects_even_when_other_flag_true(self):
        p = policy(documented=DateOrder.UNKNOWN, observed=DateOrder.UNKNOWN,
                   approved=True, clock=True)
        result = inspect_timestamp("13/10/2026 09:00:00", OCT, p, intraday=True)
        self.assertEqual(result.reason_code, "DATE_ORDER_CONFLICT_OR_UNKNOWN")

    def test_zero_records_means_unknown_not_no_trade(self):
        obs = SourceCoverageObservation("ssi.mcp.intraday", "SHS",
                                        date(2026, 9, 1), 0, NOW, True, True)
        self.assertEqual(obs.availability, RecordAvailability.EMPTY_UNKNOWN)
        self.assertFalse(obs.usable_history_coverage)

    def test_nonempty_single_day_or_unfinished_pages_not_long_history(self):
        obs = SourceCoverageObservation("ssi.mcp.intraday", "SHS",
                                        DAY, 235, NOW, True, True)
        self.assertEqual(obs.availability, RecordAvailability.OBSERVED_UNVERIFIED)
        self.assertFalse(obs.usable_history_coverage)
        self.assertFalse(replace(obs, pagination_complete=False).usable_history_coverage)
        self.assertEqual(replace(obs, request_succeeded=False).availability,
                         RecordAvailability.ERROR_BLOCKED)

    def test_d1_first_intraday_mismatch_remains_blocked_without_auto_repair(self):
        for instrument, daily, minute, delta in (
            ("SHS", "12400", "12300", "100"),
            ("VGI", "75000", "74500", "500"),
        ):
            with self.subTest(instrument=instrument):
                x = DailyFirstRecordParity(
                    instrument, DAY, Decimal(daily), Decimal(minute),
                    "09:00:00 unverified timestamp label",
                )
                self.assertEqual(x.parity_state, ParityState.MISMATCH_BLOCKED)
                self.assertEqual(x.delta, Decimal(delta))

    def test_matching_prices_do_not_authorize_provider_parity(self):
        x = DailyFirstRecordParity("SHS", DAY, Decimal("12400"),
                                   Decimal("12400"), "09:00:00")
        self.assertEqual(x.parity_state, ParityState.MATCH_UNVERIFIED)
        self.assertEqual(x.delta, Decimal(0))
        self.assertEqual(replace(x, first_intraday_open=None).parity_state,
                         ParityState.MISSING_UNKNOWN)

    def test_adjusted_daily_and_raw_intraday_must_not_be_joined(self):
        self.assertEqual(cross_timeframe_price_basis(
            PriceBasis.ADJUSTED, PriceBasis.RAW,
            independently_verified_adjustment_mapping=False,
        ), SourceGate.BLOCKED)
        self.assertEqual(cross_timeframe_price_basis(
            PriceBasis.UNKNOWN, PriceBasis.RAW,
            independently_verified_adjustment_mapping=True,
        ), SourceGate.BLOCKED)
        self.assertEqual(cross_timeframe_price_basis(
            PriceBasis.RAW, PriceBasis.RAW,
            independently_verified_adjustment_mapping=False,
        ), SourceGate.OBSERVED_UNVERIFIED)
        self.assertEqual(cross_timeframe_price_basis(
            PriceBasis.ADJUSTED, PriceBasis.RAW,
            independently_verified_adjustment_mapping=True,
        ), SourceGate.OBSERVED_UNVERIFIED)

    def test_invalid_source_observations_and_price_types_are_rejected(self):
        with self.assertRaises(TypeError):
            inspect_timestamp("13/10/2026", datetime(2026, 10, 13), policy(),
                              intraday=False)
        with self.assertRaises(TypeError):
            inspect_timestamp("13/10/2026", OCT, policy(), intraday=1)
        with self.assertRaises(ValueError):
            SourceCoverageObservation("a", "SHS", DAY, -1, NOW, True, True)
        with self.assertRaises(ValueError):
            SourceCoverageObservation("a", "SHS", DAY, True, NOW, True, True)
        with self.assertRaises(ValueError):
            SourceCoverageObservation("a", "SHS", DAY, 0,
                                      NOW.replace(tzinfo=None), True, True)
        with self.assertRaises(TypeError):
            EndpointTimestampPolicy("a", "v1", "DD/MM/YYYY",
                                    DateOrder.DAY_FIRST, False, False)
        with self.assertRaises(ValueError):
            DailyFirstRecordParity("SHS", DAY, 12400.0, Decimal("12300"), None)
        with self.assertRaises(TypeError):
            cross_timeframe_price_basis(
                PriceBasis.RAW, PriceBasis.RAW,
                independently_verified_adjustment_mapping=1
            )


if __name__ == "__main__":
    unittest.main()
