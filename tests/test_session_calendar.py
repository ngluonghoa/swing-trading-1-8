"""Synthetic-only checks: these timestamps are NOT official market hours."""
import unittest
from datetime import date, datetime, timedelta, timezone
from swing_trading.market_data import InstrumentClass, MarketBarKey, PriceBasis, Timeframe
from swing_trading.session_calendar import CalendarSnapshot, MinuteTimestamp, SessionType, TimestampSemantic, TradingSession

D = date(2026, 11, 6)
T = datetime(2026, 11, 6, 2, 0, tzinfo=timezone.utc)
V = "fixture-v1"

def session(sid="AM", start=T, kind=SessionType.CONTINUOUS, verified=True):
    return TradingSession("HOSE", D, sid, kind, start, start + timedelta(hours=1),
                          V, "fixture-policy", "SYNTHETIC", verified)

def snapshot(items=None, verified=True):
    return CalendarSnapshot("HOSE", D, V, "SYNTHETIC", verified,
                            (session(), session("PM", T + timedelta(hours=2))) if items is None else items)

def bar(start=T, sid="AM", tf=Timeframe.M15, calendar=V):
    return MarketBarKey("HOSE:TEST:v1", "HOSE", InstrumentClass.STOCK, tf, sid,
                        start, PriceBasis.RAW, calendar, "fixture-agg")

class CalendarTests(unittest.TestCase):
    def test_inside_verified_session(self):
        self.assertEqual(snapshot().resolve_intraday(bar(), T + timedelta(minutes=15)).session_id, "AM")

    def test_unverified_does_not_pass(self):
        self.assertIsNone(snapshot(verified=False).resolve_intraday(bar(), T + timedelta(minutes=15)))
        self.assertIsNone(snapshot((session(verified=False),)).resolve_intraday(bar(), T + timedelta(minutes=15)))
        self.assertIsNone(snapshot(()).resolve_intraday(bar(), T + timedelta(minutes=15)))

    def test_cannot_span_gap_or_auction(self):
        s = snapshot()
        self.assertIsNone(s.resolve_intraday(bar(T + timedelta(minutes=45)), T + timedelta(hours=2, minutes=15)))
        auction = snapshot((session("ATC", kind=SessionType.AUCTION),))
        self.assertIsNone(auction.resolve_intraday(bar(sid="ATC"), T + timedelta(minutes=15)))

    def test_identity_and_weekly_boundaries(self):
        s = snapshot()
        self.assertIsNone(s.resolve_intraday(bar(calendar="wrong"), T + timedelta(minutes=15)))
        self.assertIsNone(s.resolve_intraday(bar(sid="PM"), T + timedelta(minutes=15)))
        self.assertIsNone(s.resolve_intraday(bar(tf=Timeframe.W1), T + timedelta(minutes=15)))

    def test_overlap_and_invalid_rules(self):
        with self.assertRaises(ValueError):
            snapshot((session(), session("overlap", T + timedelta(minutes=5))))
        with self.assertRaises(TypeError):
            session(kind="CONTINUOUS")
        with self.assertRaises(ValueError):
            session(start=T.replace(tzinfo=None))

    def test_explicit_endpoint_timestamp_semantics(self):
        self.assertIsNone(MinuteTimestamp(T, TimestampSemantic.UNKNOWN, True).interval_utc())
        self.assertIsNone(MinuteTimestamp(T, TimestampSemantic.START, False).interval_utc())
        self.assertEqual(MinuteTimestamp(T, TimestampSemantic.START, True).interval_utc(),
                         (T, T + timedelta(minutes=1)))
        self.assertEqual(MinuteTimestamp(T, TimestampSemantic.END, True).interval_utc(),
                         (T - timedelta(minutes=1), T))
        with self.assertRaises(TypeError):
            MinuteTimestamp(T, "START", True)

if __name__ == "__main__":
    unittest.main()
