import unittest
from datetime import datetime, timezone

from swing_trading.backtest import BacktestHarness, ExperimentManifest
from swing_trading.replay import ReplayClock


T0 = datetime(2026, 11, 6, tzinfo=timezone.utc)


class FakeData:
    def available_events(self, as_of_utc):
        return tuple(x for x in [(T0, "visible")] if x[0] <= as_of_utc)


class FakeRegistry:
    def evaluate(self, zone_id, strategy, as_of_utc):
        raise NotImplementedError("No detector is approved")


class BacktestHarnessTests(unittest.TestCase):
    def test_manifest_rejects_unpinned_source(self):
        with self.assertRaises(ValueError):
            ExperimentManifest("id", T0, "", "v0")

    def test_visible_events_only_observed_from_market_data_port(self):
        harness = BacktestHarness(ReplayClock(T0), FakeData(), FakeRegistry())
        self.assertEqual(harness.visible_events(), ((T0, "visible"),))

if __name__ == "__main__":
    unittest.main()
