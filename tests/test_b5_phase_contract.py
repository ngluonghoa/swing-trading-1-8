"""P0.7 synthetic B5 phase manifest guards; not market-data/backtest acceptance."""
import unittest
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from swing_trading.b5_phase_contract import (
    B5PhaseReceipt, B5Ingredient, B5PhaseReadiness,
    B5_REQUIRED_INGREDIENTS, B5_PARAMETER_STATUS, B5_PHASE_PREDICATE_REFS,
    inspect_b5_phase_receipts,
)
from swing_trading.contracts import Strategy
from swing_trading.market_data import PriceBasis, Timeframe
from swing_trading.source_quality import resolve_as_known
from test_b5_feature_pack import fixtures, rebar
from test_source_quality import T, candle, m


def resolved(row, as_of=None):
    when = as_of or m(120)
    return resolve_as_known(row.market_bar_key, (row,), when)


def fixture_receipts():
    pivot, breakout, retest = fixtures()
    raw = candle()
    atr = rebar(
        raw, timeframe=Timeframe.D1,
        start=T-timedelta(days=1), end=m(15),
        known=m(15), retrieved=m(20), verified=m(25),
    )
    support = rebar(
        raw, timeframe=Timeframe.H1, start=m(50), end=m(65),
        known=m(65), retrieved=m(66), verified=m(70),
    )
    micro = rebar(
        raw, timeframe=Timeframe.M15, start=m(50), end=m(65),
        known=m(65), retrieved=m(67), verified=m(71),
    )
    volume = rebar(
        raw, timeframe=Timeframe.H1, start=m(65), end=m(80),
        known=m(80), retrieved=m(81), verified=m(85),
    )
    bars = {
        B5Ingredient.RC_PIVOT_RETEST: retest,
        B5Ingredient.RC_PRIOR_ATR: atr,
        B5Ingredient.RE_M15_TRIGGER: retest,
        B5Ingredient.RF_SUPPORT_H1_D1: support,
        B5Ingredient.RF_MICRO_HIGH_BREAK: micro,
        B5Ingredient.RF_VOLUME: volume,
    }
    receipts = []
    for ingredient in B5_REQUIRED_INGREDIENTS:
        bar = bars.get(ingredient)
        is_policy = bar is None
        receipts.append(B5PhaseReceipt(
            ingredient=ingredient,
            anchor_pivot_event_id=pivot.event_id,
            evidence_id=("fixture-" + ingredient.value) if is_policy else bar.source_event_ids[0],
            instrument_id=retest.market_bar_key.instrument_id,
            exchange=retest.market_bar_key.exchange,
            price_basis=retest.market_bar_key.price_basis,
            calendar_version=retest.market_bar_key.calendar_version,
            event_time_utc=m(20) if is_policy else bar.bar_end_utc,
            first_known_time_utc=m(25) if is_policy else bar.verified_at_utc,
            source_revision="fixture-policy-v1" if is_policy
                else bar.observation_revision.source_revision_or_payload_digest,
            method_version="fixture-method-v1",
            bar=None if is_policy else resolved(bar),
            observed_value=Decimal("1") if ingredient is B5Ingredient.RC_PRIOR_ATR else None,
        ))
    return pivot, resolved(breakout), resolved(retest), tuple(receipts)


def evaluate(*, pivot=None, breakout=None, retest=None, receipts=None,
             asof=None, strategy=Strategy.SHORT, variant_id="B5/E_RECLAIM"):
    p, a, b, rs = fixture_receipts()
    return inspect_b5_phase_receipts(
        p if pivot is None else pivot,
        a if breakout is None else breakout,
        b if retest is None else retest,
        rs if receipts is None else receipts,
        strategy=strategy, variant_id=variant_id, as_of_utc=asof or m(120),
    )


def changed(receipts, ingredient, **fields):
    return tuple(replace(item, **fields) if item.ingredient is ingredient else item
                 for item in receipts)


class B5PhaseReceiptTests(unittest.TestCase):
    def test_all_evidence_remains_uncalibrated_not_a_trade(self):
        for strategy in (Strategy.SHORT, Strategy.SWING):
            for variant in ("B5/E_RECLAIM", "B5/E_FAILED_BREAK"):
                with self.subTest(strategy=strategy, variant=variant):
                    result = evaluate(strategy=strategy, variant_id=variant)
                    self.assertEqual(result.state, B5PhaseReadiness.PRESENT_UNCALIBRATED)
                    self.assertEqual(result.observed, B5_REQUIRED_INGREDIENTS)
                    self.assertEqual(result.missing, ())
                    self.assertEqual(result.parameter_status, B5_PARAMETER_STATUS)
                    self.assertFalse(result.actionable)
                    self.assertFalse(result.detector_approved)
                    self.assertNotIn("DETECTED", result.state.value)
        self.assertEqual(len(B5_PHASE_PREDICATE_REFS), 4)

    def test_one_missing_receipt_is_not_reinterpreted_as_false(self):
        p, a, b, rs = fixture_receipts()
        rs = tuple(x for x in rs if x.ingredient is not B5Ingredient.RF_VOLUME)
        output = evaluate(receipts=rs)
        self.assertEqual(output.state, B5PhaseReadiness.RECEIPTS_MISSING)
        self.assertEqual(output.missing, (B5Ingredient.RF_VOLUME,))
        self.assertFalse(output.actionable)

    def test_missing_all_is_unverified_not_a_no_trade(self):
        result = evaluate(receipts=())
        self.assertEqual(result.state, B5PhaseReadiness.RECEIPTS_MISSING)
        self.assertEqual(result.missing, B5_REQUIRED_INGREDIENTS)

    def test_future_claimed_evidence_is_rejected(self):
        p, a, b, rs = fixture_receipts()
        bad = changed(rs, B5Ingredient.RF_RISK_POLICY,
                      event_time_utc=m(130), first_known_time_utc=m(131))
        self.assertEqual(evaluate(receipts=bad).reason, "FUTURE_EVIDENCE")

    def test_bar_known_only_after_verification_and_asof(self):
        p, a, b, rs = fixture_receipts()
        bad = changed(rs, B5Ingredient.RE_M15_TRIGGER,
                      first_known_time_utc=m(49))
        self.assertEqual(evaluate(receipts=bad).reason, "BAR_REVISION_OR_CAUSAL_KNOWLEDGE_MISMATCH")
        self.assertEqual(evaluate(receipts=rs, asof=m(49)).state,
                         B5PhaseReadiness.BASE_UNVERIFIED)

    def test_same_ingredient_never_silently_preferred(self):
        p, a, b, rs = fixture_receipts()
        doubled = rs + (replace(rs[0], evidence_id="different-payload"),)
        self.assertEqual(evaluate(receipts=doubled).reason,
                         "DUPLICATE_OR_CONFLICTING_INGREDIENT")

    def test_wrong_pivot_event_or_instrument_blocks(self):
        p, a, b, rs = fixture_receipts()
        self.assertEqual(evaluate(receipts=changed(rs, B5Ingredient.RC_PIVOT_RETEST,
                                                  anchor_pivot_event_id="other")).reason,
                         "ANCHOR_INSTRUMENT_BASIS_OR_CALENDAR_MISMATCH")
        self.assertEqual(evaluate(receipts=changed(rs, B5Ingredient.RC_WINDOW_POLICY,
                                                  instrument_id="OTHER")).state,
                         B5PhaseReadiness.RECEIPTS_UNVERIFIED)

    def test_cross_exchange_must_not_join(self):
        _, _, _, rs = fixture_receipts()
        self.assertEqual(evaluate(receipts=changed(
            rs, B5Ingredient.RF_VOLUME, exchange="OTHER")).state,
            B5PhaseReadiness.RECEIPTS_UNVERIFIED)

    def test_event_id_must_be_in_source_bar(self):
        _, _, _, rs = fixture_receipts()
        result = evaluate(receipts=changed(rs, B5Ingredient.RF_VOLUME,
                                           evidence_id="not-a-source-event"))
        self.assertEqual(result.reason, "EVIDENCE_EVENT_NOT_IN_SOURCE_BAR")

    def test_cross_basis_and_calendar_must_not_join(self):
        _, _, _, rs = fixture_receipts()
        self.assertEqual(evaluate(receipts=changed(
            rs, B5Ingredient.RF_VOLUME, price_basis=PriceBasis.ADJUSTED)).state,
            B5PhaseReadiness.RECEIPTS_UNVERIFIED)
        self.assertEqual(evaluate(receipts=changed(
            rs, B5Ingredient.RF_RISK_POLICY, calendar_version="future")).state,
            B5PhaseReadiness.RECEIPTS_UNVERIFIED)

    def test_bar_source_revision_must_match_receipt(self):
        _, _, _, rs = fixture_receipts()
        self.assertEqual(evaluate(receipts=changed(
            rs, B5Ingredient.RF_VOLUME, source_revision="other-r2")).reason,
            "BAR_REVISION_OR_CAUSAL_KNOWLEDGE_MISMATCH")

    def test_atr_requires_prior_closed_known_bar_and_positive_value(self):
        _, _, _, rs = fixture_receipts()
        self.assertEqual(evaluate(receipts=changed(
            rs, B5Ingredient.RC_PRIOR_ATR, observed_value=Decimal("0"))).reason,
            "ATR_VALUE_MISSING_OR_NONPOSITIVE")
        self.assertEqual(evaluate(receipts=changed(
            rs, B5Ingredient.RC_PRIOR_ATR, observed_value=None)).state,
            B5PhaseReadiness.RECEIPTS_UNVERIFIED)

    def test_prior_atr_and_window_policy_cannot_be_known_after_retest_starts(self):
        _, _, _, rs = fixture_receipts()
        atr_late = changed(rs, B5Ingredient.RC_PRIOR_ATR,
                           first_known_time_utc=m(35))
        self.assertEqual(evaluate(receipts=atr_late).reason, "ATR_NOT_KNOWN_BEFORE_RETEST")
        policy_late = changed(rs, B5Ingredient.RC_WINDOW_POLICY,
                              first_known_time_utc=m(35))
        self.assertEqual(evaluate(receipts=policy_late).reason,
                         "RETEST_WINDOW_POLICY_KNOWN_TOO_LATE")

    def test_retest_and_trigger_refer_to_same_m15_bar(self):
        _, _, _, rs = fixture_receipts()
        replacement = next(x for x in rs if x.ingredient is B5Ingredient.RF_MICRO_HIGH_BREAK)
        wrong = changed(rs, B5Ingredient.RE_M15_TRIGGER, bar=replacement.bar,
                        event_time_utc=replacement.event_time_utc,
                        first_known_time_utc=replacement.first_known_time_utc,
                        source_revision=replacement.source_revision)
        self.assertEqual(evaluate(receipts=wrong).reason, "RETEST_BAR_NOT_SAME_CAUSAL_EVENT")

    def test_micro_high_cannot_predate_retest(self):
        _, _, _, rs = fixture_receipts()
        original = next(x for x in rs if x.ingredient is B5Ingredient.RE_M15_TRIGGER)
        premature = changed(rs, B5Ingredient.RF_MICRO_HIGH_BREAK, bar=original.bar,
                            event_time_utc=original.event_time_utc,
                            first_known_time_utc=original.first_known_time_utc,
                            source_revision=original.source_revision)
        self.assertEqual(evaluate(receipts=premature).reason, "RF_CLOSED_BAR_NOT_AFTER_RETEST")

    def test_rf_support_and_volume_must_close_after_retest(self):
        p, a, b, rs = fixture_receipts()
        raw = candle()
        early_support = rebar(
            raw, timeframe=Timeframe.H1, start=m(10), end=m(20),
            known=m(20), retrieved=m(21), verified=m(25),
        )
        base = next(x for x in rs if x.ingredient is B5Ingredient.RF_SUPPORT_H1_D1)
        early = replace(base, bar=resolved(early_support),
                        evidence_id=early_support.source_event_ids[0],
                        event_time_utc=early_support.bar_end_utc,
                        first_known_time_utc=early_support.verified_at_utc,
                        source_revision=early_support.observation_revision.source_revision_or_payload_digest)
        altered = tuple(early if x.ingredient is B5Ingredient.RF_SUPPORT_H1_D1
                        else x for x in rs)
        self.assertEqual(evaluate(receipts=altered).reason,
                         "RF_CLOSED_BAR_NOT_AFTER_RETEST")
        base = next(x for x in rs if x.ingredient is B5Ingredient.RF_VOLUME)
        early = replace(base, bar=resolved(early_support),
                        evidence_id=early_support.source_event_ids[0],
                        event_time_utc=early_support.bar_end_utc,
                        first_known_time_utc=early_support.verified_at_utc,
                        source_revision=early_support.observation_revision.source_revision_or_payload_digest)
        altered = tuple(early if x.ingredient is B5Ingredient.RF_VOLUME
                        else x for x in rs)
        self.assertEqual(evaluate(receipts=altered).reason,
                         "RF_CLOSED_BAR_NOT_AFTER_RETEST")

    def test_wrong_timeframe_and_ambiguous_source_conflict_block(self):
        _, _, _, rs = fixture_receipts()
        original = next(x for x in rs if x.ingredient is B5Ingredient.RE_M15_TRIGGER)
        bad_timeframe = changed(rs, B5Ingredient.RF_SUPPORT_H1_D1, bar=original.bar,
                                event_time_utc=original.event_time_utc,
                                first_known_time_utc=original.first_known_time_utc,
                                source_revision=original.source_revision)
        self.assertEqual(evaluate(receipts=bad_timeframe).reason, "BAR_IDENTITY_OR_TIMEFRAME_MISMATCH")
        at = original.bar.selected
        conflict_rev = replace(at.observation_revision,
                               source_revision_or_payload_digest="r2",
                               first_known_time_utc=m(90), retrieved_at_utc=m(92))
        conflict = replace(at, observation_revision=conflict_rev,
                           retrieved_at_utc=m(92), verified_at_utc=m(95))
        ambiguous = resolve_as_known(at.market_bar_key, (at, conflict), m(120))
        self.assertEqual(evaluate(receipts=changed(
            rs, B5Ingredient.RE_M15_TRIGGER, bar=ambiguous)).reason,
            "BAR_NOT_SOURCE_QUALIFIED_AS_OF")

    def test_unverified_base_breakout_remains_blocked(self):
        p, a, b, rs = fixture_receipts()
        self.assertEqual(evaluate(pivot=replace(p, source_verified=False)).state,
                         B5PhaseReadiness.BASE_UNVERIFIED)
        self.assertEqual(evaluate(breakout=resolve_as_known(
            a.market_bar_key, (), m(120))).state, B5PhaseReadiness.BASE_UNVERIFIED)

    def test_policy_receipts_are_not_fake_bars_or_numeric_parameters(self):
        _, _, _, rs = fixture_receipts()
        policy = next(x for x in rs if x.ingredient is B5Ingredient.RF_RISK_POLICY)
        with self.assertRaises(ValueError):
            replace(policy, observed_value=Decimal("1"))
        with self.assertRaises(ValueError):
            replace(policy, method_version="")
        with self.assertRaises(ValueError):
            replace(policy, event_time_utc=m(30), first_known_time_utc=m(20))
        with self.assertRaises(ValueError):
            replace(policy, price_basis=PriceBasis.UNKNOWN)

    def test_variant_inputs_and_immutability_contract(self):
        with self.assertRaises(ValueError):
            evaluate(variant_id="B5/E_AUTO")
        with self.assertRaises(TypeError):
            evaluate(strategy="SHORT")
        with self.assertRaises(TypeError):
            evaluate(receipts=[])
        with self.assertRaises(ValueError):
            evaluate(asof=m(120).replace(tzinfo=None))
        _, _, _, rs = fixture_receipts()
        with self.assertRaises(ValueError):
            replace(rs[0], observed_value=Decimal("NaN"))


if __name__ == "__main__":
    unittest.main()
