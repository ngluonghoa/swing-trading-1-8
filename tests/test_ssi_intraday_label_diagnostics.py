"""P0.24 tests: synthetic SSI time-label surfaces NEVER equal validated M1 bars."""
from dataclasses import FrozenInstanceError, replace
from datetime import date, timedelta
import unittest

from swing_trading.source_capability_evidence import ProbeEndpoint, ProbeState
from swing_trading.ssi_intraday_label_diagnostics import (
    LabelOrderEvidence, inspect_ssi_intraday_surface,
)
from swing_trading.ssi_source_qualification import (
    DateOrder, EndpointTimestampPolicy, inspect_timestamp,
)
from test_dnse_d1_reference_fallback import NOW

DAY = date(2026, 10, 14)


def response(*labels, symbol="SHS"):
    return {"status": "ok", "data": {
        "ticks": [{"symbol": symbol, "trading_date": label,
                   "close": "998877", "volume": "777777"} for label in labels]
    }}


class SsiIntradayLabelDiagnosticsTests(unittest.TestCase):
    def inspect(self, body, *, endpoint=ProbeEndpoint.SSI_INTRADAY,
                requested_day=DAY, symbol="SHS"):
        return inspect_ssi_intraday_surface(
            endpoint, body, symbol=symbol, requested_day=requested_day,
            checked_at_utc=NOW,
        )

    def test_conditional_day_first_gap_geometry_is_not_bar_coverage(self):
        r=self.inspect(response(
            "14/10/2026 09:03:00", "14/10/2026 09:01:00",
            "14/10/2026 09:00:00",
        ))
        self.assertEqual(r.state, ProbeState.RETURNED_ROWS)
        self.assertEqual(r.observed_rows,3)
        self.assertEqual(r.date_order_evidence,
                         LabelOrderEvidence.DAY_FIRST_POSSIBLE_ONLY)
        self.assertEqual(r.observed_order,"DESCENDING")
        self.assertEqual(r.gaps_over_one_minute,1)
        self.assertEqual(r.longest_label_gap_minutes,2)
        self.assertEqual(r.unobserved_minutes_between_labels,1)
        self.assertEqual((r.earliest_minute_of_day,r.latest_minute_of_day),
                         (540,543))
        self.assertFalse(r.observed_gap_is_missing_candle)
        self.assertFalse(r.eligible_for_m1_m5_m15)
        self.assertFalse(r.historical_backtest_qualified)

    def test_lunch_like_gap_is_diagnostic_not_data_loss(self):
        r=self.inspect(response(
            "14/10/2026 13:01:00", "14/10/2026 13:00:00",
            "14/10/2026 11:30:00", "14/10/2026 11:29:00",
        ))
        self.assertEqual(r.gaps_over_one_minute,1)
        self.assertEqual(r.longest_label_gap_minutes,90)
        self.assertEqual(r.unobserved_minutes_between_labels,89)
        self.assertFalse(r.observed_gap_is_missing_candle)

    def test_duplicate_seconds_same_minute_are_not_independent_minute_bars(self):
        r=self.inspect(response(
            "14/10/2026 09:00:45", "14/10/2026 09:00:30",
            "14/10/2026 09:00:30",
        ))
        self.assertEqual(r.observed_rows,3)
        self.assertEqual(r.unique_text_labels,2)
        self.assertEqual(r.unique_minute_labels,1)
        self.assertEqual(r.duplicate_minute_labels,2)
        self.assertEqual(r.gaps_over_one_minute,0)
        self.assertEqual(r.longest_label_gap_minutes,0)

    def test_month_first_only_label_never_certifies_timestamp(self):
        r=self.inspect(response("10/14/2026 09:03:00"))
        self.assertEqual(r.date_order_evidence,
                         LabelOrderEvidence.MONTH_FIRST_POSSIBLE_ONLY)
        self.assertFalse(r.timestamp_semantics_verified)
        self.assertFalse(r.publisher_first_known_verified)

    def test_date_order_ambiguous_day_equals_month_returns_no_geometry(self):
        r=self.inspect(response("05/05/2026 09:03:00"),
                       requested_day=date(2026,5,5))
        self.assertEqual(r.date_order_evidence, LabelOrderEvidence.AMBIGUOUS)
        self.assertIsNone(r.unique_minute_labels)
        self.assertIsNone(r.longest_label_gap_minutes)
        self.assertEqual(r.observed_order,"UNDECIDABLE")

    def test_mixed_date_orders_for_one_requested_day_are_refused(self):
        with self.assertRaises(ValueError):
            self.inspect(response("14/10/2026 09:00:00",
                                  "10/14/2026 09:01:00"))

    def test_wrong_session_label_or_calendar_date_is_refused(self):
        with self.assertRaises(ValueError):
            self.inspect(response("15/10/2026 09:00:00"))
        with self.assertRaises(ValueError):
            self.inspect(response("31/02/2026 09:00:00"))

    def test_bad_label_shape_and_time_components_are_refused(self):
        for label in ("2026-10-14 09:00:00","14/10/2026 26:00:00",
                      "14/10/2026 09:61:00","14/10/2026 09:00:61",
                      "14/10/2026 09:00:00+07:00"):
            with self.subTest(label=label),self.assertRaises(ValueError):
                self.inspect(response(label))

    def test_provider_identity_and_typed_date_are_strict(self):
        with self.assertRaises(TypeError):
            self.inspect(response("14/10/2026 09:00:00"),
                         endpoint=ProbeEndpoint.DNSE_DAY)
        with self.assertRaises(TypeError):
            self.inspect(response("14/10/2026 09:00:00"),
                         requested_day=NOW)
        with self.assertRaises(ValueError):
            self.inspect(response("14/10/2026 09:00:00",symbol="BAD"))

    def test_empty_and_source_unavailable_do_not_create_gap_numbers(self):
        for body,state in (
            (response(),ProbeState.RETURNED_EMPTY),
            ({"status":"error","error":{"code":"DOWNSTREAM_UNAVAILABLE"}},
             ProbeState.DOWNSTREAM_UNAVAILABLE),
        ):
            with self.subTest(state=state):
                p=self.inspect(body,endpoint=ProbeEndpoint.SSI_FULL_INTRADAY)
                self.assertEqual(p.state,state)
                self.assertEqual(p.observed_rows,0)
                self.assertIsNone(p.gaps_over_one_minute)
                self.assertEqual(p.date_order_evidence,
                                 LabelOrderEvidence.EMPTY_OR_UNAVAILABLE)

    def test_label_diagnostics_do_not_expose_price_volume_or_credentials(self):
        r=self.inspect(response("14/10/2026 09:00:00"))
        output=repr(r)
        self.assertNotIn("998877",output)
        self.assertNotIn("777777",output)
        self.assertFalse(hasattr(r,"ticks"))
        self.assertFalse(hasattr(r,"close"))
        self.assertFalse(r.source_retention_rights_verified)
        self.assertFalse(r.actionable)

    def test_ascending_or_mixed_label_order_diagnostic(self):
        self.assertEqual(self.inspect(response(
            "14/10/2026 09:00:00","14/10/2026 09:02:00"
        )).observed_order,"ASCENDING")
        self.assertEqual(self.inspect(response(
            "14/10/2026 09:01:00","14/10/2026 09:00:00",
            "14/10/2026 09:02:00"
        )).observed_order,"MIXED")

    def test_reference_qualification_policy_conflict_still_blocks(self):
        policy=EndpointTimestampPolicy(
            endpoint_id=ProbeEndpoint.SSI_INTRADAY.value,
            policy_version="P0.24",
            documented_date_order=DateOrder.MONTH_FIRST,
            observed_date_order=DateOrder.DAY_FIRST,
            independently_confirmed=False,
            timestamp_label_confirmed=False,
        )
        assessment=inspect_timestamp("14/10/2026 09:00:00",DAY,policy,
                                     intraday=True)
        self.assertEqual(assessment.reason_code,
                         "DATE_ORDER_CONFLICT_OR_UNKNOWN")
        self.assertIsNone(assessment.interpreted_time_utc)
        self.assertFalse(assessment.usable_for_market_time)

    def test_no_mutable_approval_controls(self):
        r=self.inspect(response("14/10/2026 09:00:00"))
        with self.assertRaises(TypeError):
            replace(r,actionable=True)
        with self.assertRaises(FrozenInstanceError):
            r.observed_rows=999

    def test_transient_limit_blocks_unbounded_rows(self):
        labels=("14/10/2026 09:00:00" for _ in range(10001))
        with self.assertRaises(ValueError):
            self.inspect(response(*labels))


if __name__ == "__main__":
    unittest.main()
