"""P0.6 synthetic replay tests: M5/M15, dedup, correction, conflict, no-lookahead.

All source/entitlement claims in imported fixtures are synthetic; no SSI feed.
"""
import unittest
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from swing_trading.market_data import Timeframe
from swing_trading.replay_batch import replay_frame, replay_sequence
from swing_trading.source_quality import CoverageState, QualityState
from test_source_quality import T, candle, m


def m5_fixture():
    source = candle()
    key = replace(source.market_bar_key,
                  timeframe=Timeframe.M5, bar_start_utc=m(15))
    observation = replace(source.observation_key, market_bar_key=key)
    revision = replace(source.observation_revision, observation_key=observation,
                       first_known_time_utc=m(20), retrieved_at_utc=m(21))
    return replace(
        source, market_bar_key=key, observation_key=observation,
        observation_revision=revision, bar_end_utc=m(20),
        retrieved_at_utc=m(21), verified_at_utc=m(22),
        observed_minutes=5, expected_minutes=5,
        source_event_ids=("m5-fixture-event",),
    )


class ReplayBatchTests(unittest.TestCase):
    def test_m15_and_m5_replay_in_time_order_and_no_lookahead(self):
        a = candle()  # M15: known 15, retrieved 20, verified 25
        b = m5_fixture()  # M5: known 20, retrieved 21, verified 22
        keys = (b.market_bar_key, a.market_bar_key)
        frames = replay_sequence(keys, (b, a), (m(14), m(18), m(21), m(28)))
        self.assertEqual(len(frames), 4)
        self.assertEqual(
            frames[0].find(a.market_bar_key).resolution.reason,
            "NO_VISIBLE_REVISION")
        self.assertEqual(
            frames[1].find(b.market_bar_key).resolution.reason,
            "NO_VISIBLE_REVISION")
        self.assertFalse(frames[1].find(a.market_bar_key).source_prerequisites_at(m(18)))
        self.assertFalse(frames[2].find(a.market_bar_key).source_prerequisites_at(m(21)))
        self.assertTrue(frames[3].find(a.market_bar_key).source_prerequisites_at(m(28)))
        self.assertTrue(frames[3].find(b.market_bar_key).source_prerequisites_at(m(28)))
        self.assertEqual([item.resolution.market_bar_key.timeframe.value
                          for item in frames[-1].bars], ["M15", "M5"])

    def test_exact_retransmission_is_deduplicated_with_a_receipt_count(self):
        bar = m5_fixture()
        item = replay_frame((bar.market_bar_key,), (bar, bar, bar), m(30)).bars[0]
        self.assertEqual(item.exact_retransmissions_removed, 2)
        self.assertEqual(item.resolution.visible_candidate_count, 1)
        self.assertEqual(item.resolution.selected, bar)
        self.assertTrue(item.source_prerequisites_at(m(30)))
        self.assertFalse(item.revision_identity_collision)

    def test_same_revision_identity_different_payload_is_conflict(self):
        bar = m5_fixture()
        altered = replace(bar, close=Decimal("11.5"),
                          raw_digest_sha256="c" * 64)
        item = replay_frame((bar.market_bar_key,), (bar, altered), m(30)).bars[0]
        self.assertTrue(item.revision_identity_collision)
        self.assertEqual(item.resolution.reason, "SOURCE_OR_REVISION_CONFLICT")
        self.assertEqual(item.resolution.visible_candidate_count, 2)
        self.assertIsNone(item.resolution.selected)
        self.assertFalse(item.source_prerequisites_at(m(30)))

    def test_future_source_correction_cannot_change_prior_as_of_frame(self):
        bar = m5_fixture()
        revision = replace(bar.observation_revision,
                           source_revision_or_payload_digest="r2",
                           first_known_time_utc=m(40), retrieved_at_utc=m(41))
        corrected = replace(bar, observation_revision=revision,
                            retrieved_at_utc=m(41), verified_at_utc=m(42),
                            close=Decimal("11.5"))
        frames = replay_sequence((bar.market_bar_key,), (bar, corrected),
                                 (m(30), m(39), m(40), m(50)))
        self.assertEqual(frames[0].bars[0].resolution.selected, bar)
        self.assertEqual(frames[1].bars[0].resolution.selected, bar)
        self.assertEqual(frames[2].bars[0].resolution.reason,
                         "SOURCE_OR_REVISION_CONFLICT")
        self.assertIsNone(frames[3].bars[0].resolution.selected)
        self.assertFalse(frames[3].bars[0].source_prerequisites_at(m(50)))

    def test_retrieval_and_verification_are_not_silently_backdated(self):
        bar = m5_fixture()
        revision = replace(bar.observation_revision, retrieved_at_utc=m(40))
        late = replace(bar, observation_revision=revision,
                       retrieved_at_utc=m(40), verified_at_utc=m(41))
        item = replay_frame((late.market_bar_key,), (late,), m(30)).bars[0]
        self.assertEqual(item.resolution.selected, late)
        self.assertFalse(item.source_prerequisites_at(m(30)))
        self.assertTrue(replay_frame((late.market_bar_key,), (late,), m(42))
                        .bars[0].source_prerequisites_at(m(42)))

    def test_two_providers_remain_unresolved(self):
        bar = m5_fixture()
        other_obs = replace(bar.observation_key, provider_id="ALT_FIXTURE")
        other_rev = replace(bar.observation_revision, observation_key=other_obs)
        other = replace(bar, observation_key=other_obs, observation_revision=other_rev)
        item = replay_frame((bar.market_bar_key,), (bar, other), m(30)).bars[0]
        self.assertEqual(item.resolution.reason, "SOURCE_OR_REVISION_CONFLICT")
        self.assertFalse(item.revision_identity_collision)
        self.assertFalse(item.source_prerequisites_at(m(30)))

    def test_deterministic_under_input_order_and_duplicate_order(self):
        a = candle()
        b = m5_fixture()
        left = replay_frame((a.market_bar_key, b.market_bar_key),
                            (b, a, b), m(30))
        right = replay_frame((b.market_bar_key, a.market_bar_key),
                             (a, b, b), m(30))
        self.assertEqual(left, right)

    def test_quality_and_coverage_fail_closed_on_m5(self):
        bar = m5_fixture()
        variants = (
            replace(bar, coverage_state=CoverageState.SPARSE_UNVERIFIED),
            replace(bar, coverage_state=CoverageState.UNKNOWN),
            replace(bar, quality_state=QualityState.UNVERIFIED),
            replace(bar, volume=None),
            replace(bar, calendar_cutoff_verified=False),
        )
        for variant in variants:
            with self.subTest(variant=variant):
                item = replay_frame((variant.market_bar_key,), (variant,),
                                    m(30)).bars[0]
                self.assertFalse(item.source_prerequisites_at(m(30)))

    def test_empty_requested_bar_is_unknown_not_a_no_trade_decision(self):
        key = m5_fixture().market_bar_key
        frame = replay_frame((key,), (), m(30))
        self.assertEqual(frame.bars[0].resolution.reason, "NO_VISIBLE_REVISION")
        self.assertFalse(frame.bars[0].source_prerequisites_at(m(30)))

    def test_unrequested_rows_duplicate_keys_and_invalid_collections_fail(self):
        bar = m5_fixture()
        with self.assertRaises(ValueError):
            replay_frame((), (bar,), m(30))
        with self.assertRaises(ValueError):
            replay_frame((bar.market_bar_key, bar.market_bar_key), (bar,), m(30))
        with self.assertRaises(TypeError):
            replay_frame([bar.market_bar_key], (bar,), m(30))
        with self.assertRaises(TypeError):
            replay_frame((bar.market_bar_key,), [bar], m(30))
        with self.assertRaises(KeyError):
            replay_frame((), (), m(30)).find(bar.market_bar_key)

    def test_replay_clock_and_utc_constraints(self):
        bar = m5_fixture()
        with self.assertRaises(ValueError):
            replay_sequence((bar.market_bar_key,), (bar,),
                            (m(30), m(29)))
        with self.assertRaises(ValueError):
            replay_sequence((bar.market_bar_key,), (bar,), ())
        with self.assertRaises(ValueError):
            replay_frame((bar.market_bar_key,), (bar,), m(30).replace(tzinfo=None))


if __name__ == "__main__":
    unittest.main()
