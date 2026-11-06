"""Validation that resolved source conflicts cannot be forged as verified."""
import unittest
from datetime import datetime, timezone

from swing_trading.market_data import InstrumentClass, MarketBarKey, PriceBasis, Timeframe
from swing_trading.source_quality import ResolvedBarSnapshotV12

T = datetime(2026, 11, 6, tzinfo=timezone.utc)
K = MarketBarKey("HOSE:ABC:fixture-v1", "HOSE", InstrumentClass.STOCK,
                 Timeframe.D1, "fixture-day", T, PriceBasis.RAW,
                 "fixture-cal", "fixture-policy")


class ResolutionGuardTests(unittest.TestCase):
    def test_no_source_is_never_selected(self):
        snapshot = ResolvedBarSnapshotV12(K, None, 0, "NO_VISIBLE_REVISION")
        self.assertFalse(snapshot.confirmation_prerequisites(T))

    def test_invalid_status_and_counts_are_rejected(self):
        for count, reason in ((1, "NO_VISIBLE_REVISION"),
                              (0, "SINGLE_VISIBLE_REVISION"),
                              (1, "SOURCE_OR_REVISION_CONFLICT"),
                              (0, "UNVERIFIED_ALIAS"),
                              (True, "NO_VISIBLE_REVISION")):
            with self.subTest(count=count, reason=reason):
                with self.assertRaises(ValueError):
                    ResolvedBarSnapshotV12(K, None, count, reason)

    def test_conflict_never_authorizes_a_selection(self):
        conflict = ResolvedBarSnapshotV12(K, None, 2, "SOURCE_OR_REVISION_CONFLICT")
        self.assertFalse(conflict.confirmation_prerequisites(T))


if __name__ == "__main__":
    unittest.main()
