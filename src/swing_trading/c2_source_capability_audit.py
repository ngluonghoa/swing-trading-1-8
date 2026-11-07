"""C2A metadata-only, read-only audit of connected SSI/DNSE/VCBS MCP surfaces.

This module neither calls providers nor stores provider rows. Endpoint contracts
are observed connector interfaces, NOT authenticated vendor entitlements or
certified market-data capabilities. No rights, caching, indicators or trades.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import Enum
import json
from collections.abc import Mapping

from .incremental_cache import Provider
from .cache_fetch_planner import SourceCapability

MAX_SERIALIZED_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_ROWS = 10000


class ConnectedEndpoint(str, Enum):
    SSI_D1_DETAILED = "marketdata_list_daily_stock_infor"
    SSI_INTRADAY_SESSION = "marketdata_list_intraday_stock_infor.range_1d"
    SSI_INTRADAY_LATEST = "marketdata_list_intraday_stock_infor.latest"
    DNSE_D1_HISTORY = "price_get_history"
    VCBS_D1_WINDOW = "vcbs_get_history.D"
    VCBS_INTRADAY_PRICE_POINTS = "vcbs_get_intraday_history"
    VCBS_QUOTE_BATCH = "vcbs_get_stock_price"


class DataNeed(str, Enum):
    D1_OHLCV = "D1_OHLCV"
    MINUTE_OHLCV = "MINUTE_OHLCV"
    MINUTE_PRICE_REFERENCE = "MINUTE_PRICE_REFERENCE"
    QUOTE_REFERENCE = "QUOTE_REFERENCE"


class FetchBoundary(str, Enum):
    COARSE_DAY_RANGE = "COARSE_DAY_RANGE"
    WHOLE_SESSION = "WHOLE_SESSION"
    LATEST_SINGLE = "LATEST_SINGLE"
    FULL_D1_HISTORY = "FULL_D1_HISTORY"
    CALENDAR_DATE_WINDOW = "CALENDAR_DATE_WINDOW"
    CURRENT_SESSION_PRICE_SERIES = "CURRENT_SESSION_PRICE_SERIES"
    QUOTE_BATCH = "QUOTE_BATCH"


class RefreshVerdict(str, Enum):
    REVALIDATE_DATE_WINDOW = "REVALIDATE_DATE_WINDOW"
    REFETCH_WHOLE_SESSION = "REFETCH_WHOLE_SESSION"
    REFETCH_FULL_HISTORY = "REFETCH_FULL_HISTORY"
    REFETCH_COARSE_DAILY_RANGE = "REFETCH_COARSE_DAILY_RANGE"
    REFERENCE_SNAPSHOT = "REFERENCE_SNAPSHOT"
    BLOCKED = "BLOCKED"


class ProbeState(str, Enum):
    SHAPE_RETURNED = "SHAPE_RETURNED"
    EMPTY_UNVERIFIED = "EMPTY_UNVERIFIED"
    SOURCE_ERROR = "SOURCE_ERROR"
    SCHEMA_REJECTED = "SCHEMA_REJECTED"


@dataclass(frozen=True)
class EndpointContract:
    endpoint: ConnectedEndpoint
    provider: Provider
    need: DataNeed
    boundary: FetchBoundary
    price_units: str
    bounded_calendar_dates: bool
    exact_subday_range: bool = False
    source_change_cursor: bool = False
    vendor_revision_provenance: bool = False
    qualified_minute_ohlcv: bool = False
    historical_retention_authorized: bool = False
    exchange_freshness_verified: bool = False
    trading_actionable: bool = False

    def __post_init__(self) -> None:
        if (not isinstance(self.endpoint, ConnectedEndpoint)
                or not isinstance(self.provider, Provider)
                or not isinstance(self.need, DataNeed)
                or not isinstance(self.boundary, FetchBoundary)):
            raise TypeError("Typed endpoint contract required")
        if self.price_units not in ("VND", "THOUSAND_VND"):
            raise ValueError("Explicit observed price units required")
        if any((self.exact_subday_range, self.source_change_cursor,
                self.vendor_revision_provenance, self.qualified_minute_ohlcv,
                self.historical_retention_authorized, self.exchange_freshness_verified,
                self.trading_actionable)):
            raise ValueError("C2A observed MCP schema cannot certify vendor capability, rights or trades")


_CONTRACTS = {
    ConnectedEndpoint.SSI_D1_DETAILED: EndpointContract(
        ConnectedEndpoint.SSI_D1_DETAILED, Provider.SSI, DataNeed.D1_OHLCV,
        FetchBoundary.COARSE_DAY_RANGE, "VND", False),
    ConnectedEndpoint.SSI_INTRADAY_SESSION: EndpointContract(
        ConnectedEndpoint.SSI_INTRADAY_SESSION, Provider.SSI, DataNeed.MINUTE_OHLCV,
        FetchBoundary.WHOLE_SESSION, "VND", False),
    ConnectedEndpoint.SSI_INTRADAY_LATEST: EndpointContract(
        ConnectedEndpoint.SSI_INTRADAY_LATEST, Provider.SSI, DataNeed.QUOTE_REFERENCE,
        FetchBoundary.LATEST_SINGLE, "VND", False),
    ConnectedEndpoint.DNSE_D1_HISTORY: EndpointContract(
        ConnectedEndpoint.DNSE_D1_HISTORY, Provider.DNSE, DataNeed.D1_OHLCV,
        FetchBoundary.FULL_D1_HISTORY, "THOUSAND_VND", False),
    ConnectedEndpoint.VCBS_D1_WINDOW: EndpointContract(
        ConnectedEndpoint.VCBS_D1_WINDOW, Provider.VCBS, DataNeed.D1_OHLCV,
        FetchBoundary.CALENDAR_DATE_WINDOW, "VND", True),
    ConnectedEndpoint.VCBS_INTRADAY_PRICE_POINTS: EndpointContract(
        ConnectedEndpoint.VCBS_INTRADAY_PRICE_POINTS, Provider.VCBS, DataNeed.MINUTE_PRICE_REFERENCE,
        FetchBoundary.CURRENT_SESSION_PRICE_SERIES, "VND", False),
    ConnectedEndpoint.VCBS_QUOTE_BATCH: EndpointContract(
        ConnectedEndpoint.VCBS_QUOTE_BATCH, Provider.VCBS, DataNeed.QUOTE_REFERENCE,
        FetchBoundary.QUOTE_BATCH, "THOUSAND_VND", False),
}


def endpoint_contract(endpoint: ConnectedEndpoint) -> EndpointContract:
    """Connected MCP *argument shape* only; not an authorization/capability grant."""
    if not isinstance(endpoint, ConnectedEndpoint):
        raise TypeError("Typed connected endpoint required")
    return _CONTRACTS[endpoint]


def conservative_c1_m1_capability(endpoint: ConnectedEndpoint) -> SourceCapability:
    """Map *connected MCP request arguments* to the existing C1 M1 planner.

    Only SSI's DAY-granularity intraday surface can be contemplated as a
    FULL_SESSION candidate. This is NOT licence/retention permission and it
    never implies native M1 closure/quality certification. Do not map VCBS's
    D1 date-window to M1 WINDOWED, or SSI latest/VCBS price points to M1 bars.
    """
    endpoint_contract(endpoint)
    if endpoint is ConnectedEndpoint.SSI_INTRADAY_SESSION:
        return SourceCapability.FULL_SESSION
    return SourceCapability.UNKNOWN


@dataclass(frozen=True)
class ReadOnlyRefreshAdvice:
    endpoint: ConnectedEndpoint
    need: DataNeed
    verdict: RefreshVerdict
    reason: str
    supports_delta_from_last_change: bool = False
    metadata_only: bool = True
    source_authority_verified: bool = False
    retention_authorized: bool = False
    production_adapter_enabled: bool = False
    trading_actionable: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.verdict, RefreshVerdict) or not self.reason:
            raise ValueError("Typed refresh verdict and explicit reason required")
        if any((self.supports_delta_from_last_change, not self.metadata_only,
                self.source_authority_verified, self.retention_authorized,
                self.production_adapter_enabled, self.trading_actionable)):
            raise ValueError("C2A cannot authorize a real data or trading operation")


def advise_connected_refresh(endpoint: ConnectedEndpoint, need: DataNeed,
                             *, changed_since_required: bool = False) -> ReadOnlyRefreshAdvice:
    """Explain what a future approved adapter COULD ask; never make a call.

    SSI D1 range=1d returns multiple days, not a single date range. SSI M1
    intraday uses range=1d and cannot limit to five minutes. DNSE DAY MCP
    returns the broad history without date bounds. VCBS D1 supports explicit
    calendar dates but not a revision cursor; its minute prices are not M1 bars.
    """
    c = endpoint_contract(endpoint)
    if not isinstance(need, DataNeed) or type(changed_since_required) is not bool:
        raise TypeError("Typed need and delta flag required")
    if changed_since_required:
        return ReadOnlyRefreshAdvice(endpoint, need, RefreshVerdict.BLOCKED,
                "NO_CONNECTED_MCP_HAS_VERIFIED_CHANGED_SINCE_REVISION_CURSOR")
    if c.need is not need:
        return ReadOnlyRefreshAdvice(endpoint, need, RefreshVerdict.BLOCKED,
                "ENDPOINT_DOES_NOT_SUPPLY_REQUIRED_DATA_PRODUCT")
    choices = {
        FetchBoundary.CALENDAR_DATE_WINDOW: (RefreshVerdict.REVALIDATE_DATE_WINDOW,
            "CALENDAR_DATES_BOUND_RESPONSE_NOT_DELTA_NOT_DATA_RIGHTS"),
        FetchBoundary.WHOLE_SESSION: (RefreshVerdict.REFETCH_WHOLE_SESSION,
            "MCP_HAS_DAY_GRANULARITY_NO_MINUTE_WINDOW; LOCAL_DIFF_ONLY"),
        FetchBoundary.FULL_D1_HISTORY: (RefreshVerdict.REFETCH_FULL_HISTORY,
            "DAY_MCP_HAS_NO_DATE_RANGE_ARGUMENT; LOCAL_DIFF_ONLY"),
        FetchBoundary.COARSE_DAY_RANGE: (RefreshVerdict.REFETCH_COARSE_DAILY_RANGE,
            "SSI_DAILY_RANGE_BUCKET_NOT_EXACT_DATE_DELTA; LOCAL_DIFF_ONLY"),
        FetchBoundary.CURRENT_SESSION_PRICE_SERIES: (RefreshVerdict.REFERENCE_SNAPSHOT,
            "PRICE_POINTS_ARE_NOT_NATIVE_MINUTE_OHLCV"),
        FetchBoundary.LATEST_SINGLE: (RefreshVerdict.REFERENCE_SNAPSHOT,
            "LATEST_SINGLE_ROW_IS_NOT_SESSION_COVERAGE"),
        FetchBoundary.QUOTE_BATCH: (RefreshVerdict.REFERENCE_SNAPSHOT,
            "QUOTE_BATCH_IS_NOT_A_CLOSED_CANDLE"),
    }
    verdict, reason = choices[c.boundary]
    return ReadOnlyRefreshAdvice(endpoint, need, verdict, reason)


def _utc(t: datetime) -> None:
    if (not isinstance(t, datetime) or t.tzinfo is None
            or t.utcoffset() != timedelta(0)):
        raise ValueError("UTC-aware observation clock required")


def _number(x: object, *, positive: bool) -> bool:
    if isinstance(x, bool) or not isinstance(x, (int, float, str)):
        return False
    try:
        d = Decimal(str(x))
    except (ValueError, InvalidOperation):
        return False
    return d.is_finite() and (d > 0 if positive else d >= 0)


def _candle(item: Mapping, o: str, h: str, l: str, c: str, volume: str) -> bool:
    fields = (o, h, l, c)
    if any(not _number(item.get(k), positive=True) for k in fields):
        return False
    if not _number(item.get(volume), positive=False):
        return False
    opening, high, low, close = (Decimal(str(item[k])) for k in fields)
    return low <= min(opening, close) <= high and low <= max(opening, close) <= high


def _rows(payload: object, ep: ConnectedEndpoint) -> tuple[int, int, bool, bool]:
    """Return total, invalid, expected-shape, provider-error using payload in memory.

    NO payload, symbol, account, price, timestamp or digest is returned.
    """
    if ep in (ConnectedEndpoint.SSI_D1_DETAILED, ConnectedEndpoint.SSI_INTRADAY_SESSION,
              ConnectedEndpoint.SSI_INTRADAY_LATEST):
        if not isinstance(payload, Mapping):
            return 0, 0, False, False
        if payload.get("status") != "ok":
            return 0, 0, True, True
        data = payload.get("data")
        key = "stocks" if ep is ConnectedEndpoint.SSI_D1_DETAILED else "ticks"
        if not isinstance(data, Mapping) or not isinstance(data.get(key), list):
            return 0, 0, False, False
        arr = data[key]
        if ep is ConnectedEndpoint.SSI_INTRADAY_LATEST and len(arr) > 1:
            return len(arr), len(arr), False, False
        invalid = 0
        for row in arr:
            if (not isinstance(row, Mapping) or not isinstance(row.get("trading_date"), str)
                    or not row["trading_date"] or
                    not _candle(row, "open", "high", "low", "close", "volume")):
                invalid += 1
        return len(arr), invalid, True, False
    if ep is ConnectedEndpoint.DNSE_D1_HISTORY:
        if not isinstance(payload, Mapping) or not isinstance(payload.get("data"), Mapping):
            return 0, 0, False, False
        d = payload["data"]
        keys = ("t", "o", "h", "l", "c", "v")
        if any(not isinstance(d.get(k), list) for k in keys):
            return 0, 0, False, False
        n = len(d["t"])
        if any(len(d[k]) != n for k in keys):
            return n, n, False, False
        invalid = 0
        prev = None
        for i in range(n):
            t = d["t"][i]
            if (type(t) is not int or t <= 0 or (prev is not None and t <= prev)
                    or not _candle({k: d[k][i] for k in keys}, "o", "h", "l", "c", "v")):
                invalid += 1
            prev = t
        return n, invalid, True, False
    if ep is ConnectedEndpoint.VCBS_D1_WINDOW:
        if not isinstance(payload, list):
            return 0, 0, False, False
        invalid = 0
        for row in payload:
            if (not isinstance(row, Mapping) or not isinstance(row.get("tradingDate"), str)
                    or not row["tradingDate"] or row.get("priceBasis") != "raw"
                    or row.get("price_unit") != "VND" or row.get("volumeScope") != "matched"
                    or not _candle(row, "openPrice", "highPrice", "lowPrice", "closePrice", "volume")):
                invalid += 1
        return len(payload), invalid, True, False
    if ep is ConnectedEndpoint.VCBS_INTRADAY_PRICE_POINTS:
        if not isinstance(payload, Mapping):
            return 0, 0, False, False
        if payload.get("data_status") in ("no_data", "error"):
            return 0, 0, True, payload.get("data_status") == "error"
        series = payload.get("series")
        if not isinstance(series, list):
            return 0, 0, False, False
        invalid = sum(1 for x in series if not isinstance(x, Mapping)
                      or not isinstance(x.get("time"), str)
                      or not _number(x.get("price"), positive=True))
        if type(payload.get("dataPoints")) is not int or payload["dataPoints"] != len(series):
            return len(series), len(series), False, False
        return len(series), invalid, True, False
    if ep is ConnectedEndpoint.VCBS_QUOTE_BATCH:
        # The connected endpoint documents partial/no_data, but response nesting
        # must be verified separately. Do not invent a data-row contract.
        if isinstance(payload, Mapping) and payload.get("data_status") == "error":
            return 0, 0, True, True
        return 0, 0, False, False
    raise TypeError("Unexpected endpoint enum")


@dataclass(frozen=True)
class InMemoryShapeAudit:
    endpoint: ConnectedEndpoint
    provider: Provider
    state: ProbeState
    observed_rows: int
    rejected_rows: int
    approx_serialized_bytes: int
    checked_at_utc: datetime
    reference_only: bool = True
    source_freshness_verified: bool = False
    closed_bar_finality_verified: bool = False
    source_rights_verified: bool = False
    price_adjustment_parity_verified: bool = False
    licensed_retention_approved: bool = False
    indicator_eligible: bool = False
    live_trading_enabled: bool = False

    def __post_init__(self) -> None:
        _utc(self.checked_at_utc)
        if not isinstance(self.endpoint, ConnectedEndpoint) or not isinstance(self.provider, Provider) or not isinstance(self.state, ProbeState):
            raise TypeError("Typed probe summary required")
        if any(type(x) is not int or x < 0 for x in (self.observed_rows, self.rejected_rows, self.approx_serialized_bytes)):
            raise ValueError("Nonnegative integer metadata required")
        if self.rejected_rows > self.observed_rows:
            raise ValueError("Rejected rows exceed observed rows")
        if any((not self.reference_only, self.source_freshness_verified,
                self.closed_bar_finality_verified, self.source_rights_verified,
                self.price_adjustment_parity_verified, self.licensed_retention_approved,
                self.indicator_eligible, self.live_trading_enabled)):
            raise ValueError("MCP schema is not a source-rights or production certificate")


def audit_transient_response(endpoint: ConnectedEndpoint, payload: object,
                             *, checked_at_utc: datetime) -> InMemoryShapeAudit:
    """Inspect an in-memory response shape; return metadata without raw quote rows.

    Caller must be independently approved to request any actual external feed;
    this function grants no such approval and intentionally has no I/O path.
    Serialized byte length is a diagnostic proxy, NOT wire-transfer bytes or
    independently observed latency. No raw payload SHA or OHLCV is persisted.
    """
    c = endpoint_contract(endpoint)
    _utc(checked_at_utc)
    try:
        size = len(json.dumps(payload, ensure_ascii=True, allow_nan=False,
                              separators=(",", ":")).encode("utf-8"))
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("Invalid or non-JSON in-memory source response") from exc
    if size > MAX_SERIALIZED_RESPONSE_BYTES:
        raise ValueError("Response exceeds the bounded diagnostic size; not inspected")
    n, invalid, valid_shape, source_error = _rows(payload, endpoint)
    if n > MAX_ROWS:
        raise ValueError("Excessive rows for bounded diagnostic")
    state = (ProbeState.SOURCE_ERROR if source_error else
             ProbeState.SCHEMA_REJECTED if not valid_shape or invalid else
             ProbeState.SHAPE_RETURNED if n else ProbeState.EMPTY_UNVERIFIED)
    return InMemoryShapeAudit(endpoint, c.provider, state, n, invalid, size, checked_at_utc)


def require_authorized_c2_source(report: InMemoryShapeAudit) -> None:
    """This contract cannot certify entitlement or authorize real data use."""
    if not isinstance(report, InMemoryShapeAudit):
        raise TypeError("Typed audit required")
    raise PermissionError("C2A lacks independently authenticated SSI/DNSE/VCBS feed rights")
