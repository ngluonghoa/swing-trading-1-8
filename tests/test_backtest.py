import unittest
from datetime import datetime, timedelta, timezone

from swing_trading.backtest import BacktestHarness, ExperimentManifest
from swing_trading.causal import CausalMarketEvent
from swing_trading.replay import ReplayClock

T0 = datetime(2026, 11, 6, tzinfo=timezone.utc)


class FakeData:
    def available_events(self, as_of_utc):
        # Deliberately returns future knowledge, so the harness must guard it.
        return (
            CausalMarketEvent("a", "r1", T0, T0, {"close": "1"}),
            CausalMarketEvent("a", "r2", T0, T0 + timedelta(minutes=10), {"close": "2"}),
        )


class BrokenData:
    def available_events(self, as_of_utc):
        return ((T0, "untyped"),)


class FakeRegistry:
    def evaluate(self, zone_id, strategy, as_of_utc):
        raise NotImplementedError("No detector is approved")


class BacktestHarnessTests(unittest.TestCase):
    def test_manifest_rejects_unpinned_source(self):
        with self.assertRaises(ValueError):
            ExperimentManifest("id", T0, "", "v0")

    def test_future_revision_not_visible(self):
        harness = BacktestHarness(ReplayClock(T0), FakeData(), FakeRegistry())
        self.assertEqual([e.revision_id for e in harness.visible_events()], ["r1"])
        harness.clock.advance_to(T0 + timedelta(minutes=10))
        self.assertEqual([e.revision_id for e in harness.visible_events()], ["r1", "r2"])

    def test_untyped_source_fails_closed(self):
        harness = BacktestHarness(ReplayClock(T0), BrokenData(), FakeRegistry())
        with self.assertRaises(TypeError):
            harness.visible_events()

    def test_event_cannot_be_known_before_it_happens(self):
        with self.assertRaises(ValueError):
            CausalMarketEvent("a", "r1", T0 + timedelta(seconds=1), T0, {})

if __name__ == "__main__":
    unittest.main()
