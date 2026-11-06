"""P0.12 read-only SSI intraday/daily matched-volume reconciliation.

Endpoint response timestamps remain provider-ambiguous until an independently
documented date/clock policy is approved. A matching total is diagnostic only:
it does not certify every minute, cumulative trade volume, source licence,
exchange calendar, first-known availability or a backtest.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum

from .replay import require_utc


_VN = timezone(timedelta(hours=7))


class SsiTimestampLayout(str, Enum):
    UNKNOWN = "UNKNOWN"
    DAY_MONTH_YEAR = "DAY_MONTH_YEAR"
    MONTH_DAY_YEAR = "MONTH_DAY_YEAR"


class ParityState(str, Enum):
    BLOCKED = "BLOCKED"
    MATCH_UNCERTIFIED = "MATCH_UNCERTIFIED"


@dataclass(frozen=True)
class IntradayMinuteVolume:
    symbol: str
    provider_local_timestamp: str
    matched_volume: int

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("Symbol required")
        if not isinstance(self.provider_local_timestamp, str):
            raise TypeError("Provider timestamp text required")
        if type(self.matched_volume) is not int or self.matched_volume < 0:
            raise ValueError("Matched volume must be a nonnegative int")


@dataclass(frozen=True)
class SsiIntradaySample:
    """Unpaged intraday endpoint diagnostics, not a complete raw-tick feed."""
    symbol: str
    exchange: str
    expected_trading_date: date
    date_layout: SsiTimestampLayout
    endpoint: str
    fetched_at_utc: datetime
    rows: tuple[IntradayMinuteVolume, ...]
    source_snapshot_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("Symbol required")
        if not isinstance(self.exchange, str) or not self.exchange.strip():
            raise ValueError("Exchange required")
        if (not isinstance(self.expected_trading_date, date)
                or isinstance(self.expected_trading_date, datetime)):
            raise TypeError("Local expected trading date required")
        if not isinstance(self.date_layout, SsiTimestampLayout):
            raise TypeError("Explicit SSI timestamp layout required")
        if self.endpoint != "marketdata_list_intraday_stock_infor":
            raise ValueError("Only the specifically observed SSI endpoint is supported")
        require_utc(self.fetched_at_utc)
        if (not isinstance(self.rows, tuple)
                or any(not isinstance(x, IntradayMinuteVolume) for x in self.rows)):
            raise TypeError("Immutable normalized minute-volume rows required")
        if not isinstance(self.source_snapshot_id, str) or not self.source_snapshot_id.strip():
            raise ValueError("Source snapshot ID required")


@dataclass(frozen=True)
class SsiDailyMatchedReceipt:
    symbol: str
    exchange: str
    trading_date: date
    total_match_volume: int | None
    endpoint: str
    fetched_at_utc: datetime
    source_snapshot_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("Symbol required")
        if not isinstance(self.exchange, str) or not self.exchange.strip():
            raise ValueError("Exchange required")
        if not isinstance(self.trading_date, date) or isinstance(self.trading_date, datetime):
            raise TypeError("Local trading date required")
        if (self.total_match_volume is not None and
                (type(self.total_match_volume) is not int or self.total_match_volume < 0)):
            raise ValueError("Total matched volume must be nonnegative int or missing")
        if self.endpoint != "marketdata_list_daily_stock_infor":
            raise ValueError("Only SSI detailed daily match endpoint is supported")
        require_utc(self.fetched_at_utc)
        if not isinstance(self.source_snapshot_id, str) or not self.source_snapshot_id.strip():
            raise ValueError("Daily source snapshot ID required")


@dataclass(frozen=True)
class SsiVolumeParityAudit:
    state: ParityState
    reason: str
    source_row_count: int
    summed_intraday_matched_volume: int | None
    daily_matched_volume: int | None
    observed_first_utc: datetime | None
    observed_last_utc: datetime | None
    timestamp_semantics_certified: bool = False
    minute_coverage_certified: bool = False
    cumulative_volume_certified: bool = False
    market_source_certified: bool = False
    actionable: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.state, ParityState) or not self.reason:
            raise ValueError("Explicit parity state and reason required")
        if type(self.source_row_count) is not int or self.source_row_count < 0:
            raise ValueError("Valid count required")
        for field in ("summed_intraday_matched_volume", "daily_matched_volume"):
            value = getattr(self, field)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("Invalid volume")
        for field in ("observed_first_utc", "observed_last_utc"):
            value = getattr(self, field)
            if value is not None:
                require_utc(value)
        if (self.timestamp_semantics_certified or self.minute_coverage_certified
                or self.cumulative_volume_certified or self.market_source_certified
                or self.actionable):
            raise ValueError("Volume total agreement cannot certify trading source or clock")
        if self.state is ParityState.MATCH_UNCERTIFIED:
            if (self.summed_intraday_matched_volume is None
                    or self.daily_matched_volume != self.summed_intraday_matched_volume
                    or self.source_row_count == 0):
                raise ValueError("Match state requires nonempty equal totals")


def parse_ssi_local_timestamp(value: str, layout: SsiTimestampLayout) -> datetime:
    """Parse only an explicitly declared layout; no locale guessing."""
    if not isinstance(layout, SsiTimestampLayout):
        raise TypeError("Timestamp layout enum required")
    if layout is SsiTimestampLayout.UNKNOWN:
        raise ValueError("SSI provider timestamp policy is unresolved")
    if not isinstance(value, str):
        raise TypeError("Timestamp must be a string")
    pattern = ("%d/%m/%Y %H:%M:%S" if layout is SsiTimestampLayout.DAY_MONTH_YEAR
               else "%m/%d/%Y %H:%M:%S")
    parsed = datetime.strptime(value, pattern)
    if parsed.strftime(pattern) != value:
        raise ValueError("Noncanonical SSI local timestamp")
    return parsed.replace(tzinfo=_VN).astimezone(timezone.utc)


def normalize_ssi_volume(value: str | int) -> int:
    """No float, thousands separator, negative, fractional or bool coercion."""
    if type(value) is int and value >= 0:
        return value
    if type(value) is str and value and value.isascii() and value.isdecimal():
        return int(value)
    raise ValueError("Volume must be a lossless nonnegative integer")


def audit_ssi_intraday_daily_volume(
    intraday: SsiIntradaySample,
    daily: SsiDailyMatchedReceipt,
    *,
    as_of_utc: datetime,
) -> SsiVolumeParityAudit:
    """Compare sampled per-minute totals with exact same-day daily MATCH volume.

    MATCH_UNCERTIFIED is *not* proof intraday minutes are complete: two SSI
    endpoints may share an upstream source, missing no-trade minutes are
    ambiguous, and old values have no historical first-known evidence.
    """
    require_utc(as_of_utc)
    if not isinstance(intraday, SsiIntradaySample) or not isinstance(
        daily, SsiDailyMatchedReceipt
    ):
        raise TypeError("Typed SSI endpoint samples required")

    def finish(reason, state=ParityState.BLOCKED, summed=None, first=None, last=None):
        return SsiVolumeParityAudit(
            state, reason, len(intraday.rows), summed,
            daily.total_match_volume, first, last,
        )

    if (intraday.symbol != daily.symbol or intraday.exchange != daily.exchange
            or intraday.expected_trading_date != daily.trading_date):
        return finish("SYMBOL_EXCHANGE_OR_TRADING_DATE_MISMATCH")
    if intraday.fetched_at_utc > as_of_utc or daily.fetched_at_utc > as_of_utc:
        return finish("ENDPOINT_SAMPLE_NOT_KNOWN_AT_AS_OF")
    if intraday.date_layout is SsiTimestampLayout.UNKNOWN:
        return finish("PROVIDER_DATE_LAYOUT_UNRESOLVED")
    if daily.total_match_volume is None:
        return finish("MISSING_DAILY_MATCHED_VOLUME")
    if not intraday.rows:
        return finish("EMPTY_INTRADAY_IS_NOT_ZERO_VOLUME_OR_CLOSED_SESSION")

    seen = set()
    times = []
    total = 0
    for row in intraday.rows:
        if row.symbol != intraday.symbol:
            return finish("INTRADAY_SYMBOL_MISMATCH")
        try:
            dt = parse_ssi_local_timestamp(row.provider_local_timestamp,
                                           intraday.date_layout)
        except ValueError:
            return finish("BAD_OR_MISMATCHED_PROVIDER_DATE_LAYOUT")
        if dt.astimezone(_VN).date() != intraday.expected_trading_date:
            return finish("INTRADAY_TIMESTAMP_NOT_REQUESTED_TRADING_DATE")
        if dt > as_of_utc:
            return finish("FUTURE_MARKET_TIMESTAMP")
        if dt in seen:
            return finish("DUPLICATE_INTRADAY_TIME_SLOT")
        seen.add(dt)
        times.append(dt)
        total += row.matched_volume
    first, last = min(times), max(times)
    if total != daily.total_match_volume:
        return finish("INTRADAY_DAILY_MATCHED_VOLUME_MISMATCH",
                      summed=total, first=first, last=last)
    return finish("TOTAL_MATCH_EQUAL_BUT_MINUTE_COVERAGE_UNCERTIFIED",
                  state=ParityState.MATCH_UNCERTIFIED,
                  summed=total, first=first, last=last)
