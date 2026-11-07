"""Evidence-scoped VCBS source capability and RAW D1 reference guards.

No VCBS transport, credentials, trading, entitlement check, vendor provenance,
market-data persistence or verified market candles are implemented here.
Direct reads observed on 2026-11-07 are NOT a grant to retain market data.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
import re
from typing import Mapping


_SYMBOL = re.compile(r"^[A-Z0-9-]{1,16}$")


class VcbsFeed(str, Enum):
    DAILY_HISTORY = "vcbs_get_history.D"
    WEEKLY_MONTHLY_HISTORY = "vcbs_get_history.WM"
    SESSION_PRICE_SERIES = "vcbs_get_intraday_history"
    QUOTE_BATCH = "vcbs_get_stock_price"
    TECHNICAL_REFERENCE = "vcbs_get_technical_indicators"
    CORPORATE_ACTION_REFERENCE = "vcbs_get_corporate_events"


class VcbsFetchScope(str, Enum):
    DATE_WINDOW = "DATE_WINDOW"
    CURRENT_SESSION_ONLY = "CURRENT_SESSION_ONLY"
    LATEST_SNAPSHOT = "LATEST_SNAPSHOT"
    REFERENCE = "REFERENCE"


@dataclass(frozen=True)
class VcbsSourceContract:
    feed: VcbsFeed
    fetch_scope: VcbsFetchScope
    raw_ohlcv_candidate: bool
    full_minute_ohlcv: bool = False
    has_change_cursor: bool = False
    provider_revision_verified: bool = False
    authorized_for_retention: bool = False
    source_freshness_verified: bool = False
    eligible_for_actionable_signal: bool = False
    notes: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.feed, VcbsFeed) or not isinstance(self.fetch_scope, VcbsFetchScope):
            raise TypeError("Typed VCBS feed and fetch scope required")
        if any((self.full_minute_ohlcv, self.has_change_cursor,
                self.provider_revision_verified, self.authorized_for_retention,
                self.source_freshness_verified, self.eligible_for_actionable_signal)):
            raise ValueError("VCBS read-only capability audit cannot self-certify data rights, revisions or trades")
        if not self.notes:
            raise ValueError("Explicit capability limitation required")


_CAPABILITIES = {
    VcbsFeed.DAILY_HISTORY: VcbsSourceContract(
        VcbsFeed.DAILY_HISTORY, VcbsFetchScope.DATE_WINDOW, True,
        notes="start_date/end_date bound D1 records, not a changed-since cursor; RAW OHLCV only as reference, calendar/rights unverified"),
    VcbsFeed.WEEKLY_MONTHLY_HISTORY: VcbsSourceContract(
        VcbsFeed.WEEKLY_MONTHLY_HISTORY, VcbsFetchScope.DATE_WINDOW, False,
        notes="W/M are provider-derived aggregates including partial periods; no independently verified parity"),
    VcbsFeed.SESSION_PRICE_SERIES: VcbsSourceContract(
        VcbsFeed.SESSION_PRICE_SERIES, VcbsFetchScope.CURRENT_SESSION_ONLY, False,
        notes="price-by-minute points without complete minute OHLCV; volume snapshots are cumulative; no time-window parameters"),
    VcbsFeed.QUOTE_BATCH: VcbsSourceContract(
        VcbsFeed.QUOTE_BATCH, VcbsFetchScope.LATEST_SNAPSHOT, False,
        notes="up to 20 symbols, board price unit THOUSAND VND, not timestamped verified OHLCV"),
    VcbsFeed.TECHNICAL_REFERENCE: VcbsSourceContract(
        VcbsFeed.TECHNICAL_REFERENCE, VcbsFetchScope.REFERENCE, False,
        notes="provider-computed D/W/M indicators; basis/partial/as-of must be retained; no own candle lineage"),
    VcbsFeed.CORPORATE_ACTION_REFERENCE: VcbsSourceContract(
        VcbsFeed.CORPORATE_ACTION_REFERENCE, VcbsFetchScope.REFERENCE, False,
        notes="ex-dates and adjustments are reference-only; not a trusted authoritative corporate-action revision ledger"),
}


def vcbs_capability(feed: VcbsFeed) -> VcbsSourceContract:
    """Known connector surface, NOT a source contract or permission from VCBS."""
    if not isinstance(feed, VcbsFeed):
        raise TypeError("Explicit VCBS endpoint required")
    return _CAPABILITIES[feed]


def _price(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, str, float)):
        raise ValueError("Number/string price expected")
    try:
        price = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError("Invalid source price") from error
    if not price.is_finite() or price <= 0:
        raise ValueError("Positive finite price required")
    return price


@dataclass(frozen=True)
class VcbsRawDailyReference:
    """Diagnostic-only RAW daily field validation; never a resolved market bar."""
    provider: str
    symbol: str
    trading_date: date
    open_vnd: Decimal
    high_vnd: Decimal
    low_vnd: Decimal
    close_vnd: Decimal
    volume_shares: int
    volume_scope: str
    retrieved_at_utc: datetime
    provisional: bool
    price_basis: str = "RAW"
    quality_verified: bool = False
    lifecycle_closed_verified: bool = False
    rights_verified: bool = False
    retention_allowed: bool = False
    indicators_allowed: bool = False
    backtest_allowed: bool = False
    actionable: bool = False

    def __post_init__(self) -> None:
        if self.provider != "VCBS" or self.price_basis != "RAW":
            raise ValueError("VCBS RAW basis only; no provider/basis conflation")
        if any((self.quality_verified, self.lifecycle_closed_verified, self.rights_verified,
                self.retention_allowed, self.indicators_allowed, self.backtest_allowed,
                self.actionable)):
            raise ValueError("Source row cannot grant validation, data rights or trading authorization")
        if self.volume_scope != "matched":
            raise ValueError("Only clearly labeled matched shares accepted as diagnostic reference")


def inspect_vcbs_raw_daily_row(
    row: Mapping[str, object], *, symbol: str, retrieved_at_utc: datetime,
) -> VcbsRawDailyReference:
    """Validate RAW D1 snapshot fields only; no database or real data cache writes.

    The VCBS `price` field can represent ADJUSTED close while openPrice/highPrice/
    lowPrice remain RAW. Never combine them into a fake adjusted OHLCV candle.
    """
    if not isinstance(row, Mapping):
        raise TypeError("VCBS history row mapping required")
    if not isinstance(symbol, str) or not _SYMBOL.fullmatch(symbol):
        raise ValueError("Exact normalized ticker required")
    if (not isinstance(retrieved_at_utc, datetime) or
            retrieved_at_utc.tzinfo is None or
            retrieved_at_utc.utcoffset() != timezone.utc.utcoffset(retrieved_at_utc)):
        raise ValueError("UTC-aware retrieval time required")
    if row.get("priceBasis") != "raw" or row.get("price_unit") != "VND":
        raise ValueError("VCBS_RAW_D1_PRICE_BASIS_OR_UNIT_UNVERIFIED")
    if row.get("volumeScope") != "matched":
        raise ValueError("VCBS_D1_VOLUME_SCOPE_UNVERIFIED")
    if row.get("provisional", False) not in (True, False):
        raise ValueError("Provisional marker must be boolean")
    if type(row.get("provisional", False)) is not bool:
        raise ValueError("Provisional marker must be boolean")
    try:
        trading_day = date.fromisoformat(row["tradingDate"])
    except (KeyError, ValueError, TypeError) as error:
        raise ValueError("Unambiguous tradingDate required") from error
    o, h, l, c = (_price(row.get(k)) for k in
                   ("openPrice", "highPrice", "lowPrice", "closePrice"))
    if l > min(o, c) or h < max(o, c):
        raise ValueError("Impossible OHLC order")
    if _price(row.get("price")) != c:
        raise ValueError("Mixed adjusted close and RAW OHLC forbidden")
    volume = row.get("volume")
    if isinstance(volume, bool) or not isinstance(volume, int) or volume < 0:
        raise ValueError("Matched volume must be nonnegative integer")
    return VcbsRawDailyReference(
        "VCBS", symbol, trading_day, o, h, l, c, volume, "matched",
        retrieved_at_utc, row.get("provisional", False),
    )
