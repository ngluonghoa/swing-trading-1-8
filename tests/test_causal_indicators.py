"""P0.9 synthetic-only ATR14 and RVOL_TF20 causal numerical tests."""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from swing_trading.causal_indicators import (
    CausalIndicatorResult, IndicatorState, VolumeComparisonBar,
    VolumeSessionClass, calculate_rvol_tf20, calculate_wilder_atr14,
)
from swing_trading.market_data import PriceBasis, Timeframe
from swing_trading.source_quality import (
    CoverageState, QualityState, resolve_as_known,
)
from test_source_quality import T, candle


AS_OF = T + timedelta(days=2)
START = T - timedelta(days=55)


def make_bar(
    i, *,
    timeframe=Timeframe.D1, volume=100,
    open_price=Decimal("10"), high=Decimal("12"),
    low=Decimal("8"), close=Decimal("10"),
    start=None, known=None, verified=None,
):
    base = candle()
    begin = start or START + timedelta(days=i)
    end = begin + timedelta(hours=6) if timeframe is Timeframe.D1 else begin + timedelta(minutes=15)
    known = known or end
    retrieved = max(known, end) + timedelta(minutes=1)
    verified = verified or retrieved + timedelta(minutes=1)
    key = replace(base.market_bar_key, timeframe=timeframe,
                  session_period_id="fixture-session-" + str(i),
                  bar_start_utc=begin)
    obs = replace(base.observation_key, market_bar_key=key)
    rev = replace(base.observation_revision, observation_key=obs,
                  source_revision_or_payload_digest="fixture-" + str(i),
                  first_known_time_utc=known, retrieved_at_utc=retrieved)
    row = replace(base, market_bar_key=key, observation_key=obs,
                  observation_revision=rev,
                  bar_end_utc=end, retrieved_at_utc=retrieved,
                  verified_at_utc=verified, open=open_price, high=high,
                  low=low, close=close, volume=volume,
                  observed_minutes=None, expected_minutes=None,
                  source_event_ids=("event-" + str(i),))
    return row


def snap(row, asof=AS_OF):
    return resolve_as_known(row.market_bar_key, (row,), asof)


def d1(n=15, **kwargs):
    return tuple(snap(make_bar(i, **kwargs)) for i in range(n))


def tf20(*, timeframe=Timeframe.D1, volume=100,
         session_class=VolumeSessionClass.DAILY):
    if timeframe is Timeframe.D1:
        rows = [make_bar(i, timeframe=timeframe, volume=volume)
                for i in range(21)]
    else:
        rows = [make_bar(i, timeframe=timeframe, volume=volume,
                         start=START + timedelta(minutes=i*15))
                for i in range(21)]
    def tagged(row):
        return VolumeComparisonBar(snap(row), session_class, "fixture-compare-v1")
    return tagged(rows[-1]), tuple(tagged(x) for x in rows[:-1])


class CausalATR14Tests(unittest.TestCase):
    def test_constant_true_range_has_exact_seed(self):
        result = calculate_wilder_atr14(d1(), as_of_utc=AS_OF)
        self.assertEqual(result.value, Decimal("4"))
        self.assertEqual(result.used_bar_count, 15)
        self.assertEqual(result.state, IndicatorState.COMPUTED_UNCALIBRATED)
        self.assertFalse(result.data_certified)
        self.assertFalse(result.parameter_approved)
        self.assertFalse(result.actionable)

    def test_wilder_recurrence_not_simple_rolling_mean(self):
        rows = list(d1(16))
        last = rows[-1].selected
        changed = replace(last, high=Decimal("20"), low=Decimal("9"),
                          close=Decimal("10"))
        rows[-1] = snap(changed)
        result = calculate_wilder_atr14(tuple(rows), as_of_utc=AS_OF)
        self.assertEqual(result.value, Decimal("4.5"))
        self.assertEqual(result.used_bar_count, 16)

    def test_gap_true_range_uses_previous_close(self):
        rows = list(d1())
        previous = rows[-2].selected
        # The final bar has range 2 but opens far above prior close=10.
        new = replace(rows[-1].selected, high=Decimal("21"),
                      low=Decimal("19"), open=Decimal("20"), close=Decimal("20"))
        rows[-1] = snap(new)
        result = calculate_wilder_atr14(tuple(rows), as_of_utc=AS_OF)
        # 13 times TR4 and one gap TR11 (21-10), over 14
        self.assertEqual(result.value, Decimal("4.5"))

    def test_insufficient_history_and_unknown_history_type(self):
        x = calculate_wilder_atr14(d1(14), as_of_utc=AS_OF)
        self.assertEqual(x.reason, "REQUIRE_15_D1_BARS_FOR_14_TRUE_RANGES")
        self.assertIsNone(x.value)
        y = calculate_wilder_atr14(list(d1()), as_of_utc=AS_OF)
        self.assertEqual(y.reason, "INPUT_MUST_BE_IMMUTABLE_TUPLE")

    def test_zero_atr_disallows_normalization(self):
        x = calculate_wilder_atr14(d1(high=Decimal("10"),low=Decimal("10")),
                                   as_of_utc=AS_OF)
        self.assertEqual(x.reason, "NONPOSITIVE_ATR14_CANNOT_NORMALIZE")

    def test_future_known_cutoff_rejected(self):
        rows = d1()
        last = rows[-1].selected
        r = calculate_wilder_atr14(rows, as_of_utc=AS_OF,
                    known_before_utc=last.verified_at_utc-timedelta(seconds=1))
        self.assertEqual(r.reason, "BAR_NOT_QUALIFIED_AT_CUTOFF")
        self.assertIsNone(r.value)

    def test_unknown_quality_and_partial_coverage_block(self):
        rows = list(d1())
        for bad in (replace(rows[3].selected, quality_state=QualityState.UNVERIFIED),
                    replace(rows[3].selected, coverage_state=CoverageState.SESSION_PARTIAL)):
            with self.subTest(state=bad.quality_state,coverage=bad.coverage_state):
                altered = list(rows)
                altered[3] = snap(bad)
                r = calculate_wilder_atr14(tuple(altered),as_of_utc=AS_OF)
                self.assertEqual(r.state, IndicatorState.BLOCKED)

    def test_missing_volume_and_unverified_entitlement_block(self):
        rows = list(d1())
        bad = replace(rows[0].selected, volume=None)
        rows[0] = snap(bad)
        self.assertEqual(calculate_wilder_atr14(tuple(rows),as_of_utc=AS_OF).state,
                         IndicatorState.BLOCKED)
        rows = list(d1())
        source = replace(rows[0].selected.provenance, entitlement_verified=False)
        rows[0] = snap(replace(rows[0].selected, provenance=source))
        self.assertEqual(calculate_wilder_atr14(tuple(rows),as_of_utc=AS_OF).state,
                         IndicatorState.BLOCKED)

    def test_duplicates_and_unordered_are_rejected(self):
        rows = d1()
        dup = rows[:5] + (rows[4],) + rows[5:]
        x = calculate_wilder_atr14(dup, as_of_utc=AS_OF)
        self.assertEqual(x.reason, "DUPLICATE_OVERLAPPING_OR_UNSORTED_BARS")
        out_of_order = rows[:5] + (rows[6],rows[5]) + rows[7:]
        self.assertEqual(calculate_wilder_atr14(out_of_order,as_of_utc=AS_OF).state,
                         IndicatorState.BLOCKED)

    def test_instrument_provider_price_basis_adjustment_never_mix(self):
        rows = list(d1())
        src = rows[8].selected
        # Strong lineage consistency: source, basis, adjustment, aggregation
        def rekey(obj, **fields):
            k = replace(obj.market_bar_key, **fields)
            o = replace(obj.observation_key, market_bar_key=k)
            v = replace(obj.observation_revision, observation_key=o)
            return replace(obj, market_bar_key=k, observation_key=o,
                           observation_revision=v)
        cases=[
            rekey(src, instrument_id="HOSE:OTHER"),
            rekey(src, price_basis=PriceBasis.ADJUSTED),
            rekey(src, aggregation_policy_version="different"),
            replace(src, observation_key=replace(src.observation_key,
                                                 provider_id="ALT"),
                    observation_revision=replace(src.observation_revision,
                        observation_key=replace(src.observation_key,provider_id="ALT"))),
            replace(src, observation_revision=replace(src.observation_revision,
                                                     adjustment_revision="changed")),
        ]
        for item in cases:
            with self.subTest(item=item.market_bar_key):
                seq=list(rows)
                seq[8]=snap(item)
                self.assertEqual(calculate_wilder_atr14(tuple(seq),as_of_utc=AS_OF).reason,
                                 "SOURCE_BASIS_OR_POLICY_MISMATCH")

    def test_wrong_tf_and_naive_clock_block(self):
        rows = d1()
        original=rows[-1].selected
        key=replace(original.market_bar_key,timeframe=Timeframe.H1)
        obs=replace(original.observation_key,market_bar_key=key)
        rev=replace(original.observation_revision,observation_key=obs)
        alt=replace(original,market_bar_key=key,observation_key=obs,observation_revision=rev)
        seq=rows[:-1]+(snap(alt),)
        self.assertEqual(calculate_wilder_atr14(seq,as_of_utc=AS_OF).reason,"TIMEFRAME_MISMATCH")
        with self.assertRaises(ValueError):
            calculate_wilder_atr14(rows,as_of_utc=AS_OF.replace(tzinfo=None))

    def test_revision_conflict_never_auto_selected(self):
        rows=list(d1())
        c=rows[0].selected
        rev=replace(c.observation_revision,source_revision_or_payload_digest="correction",
                    first_known_time_utc=c.bar_end_utc+timedelta(minutes=2),
                    retrieved_at_utc=c.retrieved_at_utc+timedelta(minutes=2))
        corrected=replace(c,observation_revision=rev,retrieved_at_utc=rev.retrieved_at_utc,
                          verified_at_utc=rev.retrieved_at_utc+timedelta(minutes=1))
        rows[0]=resolve_as_known(c.market_bar_key,(c,corrected),AS_OF)
        self.assertEqual(calculate_wilder_atr14(tuple(rows),as_of_utc=AS_OF).reason,
                         "BAR_NOT_QUALIFIED_AT_CUTOFF")


class CausalRVOLTF20Tests(unittest.TestCase):
    def test_constant_daily_volume_is_one(self):
        target,prior=tf20()
        r=calculate_rvol_tf20(target,prior,as_of_utc=AS_OF)
        self.assertEqual(r.value,Decimal("1"))
        self.assertEqual(r.used_bar_count,21)
        self.assertEqual(r.state,IndicatorState.COMPUTED_UNCALIBRATED)
        self.assertFalse(r.actionable)

    def test_double_volume_is_two_and_target_excluded(self):
        target,prior=tf20()
        target=replace(target,snapshot=snap(replace(target.snapshot.selected,volume=200)))
        self.assertEqual(calculate_rvol_tf20(target,prior,as_of_utc=AS_OF).value,
                         Decimal("2"))

    def test_zero_target_volume_is_valid_zero(self):
        target,prior=tf20()
        target=replace(target,snapshot=snap(replace(target.snapshot.selected,volume=0)))
        self.assertEqual(calculate_rvol_tf20(target,prior,as_of_utc=AS_OF).value,
                         Decimal("0"))

    def test_zero_average_cannot_be_divided(self):
        target,prior=tf20(volume=0)
        self.assertEqual(calculate_rvol_tf20(target,prior,as_of_utc=AS_OF).reason,
                         "ZERO_VOLUME_DENOMINATOR")

    def test_missing_or_extra_comparator_blocks(self):
        target,prior=tf20()
        for seq in (prior[:-1],prior+prior[-1:]):
            with self.subTest(n=len(seq)):
                self.assertEqual(calculate_rvol_tf20(target,seq,as_of_utc=AS_OF).reason,
                                 "REQUIRE_EXACTLY_20_PRIOR_COMPARABLE_BARS")

    def test_timeframe_and_source_identity_must_match(self):
        target,prior=tf20()
        old=prior[5].snapshot.selected
        key=replace(old.market_bar_key,timeframe=Timeframe.H1)
        obs=replace(old.observation_key,market_bar_key=key)
        rev=replace(old.observation_revision,observation_key=obs)
        alt=replace(old,market_bar_key=key,observation_key=obs,observation_revision=rev)
        seq=list(prior)
        seq[5]=replace(seq[5],snapshot=snap(alt))
        self.assertEqual(calculate_rvol_tf20(target,tuple(seq),as_of_utc=AS_OF).reason,
                         "TIMEFRAME_MISMATCH")

    def test_instrument_or_provider_source_cannot_mix(self):
        target,prior=tf20()
        c=prior[0].snapshot.selected
        new=replace(c.observation_key,provider_id="OTHER")
        rev=replace(c.observation_revision,observation_key=new)
        altered=replace(c,observation_key=new,observation_revision=rev)
        seq=(replace(prior[0],snapshot=snap(altered)),)+prior[1:]
        self.assertEqual(calculate_rvol_tf20(target,seq,as_of_utc=AS_OF).state,
                         IndicatorState.BLOCKED)

    def test_session_classes_auction_continuous_and_policy_are_separate(self):
        target,prior=tf20()
        seq=(replace(prior[0],session_class=VolumeSessionClass.CLOSING_AUCTION),)+prior[1:]
        self.assertEqual(calculate_rvol_tf20(target,seq,as_of_utc=AS_OF).reason,
                         "SESSION_CLASS_OR_COMPARISON_POLICY_MISMATCH")
        seq=(replace(prior[0],comparison_policy_version="other"),)+prior[1:]
        self.assertEqual(calculate_rvol_tf20(target,seq,as_of_utc=AS_OF).state,
                         IndicatorState.BLOCKED)

    def test_target_cannot_be_in_history(self):
        target,prior=tf20()
        seq=prior[:-1]+(target,)
        self.assertEqual(calculate_rvol_tf20(target,seq,as_of_utc=AS_OF).state,
                         IndicatorState.BLOCKED)

    def test_comparator_must_be_known_before_target_starts(self):
        target,prior=tf20()
        late=prior[-1].snapshot.selected
        altered=replace(late,verified_at_utc=target.snapshot.selected.bar_end_utc)
        seq=prior[:-1]+(replace(prior[-1],snapshot=snap(altered)),)
        self.assertEqual(calculate_rvol_tf20(target,seq,as_of_utc=AS_OF).reason,
                         "COMPARATOR_NOT_KNOWN_BEFORE_TARGET_START")

    def test_missing_comparator_volume_and_stale_target(self):
        target,prior=tf20()
        bad=replace(prior[0].snapshot.selected,volume=None)
        seq=(replace(prior[0],snapshot=snap(bad)),)+prior[1:]
        self.assertEqual(calculate_rvol_tf20(target,seq,as_of_utc=AS_OF).state,
                         IndicatorState.BLOCKED)
        bad=replace(target.snapshot.selected,quality_state=QualityState.UNVERIFIED)
        self.assertEqual(calculate_rvol_tf20(replace(target,snapshot=snap(bad)),prior,
                                                as_of_utc=AS_OF).reason,
                         "TARGET_NOT_QUALIFIED")

    def test_intraday_requires_matching_non_daily_session_kind(self):
        target,prior=tf20(timeframe=Timeframe.M15,
                          session_class=VolumeSessionClass.CONTINUOUS)
        r=calculate_rvol_tf20(target,prior,as_of_utc=AS_OF)
        self.assertEqual(r.state,IndicatorState.COMPUTED_UNCALIBRATED)
        target=replace(target,session_class=VolumeSessionClass.DAILY)
        self.assertEqual(calculate_rvol_tf20(target,prior,as_of_utc=AS_OF).reason,
                         "INTRADAY_CANNOT_USE_DAILY_SESSION_CLASS")

    def test_no_auto_data_certification_or_approved_parameter(self):
        with self.assertRaises(ValueError):
            CausalIndicatorResult("RVOL_TF20",AS_OF,IndicatorState.COMPUTED_UNCALIBRATED,
                                  "fixture",Decimal("1"),21,"v1",data_certified=True)
        with self.assertRaises(ValueError):
            CausalIndicatorResult("ATR14_D1",AS_OF,IndicatorState.COMPUTED_UNCALIBRATED,
                                  "fixture",Decimal("1"),15,"v1",actionable=True)

    def test_no_partial_closure_or_missing_coverage(self):
        target,prior=tf20()
        for altered in (replace(prior[0].snapshot.selected,
                                coverage_state=CoverageState.SPARSE_UNVERIFIED),
                        replace(prior[0].snapshot.selected,
                                coverage_state=CoverageState.SESSION_PARTIAL)):
            seq=(replace(prior[0],snapshot=snap(altered)),)+prior[1:]
            self.assertEqual(calculate_rvol_tf20(target,seq,as_of_utc=AS_OF).state,
                             IndicatorState.BLOCKED)

    def test_invalid_input_type_or_naive_time(self):
        target,prior=tf20()
        self.assertEqual(calculate_rvol_tf20(target,list(prior),as_of_utc=AS_OF).reason,
                         "INVALID_COMPARATOR_TUPLE")
        with self.assertRaises(ValueError):
            calculate_rvol_tf20(target,prior,as_of_utc=AS_OF.replace(tzinfo=None))


if __name__ == "__main__":
    unittest.main()
