"""P0.1: versioned exchange-session boundaries; synthetic fixtures only.

No official session hours, holiday dates, source entitlement or auction semantics
are inferred. Source: Drive 05_GD3_DATA_CONTRACT §2–4.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from zoneinfo import ZoneInfo

from .market_data import MarketBarKey, Timeframe
from .replay import require_utc

_VN = ZoneInfo("Asia/Ho_Chi_Minh")
_EXCHANGES = frozenset(("HOSE", "HNX", "UPCOM", "INDEX"))
_INTRADAY = frozenset((Timeframe.M1, Timeframe.M5, Timeframe.M15,
                      Timeframe.M30, Timeframe.H1))


class SessionType(str, Enum):
    CONTINUOUS = "CONTINUOUS"
    AUCTION = "AUCTION"
    AFTER_HOURS = "AFTER_HOURS"
    BOUNDARY = "BOUNDARY"


class TimestampSemantic(str, Enum):
    START = "START"
    END = "END"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class TradingSession:
    exchange: str
    trading_day: date
    session_id: str
    session_type: SessionType
    start_utc: datetime
    end_utc: datetime
    calendar_version: str
    provisional_rule: str
    source: str
    verified: bool

    def __post_init__(self):
        require_utc(self.start_utc)
        require_utc(self.end_utc)
        if self.exchange not in _EXCHANGES or type(self.trading_day) is not date:
            raise ValueError("Unknown exchange or trading_day")
        if not isinstance(self.session_type, SessionType) or type(self.verified) is not bool:
            raise TypeError("Session type and verification status must be explicit")
        if not all((self.session_id, self.calendar_version, self.provisional_rule, self.source)):
            raise ValueError("Missing session identity or provenance")
        if self.end_utc <= self.start_utc:
            raise ValueError("Session end must follow start")
        if self.start_utc.astimezone(_VN).date() != self.trading_day:
            raise ValueError("Session-local trading date mismatch")


@dataclass(frozen=True)
class CalendarSnapshot:
    exchange: str
    trading_day: date
    version: str
    source: str
    verified: bool
    sessions: tuple[TradingSession, ...]

    def __post_init__(self):
        if self.exchange not in _EXCHANGES or type(self.trading_day) is not date:
            raise ValueError("Unknown exchange or trading_day")
        if not self.version or not self.source or type(self.verified) is not bool:
            raise ValueError("Version, source and explicit verification required")
        if not isinstance(self.sessions, tuple):
            raise TypeError("Immutable session collection required")
        ordered = sorted(self.sessions, key=lambda s: s.start_utc)
        ids = set()
        for s in ordered:
            if not isinstance(s, TradingSession):
                raise TypeError("Invalid session")
            if (s.exchange, s.trading_day, s.calendar_version) != (
                self.exchange, self.trading_day, self.version
            ):
                raise ValueError("Mixed session identity/version")
            if s.session_id in ids:
                raise ValueError("Duplicate session identifier")
            ids.add(s.session_id)
        if any(b.start_utc < a.end_utc for a, b in zip(ordered, ordered[1:])):
            raise ValueError("Overlapping session periods need review")

    def resolve_intraday(self, key: MarketBarKey, end_utc: datetime) -> TradingSession | None:
        """Structural mapping only: NOT sufficient to authorize a trade."""
        if not isinstance(key, MarketBarKey):
            raise TypeError("Expected MarketBarKey")
        require_utc(end_utc)
        if end_utc <= key.bar_start_utc:
            raise ValueError("Invalid interval")
        if (not self.verified or key.timeframe not in _INTRADAY
            or key.exchange != self.exchange or key.calendar_version != self.version
            or key.bar_start_utc.astimezone(_VN).date() != self.trading_day):
            return None
        eligible = [
            s for s in self.sessions
            if s.verified and s.session_type is SessionType.CONTINUOUS
            and s.session_id == key.session_period_id
            and s.start_utc <= key.bar_start_utc and end_utc <= s.end_utc
        ]
        return eligible[0] if len(eligible) == 1 else None


@dataclass(frozen=True)
class MinuteTimestamp:
    event_time_utc: datetime
    semantic: TimestampSemantic
    verified: bool

    def __post_init__(self):
        require_utc(self.event_time_utc)
        if not isinstance(self.semantic, TimestampSemantic) or type(self.verified) is not bool:
            raise TypeError("Endpoint semantic and verification must be explicit")

    def interval_utc(self) -> tuple[datetime, datetime] | None:
        if not self.verified or self.semantic is TimestampSemantic.UNKNOWN:
            return None
        if self.semantic is TimestampSemantic.START:
            return self.event_time_utc, self.event_time_utc + timedelta(minutes=1)
        return self.event_time_utc - timedelta(minutes=1), self.event_time_utc
