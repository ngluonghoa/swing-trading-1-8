"""Strict, intentionally partial v1.2 market identity and candle-quality contracts.

Source: 05_GD3_DATA_CONTRACT_SMART_CACHE_ARCH §2/17-18. This module is
FOUNDATION_ONLY: it does not certify provider timestamps, settlement,
calendar correctness or data licensing.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from .replay import require_utc


class InstrumentClass(str, Enum):
    STOCK = "STOCK"
    INDEX = "INDEX"


class Timeframe(str, Enum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    D1 = "D1"
    W1 = "W1"


class PriceBasis(str, Enum):
    RAW = "RAW"
    ADJUSTED = "ADJUSTED"
    UNKNOWN = "UNKNOWN"


class BarClosure(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    UNKNOWN = "UNKNOWN"


class Quality(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    MISSING = "MISSING"


@dataclass(frozen=True)
class MarketBarKey:
    instrument_id: str
    exchange: str
    instrument_class: InstrumentClass
    timeframe: Timeframe
    session_period_id: str
    bar_start_utc: datetime
    price_basis: PriceBasis
    calendar_version: str
    aggregation_policy_version: str

    def __post_init__(self) -> None:
        require_utc(self.bar_start_utc)
        if not all((self.instrument_id, self.exchange, self.session_period_id,
                    self.calendar_version, self.aggregation_policy_version)):
            raise ValueError("MarketBarKey needs versioned instrument, session and policies")
        if not isinstance(self.instrument_class, InstrumentClass):
            raise TypeError("instrument_class must be InstrumentClass")
        if not isinstance(self.timeframe, Timeframe):
            raise TypeError("timeframe must be Timeframe")
        if not isinstance(self.price_basis, PriceBasis):
            raise TypeError("price_basis must be PriceBasis")


@dataclass(frozen=True)
class ProviderObservationKey:
    provider_id: str
    endpoint: str
    source_record_id: str

    def __post_init__(self) -> None:
        if not all((self.provider_id, self.endpoint, self.source_record_id)):
            raise ValueError("Every observation requires verifiable source identity")


@dataclass(frozen=True)
class ObservationRevision:
    revision_id: str
    raw_digest_sha256: str
    first_known_time_utc: datetime
    retrieved_at_utc: datetime

    def __post_init__(self) -> None:
        require_utc(self.first_known_time_utc)
        require_utc(self.retrieved_at_utc)
        if not self.revision_id or len(self.raw_digest_sha256) != 64 or any(
            c not in "0123456789abcdef" for c in self.raw_digest_sha256
        ):
            raise ValueError("Revision requires ID and lowercase SHA-256")
        if self.first_known_time_utc > self.retrieved_at_utc:
            raise ValueError("First-known time cannot follow retrieval time")


@dataclass(frozen=True)
class CanonicalCandle:
    market_bar_key: MarketBarKey
    observation_key: ProviderObservationKey
    revision: ObservationRevision
    bar_end_utc: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int | None
    quality: Quality
    closure: BarClosure
    observed_minutes: int | None = None
    expected_minutes: int | None = None
    matched_value: Decimal | None = None

    def __post_init__(self) -> None:
        require_utc(self.bar_end_utc)
        if self.bar_end_utc <= self.market_bar_key.bar_start_utc:
            raise ValueError("bar_end_utc must follow bar_start_utc")
        values = (self.open, self.high, self.low, self.close)
        if any(not isinstance(v, Decimal) or not v.is_finite() for v in values):
            raise TypeError("OHLC must be finite Decimal values")
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close):
            raise ValueError("OHLC ordering violation")
        if self.low < 0:
            raise ValueError("Negative prices not supported")
        if self.volume is not None and (type(self.volume) is not int or self.volume < 0):
            raise ValueError("Volume must be nonnegative integer or unknown (None)")
        if self.matched_value is not None and (
            not isinstance(self.matched_value, Decimal)
            or not self.matched_value.is_finite()
            or self.matched_value < 0
        ):
            raise ValueError("Matched value must be finite nonnegative Decimal or unknown")
        for minutes in (self.observed_minutes, self.expected_minutes):
            if minutes is not None and (type(minutes) is not int or minutes < 0):
                raise ValueError("Minute counts must be nonnegative integers")
        if (self.observed_minutes is not None and self.expected_minutes is not None
                and self.observed_minutes > self.expected_minutes):
            raise ValueError("Observed minute count exceeds expected count")
        if not isinstance(self.quality, Quality) or not isinstance(self.closure, BarClosure):
            raise TypeError("quality and closure must be explicit enums")

    def eligible_for_confirmed_signals(self, as_of_utc: datetime) -> bool:
        """Necessary checks only; NOT sufficient for full ACTION_ELIGIBLE gate."""
        require_utc(as_of_utc)
        return (
            self.quality is Quality.VERIFIED
            and self.closure is BarClosure.CLOSED
            and self.market_bar_key.price_basis is not PriceBasis.UNKNOWN
            and self.volume is not None
            and self.bar_end_utc <= as_of_utc
            and self.revision.first_known_time_utc <= as_of_utc
            and (self.observed_minutes is None or self.expected_minutes is None
                 or self.observed_minutes == self.expected_minutes)
        )
