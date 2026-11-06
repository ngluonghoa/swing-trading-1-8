"""Synthetic B5 evidence feature tests; not detector or historical backtest."""
import unittest
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from swing_trading.b5_feature_pack import (
    B5FeatureState, PriorPivot, extract_b5_features,
)
from swing_trading.contracts import Strategy
from swing_trading.market_data import PriceBasis, Timeframe
from swing_trading.source_quality import (
    CoverageState, QualityState, resolve_as_known,
)
from test_source_quality import T, candle, m


def rebar(original, *, timeframe, start, end, known, retrieved, verified,
          close=Decimal("11"), low=Decimal("9"), open_price=Decimal("10")):
    k = replace(original.market_bar_key, timeframe=timeframe, bar_start_utc=start)
    obs = replace(original.observation_key, market_bar_key=k)
    rev = replace(original.observation_revision, observation_key=obs,
                  first_known_time_utc=known, retrieved_at_utc=retrieved)
    return replace(
        original, market_bar_key=k, observation_key=obs, observation_revision=rev,
        bar_end_utc=end, retrieved_at_utc=retrieved, verified_at_utc=verified,
        open=open_price, high=Decimal("12"), low=low, close=close,
        observed_minutes=None, expected_minutes=None,
    )


def fixtures():
    raw = candle()
    breakout = rebar(raw, timeframe=Timeframe.D1, start=T-timedelta(days=1),
                     end=m(15), known=m(15), retrieved=m(20), verified=m(25))
    retest = rebar(raw, timeframe=Timeframe.M15, start=m(30),
                   end=m(45), known=m(45), retrieved=m(48), verified=m(50),
                   close=Decimal("10.5"), low=Decimal("9.8"))
    pivot = PriorPivot(
        breakout.market_bar_key.instrument_id, "pivot-fixture-1",
        T-timedelta(hours=1), T-timedelta(minutes=30),
        Decimal("10"), "fixture-pivot-v1", True,
    )
    return pivot, breakout, retest


def assessment(pivot=None, breakout=None, retest=None, *, asof=None,
               strategy=Strategy.SHORT):
    p,a,b = fixtures()
    p = p if pivot is None else pivot
    a = a if breakout is None else breakout
    b = b if retest is None else retest
    when = asof or m(60)
    return extract_b5_features(
        p, resolve_as_known(a.market_bar_key, (a,), when),
        resolve_as_known(b.market_bar_key, (b,), when),
        strategy=strategy, as_of_utc=when,
    )


class B5FeatureTests(unittest.TestCase):
    def test_feature_values_do_not_become_signal_or_trade(self):
        for strategy in (Strategy.SHORT, Strategy.SWING):
            with self.subTest(strategy=strategy):
                result = assessment(strategy=strategy)
                self.assertEqual(result.state, B5FeatureState.EXTRACTED_UNCALIBRATED)
                self.assertEqual(result.reason, "SPEC_PENDING_B5_RC_RE_RF_P01_P17")
                self.assertEqual(result.features.breakout_above_pivot, Decimal("1"))
                self.assertEqual(result.features.retest_close_to_pivot, Decimal("0.5"))
                self.assertEqual(result.features.retest_low_to_pivot, Decimal("-0.2"))
                self.assertEqual(result.features.retest_intrabar_change, Decimal("0.5"))
                self.assertEqual(result.features.prior_pivot_event_id, "pivot-fixture-1")
                self.assertFalse(result.detector_approved)
                self.assertFalse(result.actionable)

    def test_before_retest_known_never_extracts_future_candle(self):
        p,a,b=fixtures()
        result=extract_b5_features(
            p, resolve_as_known(a.market_bar_key,(a,),m(40)),
            resolve_as_known(b.market_bar_key,(b,),m(40)),
            strategy=Strategy.SHORT,as_of_utc=m(40))
        self.assertEqual(result.state,B5FeatureState.DATA_UNVERIFIED)
        self.assertIsNone(result.features)

    def test_before_verification_cannot_extract_lookahead(self):
        result=assessment(asof=m(49))
        self.assertEqual(result.state,B5FeatureState.DATA_UNVERIFIED)
        self.assertIsNone(result.features)

    def test_source_flags_or_unknown_coverage_block(self):
        p,a,b=fixtures()
        for other in (replace(b,quality_state=QualityState.UNVERIFIED),
                      replace(b,coverage_state=CoverageState.UNKNOWN),
                      replace(b,calendar_cutoff_verified=False),
                      replace(b,volume=None)):
            with self.subTest(source=other):
                result=assessment(retest=other)
                self.assertEqual(result.state,B5FeatureState.DATA_UNVERIFIED)
                self.assertFalse(result.actionable)

    def test_source_revision_conflict_remains_blocked(self):
        p,a,b=fixtures()
        new_rev=replace(b.observation_revision,
                        source_revision_or_payload_digest="future-correction",
                        first_known_time_utc=m(70),retrieved_at_utc=m(72))
        corrected=replace(b,observation_revision=new_rev,
                          retrieved_at_utc=m(72),verified_at_utc=m(73))
        earlier=extract_b5_features(
            p,resolve_as_known(a.market_bar_key,(a,),m(60)),
            resolve_as_known(b.market_bar_key,(b,corrected),m(60)),
            strategy=Strategy.SHORT,as_of_utc=m(60))
        later=extract_b5_features(
            p,resolve_as_known(a.market_bar_key,(a,),m(80)),
            resolve_as_known(b.market_bar_key,(b,corrected),m(80)),
            strategy=Strategy.SHORT,as_of_utc=m(80))
        self.assertEqual(earlier.state,B5FeatureState.EXTRACTED_UNCALIBRATED)
        self.assertEqual(later.state,B5FeatureState.DATA_UNVERIFIED)

    def test_mixed_identity_and_price_basis_fail_closed(self):
        p,a,b=fixtures()
        self.assertEqual(assessment(pivot=replace(p,instrument_id="HOSE:OTHER")).reason,
                         "MIXED_INSTRUMENT_IDENTITY")
        new_key=replace(b.market_bar_key,price_basis=PriceBasis.ADJUSTED)
        new_obs=replace(b.observation_key,market_bar_key=new_key)
        new_rev=replace(b.observation_revision,observation_key=new_obs)
        altered=replace(b,market_bar_key=new_key,observation_key=new_obs,
                        observation_revision=new_rev)
        self.assertEqual(assessment(retest=altered).reason,
                         "BASIS_OR_CALENDAR_VERSION_MISMATCH")

    def test_missing_and_unverified_prior_pivot_never_allowed(self):
        p,a,b=fixtures()
        self.assertEqual(assessment(pivot=replace(p,source_verified=False)).state,
                         B5FeatureState.DATA_UNVERIFIED)
        result=extract_b5_features(
            None,resolve_as_known(a.market_bar_key,(a,),m(60)),
            resolve_as_known(b.market_bar_key,(b,),m(60)),
            strategy=Strategy.SHORT,as_of_utc=m(60))
        self.assertEqual(result.state,B5FeatureState.INPUT_BLOCKED)

    def test_late_known_pivot_and_late_breakout_revision_rejected(self):
        p,a,b=fixtures()
        self.assertEqual(assessment(pivot=replace(
            p,first_known_time_utc=m(18))).reason,
            "LATE_PIVOT_OR_BREAKOUT_KNOWLEDGE")
        later_rev=replace(a.observation_revision,first_known_time_utc=m(35),
                          retrieved_at_utc=m(36))
        a2=replace(a,observation_revision=later_rev,retrieved_at_utc=m(36),
                   verified_at_utc=m(37))
        self.assertEqual(assessment(breakout=a2).reason,
                         "LATE_PIVOT_OR_BREAKOUT_KNOWLEDGE")

    def test_wrong_b5_timeframes_and_sequence_rejected(self):
        p,a,b=fixtures()
        wrong=replace(a.market_bar_key,timeframe=Timeframe.M5)
        obs=replace(a.observation_key,market_bar_key=wrong)
        rev=replace(a.observation_revision,observation_key=obs)
        a2=replace(a,market_bar_key=wrong,observation_key=obs,
                   observation_revision=rev)
        self.assertEqual(assessment(breakout=a2).state,
                         B5FeatureState.INPUT_BLOCKED)
        self.assertEqual(assessment(pivot=replace(
            p,event_time_utc=m(14),first_known_time_utc=m(18))).state,
                         B5FeatureState.DATA_UNVERIFIED)

    def test_no_prior_breakout_is_precondition_not_market_signal(self):
        p,a,b=fixtures()
        no_breakout=replace(a,close=Decimal("10"))
        result=assessment(breakout=no_breakout)
        self.assertEqual(result.state,B5FeatureState.PRECONDITION_NOT_MET)
        self.assertIsNone(result.features)
        self.assertFalse(result.actionable)

    def test_type_and_utc_validation(self):
        p,a,b=fixtures()
        with self.assertRaises(ValueError):
            extract_b5_features(p,None,None,strategy=Strategy.SHORT,
                                as_of_utc=m(60).replace(tzinfo=None))
        with self.assertRaises(TypeError):
            extract_b5_features(p,None,None,strategy="SHORT",as_of_utc=m(60))
        with self.assertRaises(ValueError):
            replace(p,price=Decimal("NaN"))
        with self.assertRaises(ValueError):
            replace(p,first_known_time_utc=p.event_time_utc-timedelta(seconds=1))


if __name__=="__main__":
    unittest.main()
