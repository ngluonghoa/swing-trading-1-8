import unittest
from datetime import datetime, timedelta, timezone

from swing_trading.contracts import DecisionStatus, Evidence, SignalDecision, Strategy, ZONE_IDS
from swing_trading.engine import evaluate_unimplemented_zones
from swing_trading.replay import ReplayClock


T0 = datetime(2026, 11, 6, tzinfo=timezone.utc)


class FoundationTests(unittest.TestCase):
    def test_16_unique_zone_ids(self):
        self.assertEqual(len(ZONE_IDS), 16)
        self.assertEqual(len(set(ZONE_IDS)), 16)

    def test_no_unverified_signal_can_be_confirmed_without_evidence(self):
        with self.assertRaises(ValueError):
            SignalDecision("B1", Strategy.SHORT, DecisionStatus.DETECTED)
        with self.assertRaises(ValueError):
            SignalDecision("B1", Strategy.SHORT, DecisionStatus.NOT_DETECTED)

    def test_verified_evidence_allows_typed_decision_but_not_performance_claim(self):
        item = SignalDecision("B1", Strategy.SHORT, DecisionStatus.NOT_DETECTED, (Evidence("fixture", T0, True),))
        self.assertEqual(item.status, DecisionStatus.NOT_DETECTED)

    def test_unimplemented_zones_fail_closed(self):
        result = evaluate_unimplemented_zones(Strategy.SWING, T0)
        self.assertEqual(len(result), 16)
        self.assertTrue(all(r.status == DecisionStatus.UNVERIFIED for r in result))

    def test_replay_clock_requires_utc(self):
        with self.assertRaises(ValueError):
            ReplayClock(datetime(2026, 11, 6))
        with self.assertRaises(ValueError):
            ReplayClock(datetime(2026, 11, 6, tzinfo=timezone(timedelta(hours=7))))

    def test_replay_cannot_move_backwards(self):
        clock = ReplayClock(T0)
        clock.advance_to(T0 + timedelta(minutes=5))
        with self.assertRaises(ValueError):
            clock.advance_to(T0)

    def test_first_known_time_no_lookahead(self):
        clock = ReplayClock(T0)
        self.assertFalse(clock.known(T0 + timedelta(seconds=1)))
        self.assertTrue(clock.known(T0))

if __name__ == "__main__":
    unittest.main()
