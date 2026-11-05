import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from swing_trading.market_data import (
    BarClosure, CanonicalCandle, InstrumentClass, MarketBarKey,
    ObservationRevision, PriceBasis, ProviderObservationKey, Quality, Timeframe
)

T0 = datetime(2026, 11, 6, tzinfo=timezone.utc)


def valid_candle(**overrides):
    key = MarketBarKey(
        "STOCK:HOSE:ABC:registry-v1", "HOSE", InstrumentClass.STOCK,
        Timeframe.M15, "HOSE:20261106:AM", T0, PriceBasis.RAW,
        "calendar-pending-fixture-v1", "aggregation-fixture-v1"
    )
    observation = ProviderObservationKey("FIXTURE", "synthetic://bars", "row-1")
    revision = ObservationRevision("rev-1", "a" * 64, T0, T0)
    fields = dict(
        market_bar_key=key, observation_key=observation,
        revision=revision, bar_end_utc=T0 + timedelta(minutes=15),
        open=Decimal("10"), high=Decimal("11"), low=Decimal("9"),
        close=Decimal("10.5"), volume=0, quality=Quality.VERIFIED,
        closure=BarClosure.CLOSED, observed_minutes=15, expected_minutes=15
    )
    fields.update(overrides)
    return CanonicalCandle(**fields)


class ContractTests(unittest.TestCase):
    def test_source_and_market_identity_are_separate(self):
        a = valid_candle()
        different_source = replace(a, observation_key=ProviderObservationKey("B", "endpoint", "row-1"))
        self.assertEqual(a.market_bar_key, different_source.market_bar_key)
        self.assertNotEqual(a.observation_key, different_source.observation_key)

    def test_verified_zero_volume_is_not_missing(self):
        c = valid_candle()
        self.assertEqual(c.volume, 0)
        self.assertTrue(c.eligible_for_confirmed_signals(T0 + timedelta(minutes=15)))
        self.assertFalse(replace(c, volume=None).eligible_for_confirmed_signals(T0 + timedelta(minutes=15)))

    def test_open_or_unknown_basis_fails_closed(self):
        c = valid_candle()
        self.assertFalse(replace(c, closure=BarClosure.OPEN).eligible_for_confirmed_signals(T0 + timedelta(hours=1)))
        self.assertFalse(replace(c, market_bar_key=replace(c.market_bar_key, price_basis=PriceBasis.UNKNOWN)).eligible_for_confirmed_signals(T0 + timedelta(hours=1)))

    def test_lookahead_revision_is_blocked(self):
        c = valid_candle()
        later = replace(c, revision=replace(c.revision, first_known_time_utc=T0 + timedelta(hours=1), retrieved_at_utc=T0 + timedelta(hours=1)))
        self.assertFalse(later.eligible_for_confirmed_signals(T0 + timedelta(minutes=15)))

    def test_incomplete_minutes_fail_closed(self):
        c = valid_candle()
        self.assertFalse(replace(c, observed_minutes=14).eligible_for_confirmed_signals(T0 + timedelta(hours=1)))

    def test_decimal_integrity(self):
        with self.assertRaises(ValueError):
            valid_candle(high=Decimal("9"))
        with self.assertRaises(TypeError):
            valid_candle(close=float("nan"))
        with self.assertRaises(ValueError):
            valid_candle(open=Decimal("NaN"))

    def test_volume_and_time_guards(self):
        with self.assertRaises(ValueError):
            valid_candle(volume=-1)
        with self.assertRaises(ValueError):
            valid_candle(volume=True)
        with self.assertRaises(ValueError):
            valid_candle(bar_end_utc=T0)

    def test_revision_time_must_be_observed(self):
        with self.assertRaises(ValueError):
            ObservationRevision("rev-1", "a" * 64, T0 + timedelta(seconds=1), T0)

if __name__ == "__main__":
    unittest.main()
