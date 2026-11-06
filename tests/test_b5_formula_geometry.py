"""P0.8 B5 raw-geometry tests: synthetic, never executable signals."""
import unittest
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from swing_trading.b5_formula_geometry import (
    B5GeometryState, B5StrategyFormulaDraft, calculate_b5_raw_geometry,
    draft_for,
)
from swing_trading.b5_phase_contract import B5Ingredient
from swing_trading.contracts import Strategy
from swing_trading.market_data import PriceBasis, Timeframe
from swing_trading.source_quality import resolve_as_known, QualityState
from test_b5_phase_contract import fixture_receipts, changed, resolved
from test_b5_feature_pack import rebar
from test_source_quality import T, candle, m


def anchors():
    p, a, b, rs = fixture_receipts()
    # Retracement high is only available after the M15 retest has CLOSED
    # and its v1.2 source snapshot is verified at m(50).
    micro = b
    fb = rebar(
        candle(), timeframe=Timeframe.M15, start=m(15), end=m(30),
        known=m(30), retrieved=m(30), verified=m(30),
        open_price=Decimal("10"), low=Decimal("9"), close=Decimal("9.5"),
    )
    return p, a, b, rs, micro, resolved(fb)


def run(*, pivot=None, breakout=None, retest=None, receipts=None,
        micro_high_anchor="use", failed_break_anchor=None,
        variant_id="B5/E_RECLAIM", strategy=Strategy.SHORT, asof=None):
    p, a, b, rs, micro, fb = anchors()
    if micro_high_anchor == "use":
        micro_high_anchor = micro
    if failed_break_anchor == "use":
        failed_break_anchor = fb
    return calculate_b5_raw_geometry(
        p if pivot is None else pivot,
        a if breakout is None else breakout,
        b if retest is None else retest,
        rs if receipts is None else receipts,
        strategy=strategy, variant_id=variant_id, as_of_utc=asof or m(120),
        micro_high_anchor=micro_high_anchor,
        failed_break_anchor=failed_break_anchor,
    )


class B5GeometryTests(unittest.TestCase):
    def test_all_strategy_variant_outputs_are_nonactionable(self):
        for strategy in (Strategy.SHORT, Strategy.SWING):
            for variant in ("B5/E_RECLAIM", "B5/E_FAILED_BREAK"):
                with self.subTest(strategy=strategy, variant=variant):
                    output = run(strategy=strategy, variant_id=variant,
                                 failed_break_anchor="use")
                    self.assertEqual(output.state,
                                     B5GeometryState.RAW_GEOMETRY_UNCALIBRATED)
                    self.assertFalse(output.detector_approved)
                    self.assertFalse(output.actionable)
                    self.assertIsNone(draft_for(strategy).rc_window_sessions)
                    self.assertFalse(draft_for(strategy).risk_policy_approved)
                    self.assertEqual(output.formula_version,
                                     "B5/" + strategy.value + "/FORMULA_DRAFT_0_1")

    def test_signed_geometry_is_math_not_a_predicate(self):
        output = run()
        self.assertEqual(output.geometry.breakout_close_above_pivot_atr, Decimal("1"))
        self.assertEqual(output.geometry.retest_low_minus_pivot_atr, Decimal("-0.2"))
        self.assertEqual(output.geometry.retest_close_minus_pivot_atr, Decimal("0.5"))
        self.assertEqual(output.geometry.retest_recovery_from_low_atr, Decimal("0.7"))
        self.assertEqual(output.geometry.failed_break_close_minus_pivot_atr, None)
        self.assertEqual(output.geometry.pivot_event_id, "pivot-fixture-1")
        self.assertEqual(output.geometry.retest_elapsed_seconds_from_breakout,
                         Decimal("1800"))
        self.assertEqual(output.geometry.followup_close_minus_micro_high_atr,
                         Decimal("-1"))

    def test_failed_break_branch_requires_independent_prior_closed_bar(self):
        output = run(variant_id="B5/E_FAILED_BREAK")
        self.assertEqual(output.state, B5GeometryState.ANCHOR_BLOCKED)
        self.assertEqual(output.reason, "NO_PRIOR_CLOSED_FAILED_BREAK_BAR")
        self.assertIsNone(output.geometry)

    def test_prior_failed_break_must_be_below_pivot(self):
        p, a, b, rs, micro, fb = anchors()
        higher = replace(fb.selected, close=Decimal("10.1"))
        b2 = resolve_as_known(higher.market_bar_key, (higher,), m(120))
        output = run(variant_id="B5/E_FAILED_BREAK", failed_break_anchor=b2)
        self.assertEqual(output.reason,
                         "FAILED_BREAK_BAR_NOT_BELOW_PIVOT_AFTER_BREAKOUT")

    def test_prior_failed_break_must_not_use_future_known_revision(self):
        p, a, b, rs, micro, fb = anchors()
        later = replace(fb.selected, verified_at_utc=m(40))
        b2 = resolve_as_known(later.market_bar_key, (later,), m(120))
        self.assertEqual(run(variant_id="B5/E_FAILED_BREAK",
                             failed_break_anchor=b2).reason,
                         "NO_PRIOR_CLOSED_FAILED_BREAK_BAR")

    def test_future_known_micro_high_cannot_be_used(self):
        p, a, b, rs, micro, fb = anchors()
        revised = replace(b.selected, verified_at_utc=m(55))
        late = resolve_as_known(revised.market_bar_key, (revised,), m(120))
        self.assertEqual(run(micro_high_anchor=late).reason,
                         "NO_CAUSAL_MICRO_HIGH_ANCHOR")

    def test_missing_micro_high_is_blocked(self):
        self.assertEqual(run(micro_high_anchor=None).state,
                         B5GeometryState.ANCHOR_BLOCKED)

    def test_no_cross_instrument_basis_or_calendar_in_anchor(self):
        p, a, b, rs, micro, fb = anchors()
        key = replace(micro.market_bar_key, price_basis=PriceBasis.ADJUSTED)
        obs = replace(micro.selected.observation_key, market_bar_key=key)
        rev = replace(micro.selected.observation_revision, observation_key=obs)
        changed_bar = replace(micro.selected, market_bar_key=key,
                              observation_key=obs, observation_revision=rev)
        alt = resolve_as_known(key, (changed_bar,), m(120))
        self.assertEqual(run(micro_high_anchor=alt).state,
                         B5GeometryState.ANCHOR_BLOCKED)

    def test_unverified_anchor_rejected(self):
        p, a, b, rs, micro, fb = anchors()
        low = replace(micro.selected, quality_state=QualityState.UNVERIFIED)
        alt = resolve_as_known(low.market_bar_key, (low,), m(120))
        self.assertEqual(run(micro_high_anchor=alt).reason,
                         "NO_CAUSAL_MICRO_HIGH_ANCHOR")

    def test_missing_receipt_aborts_math(self):
        p, a, b, rs, micro, fb = anchors()
        incomplete = tuple(item for item in rs if item.ingredient
                           is not B5Ingredient.RF_VOLUME)
        result = run(receipts=incomplete)
        self.assertEqual(result.state, B5GeometryState.BASE_BLOCKED)
        self.assertIsNone(result.geometry)

    def test_conflicting_future_receipt_blocks_geometry(self):
        _, _, _, rs, _, _ = anchors()
        bad = changed(rs, B5Ingredient.RF_VOLUME, first_known_time_utc=m(130))
        self.assertEqual(run(receipts=bad).state, B5GeometryState.BASE_BLOCKED)

    def test_cannot_set_thresholds_in_unapproved_strategy_registry(self):
        for strategy in (Strategy.SHORT, Strategy.SWING):
            draft = draft_for(strategy)
            with self.assertRaises(ValueError):
                replace(draft, rc_tolerance_atr=Decimal("0.2"))
            with self.assertRaises(ValueError):
                replace(draft, risk_policy_approved=True)
            with self.assertRaises(ValueError):
                replace(draft, rc_window_sessions=3)
            with self.assertRaises(ValueError):
                replace(draft, rule_version="B5/OTHER/FORMULA_DRAFT_0_1")

    def test_variant_and_utc_must_be_explicit(self):
        with self.assertRaises(ValueError):
            run(variant_id="B5/E_AUTO")
        with self.assertRaises(TypeError):
            run(strategy="SHORT")
        with self.assertRaises(ValueError):
            run(asof=m(120).replace(tzinfo=None))

    def test_optional_failed_break_absent_in_reclaim_branch(self):
        r = run(variant_id="B5/E_RECLAIM")
        self.assertIsNone(r.geometry.failed_break_close_minus_pivot_atr)

    def test_late_known_failed_break_snapshot_conflict(self):
        p, a, b, rs, micro, fb = anchors()
        r = fb.selected.observation_revision
        late = replace(r, first_known_time_utc=m(31),
                       retrieved_at_utc=m(32))
        candle = replace(fb.selected, observation_revision=late,
                         retrieved_at_utc=m(32), verified_at_utc=m(33))
        alt = resolve_as_known(candle.market_bar_key, (candle,), m(120))
        self.assertEqual(run(variant_id="B5/E_FAILED_BREAK",
                             failed_break_anchor=alt).state,
                         B5GeometryState.ANCHOR_BLOCKED)


if __name__ == "__main__":
    unittest.main()
