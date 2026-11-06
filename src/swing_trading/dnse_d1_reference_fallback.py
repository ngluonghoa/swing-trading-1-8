"""P0.15 read-only SSI→DNSE D1 fallback with explicit provider boundaries.

The returned OHLCV is REFERENCE ONLY; no full source entitlement,
official session calendar, corporate-action basis or historical first-known
verification. DNSE DAY timestamps identify the session, NOT its close.
Never transform fallback receipts into verified v1.2 candles or trade signals.
"""
from dataclasses import dataclass
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Callable

from .market_data import PriceBasis, Timeframe
from .replay import require_utc


_VN = timezone(timedelta(hours=7))


class D1Provider(str, Enum):
    SSI = "SSI"
    DNSE = "DNSE"


class D1PriceUnit(str, Enum):
    VND = "VND"
    THOUSAND_VND = "THOUSAND_VND"


class D1ReadState(str, Enum):
    BLOCKED = "BLOCKED"
    PRIMARY_SSI_REFERENCE_ONLY = "PRIMARY_SSI_REFERENCE_ONLY"
    FALLBACK_DNSE_REFERENCE_ONLY = "FALLBACK_DNSE_REFERENCE_ONLY"


class D1ComparisonState(str, Enum):
    BLOCKED = "BLOCKED"
    VOLUME_EQUAL_PRICE_BASIS_UNVERIFIED = "VOLUME_EQUAL_PRICE_BASIS_UNVERIFIED"
    SAME_KNOWN_BASIS_EXACT_PARITY_UNCERTIFIED = "SAME_KNOWN_BASIS_EXACT_PARITY_UNCERTIFIED"
    SOURCE_VOLUME_OR_PRICE_CONFLICT = "SOURCE_VOLUME_OR_PRICE_CONFLICT"


class D1SourceUnavailable(Exception):
    """Adapter explicitly reports a failed/blocked SSI or DNSE endpoint."""


@dataclass(frozen=True)
class D1ReferenceRequest:
    symbol: str
    exchange: str
    timeframe: Timeframe
    session_date_local: date
    as_of_utc: datetime

    def __post_init__(self) -> None:
        for name in ("symbol", "exchange"):
            v = getattr(self, name)
            if not isinstance(v, str) or not v.strip():
                raise ValueError(name + " must be explicit")
        if not isinstance(self.timeframe, Timeframe):
            raise TypeError("Timeframe enum required")
        if (not isinstance(self.session_date_local, date)
                or isinstance(self.session_date_local, datetime)):
            raise TypeError("Local session date required")
        require_utc(self.as_of_utc)


def _decimal(v) -> Decimal:
    if isinstance(v, bool) or not isinstance(v, (str, int, float, Decimal)):
        raise ValueError("OHLC must be a decimal-compatible finite number")
    try:
        x = Decimal(str(v))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid decimal OHLC") from exc
    if not x.is_finite() or x <= 0:
        raise ValueError("Positive finite OHLC required")
    return x


def _volume(v) -> int:
    if type(v) is int and v >= 0:
        return v
    if isinstance(v, str) and v and v.isascii() and v.isdecimal():
        return int(v)
    raise ValueError("Volume must be nonnegative lossless integer")


@dataclass(frozen=True)
class D1ProviderQuote:
    provider: D1Provider
    symbol: str
    exchange: str
    session_date_local: date
    observed_at_utc: datetime
    source_snapshot_id: str  # caller's ingestion receipt, not provider-native ID
    endpoint: str
    unit: D1PriceUnit
    price_basis: PriceBasis
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    session_label_utc: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.provider, D1Provider):
            raise TypeError("Explicit provider enum required")
        for name in ("symbol", "exchange", "source_snapshot_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(name + " must be explicit")
        if not isinstance(self.session_date_local, date) or isinstance(
            self.session_date_local, datetime
        ):
            raise TypeError("Explicit source session date required")
        require_utc(self.observed_at_utc)
        if not isinstance(self.unit, D1PriceUnit):
            raise TypeError("Explicit price unit required")
        if not isinstance(self.price_basis, PriceBasis):
            raise TypeError("Explicit price basis required")
        for name in ("open", "high", "low", "close"):
            x = getattr(self, name)
            if not isinstance(x, Decimal) or not x.is_finite() or x <= 0:
                raise ValueError("Positive finite Decimal OHLC required")
        if (self.low > min(self.open, self.close)
                or self.high < max(self.open, self.close)
                or self.high < self.low):
            raise ValueError("Invalid OHLC geometry")
        if type(self.volume) is not int or self.volume < 0:
            raise ValueError("Nonnegative integer matched volume required")
        if self.provider is D1Provider.SSI:
            if (self.endpoint != "marketdata_list_daily_stock_infor"
                    or self.unit is not D1PriceUnit.VND
                    or self.session_label_utc is not None):
                raise ValueError("SSI detailed daily receipt requires VND, no implied time label")
        else:
            if (self.endpoint != "price_get_history"
                    or self.unit is not D1PriceUnit.THOUSAND_VND
                    or self.price_basis is not PriceBasis.UNKNOWN
                    or self.session_label_utc is None):
                raise ValueError("DNSE DAY requires 1,000 VND unit and UNKNOWN basis")
            require_utc(self.session_label_utc)
            local_label = self.session_label_utc.astimezone(_VN)
            if (local_label.date() != self.session_date_local
                    or local_label.hour != 9 or local_label.minute != 0
                    or local_label.second != 0):
                raise ValueError("Unrecognized DNSE 09:00 local DAY session label")

    def vnd_prices(self) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        multiplier = Decimal(1000) if self.unit is D1PriceUnit.THOUSAND_VND else Decimal(1)
        return tuple(getattr(self, x) * multiplier for x in ("open", "high", "low", "close"))


@dataclass(frozen=True)
class DNSEHistorySnapshot:
    """Original DNSE OHLCV array snapshot; no invented source record IDs."""
    data: dict
    observed_at_utc: datetime
    source_snapshot_id: str

    def __post_init__(self) -> None:
        require_utc(self.observed_at_utc)
        if not isinstance(self.data, dict):
            raise TypeError("DNSE response data object required")
        if not isinstance(self.source_snapshot_id, str) or not self.source_snapshot_id.strip():
            raise ValueError("Real ingestion snapshot identifier required")


def select_dnse_d1_from_history(
    snapshot: DNSEHistorySnapshot,
    *,
    symbol: str,
    exchange: str,
    session_date_local: date,
) -> D1ProviderQuote | None:
    """Extract only exact date; Unix 02:00Z is a DAY label, never close/first-known.

    Arrays must align and be chronological. A selected historical daily
    bar is still unverified, even if its OHLCV agrees with SSI.
    """
    if not isinstance(snapshot, DNSEHistorySnapshot):
        raise TypeError("DNSEHistorySnapshot required")
    d = snapshot.data
    required = ("t", "o", "h", "l", "c", "v")
    if any(key not in d or not isinstance(d[key], list) for key in required):
        raise ValueError("DNSE historical data needs six parallel arrays")
    length = len(d["t"])
    if not length or any(len(d[key]) != length for key in required):
        raise ValueError("DNSE OHLCV lengths must be equal and nonempty")
    selected = None
    previous = None
    for i in range(length):
        ts = d["t"][i]
        if type(ts) is not int or ts < 0:
            raise ValueError("DNSE t[] must be Unix integer seconds")
        utc = datetime.fromtimestamp(ts, timezone.utc)
        if previous is not None and utc <= previous:
            raise ValueError("DNSE history timestamps must be strictly increasing")
        previous = utc
        local = utc.astimezone(_VN)
        if local.hour != 9 or local.minute != 0 or local.second != 0:
            raise ValueError("DNSE DAY timestamp is not the observed 09:00 local label")
        if local.date() != session_date_local:
            continue
        if selected is not None:
            raise ValueError("Duplicate target session")
        selected = D1ProviderQuote(
            D1Provider.DNSE, symbol, exchange, session_date_local,
            snapshot.observed_at_utc, snapshot.source_snapshot_id,
            "price_get_history", D1PriceUnit.THOUSAND_VND,
            PriceBasis.UNKNOWN,
            _decimal(d["o"][i]), _decimal(d["h"][i]),
            _decimal(d["l"][i]), _decimal(d["c"][i]),
            _volume(d["v"][i]), utc,
        )
    return selected


@dataclass(frozen=True)
class D1ReferenceAudit:
    state: D1ReadState
    reason: str
    source: D1Provider | None
    reference_quote: D1ProviderQuote | None
    primary_attempted: bool
    fallback_attempted: bool
    data_certified: bool = False
    market_calendar_certified: bool = False
    source_rights_verified: bool = False
    first_known_for_history_verified: bool = False
    eligible_for_indicators: bool = False
    eligible_for_backtest: bool = False
    actionable: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.state, D1ReadState) or not self.reason:
            raise ValueError("Explicit route audit state/reason required")
        if (self.state is D1ReadState.BLOCKED) != (self.reference_quote is None):
            raise ValueError("Only nonblocked candidate references may carry a quote")
        if self.reference_quote is not None and self.source is not self.reference_quote.provider:
            raise ValueError("Source identity and quote must match")
        if (type(self.primary_attempted) is not bool
                or type(self.fallback_attempted) is not bool):
            raise TypeError("Call inventory booleans required")
        if any((self.data_certified, self.market_calendar_certified,
                self.source_rights_verified, self.first_known_for_history_verified,
                self.eligible_for_indicators, self.eligible_for_backtest,
                self.actionable)):
            raise ValueError("P0.15 source fallback cannot approve signal/backtest")


def route_d1_reference(
    request: D1ReferenceRequest,
    fetch_ssi: Callable[[D1ReferenceRequest], D1ProviderQuote | None],
    fetch_dnse: Callable[[D1ReferenceRequest], DNSEHistorySnapshot | None],
) -> D1ReferenceAudit:
    """Actual source-selection control flow; adapters invoke external MCP separately.

    The host provides read-only source adapters; this module does not call
    connectors, mint credentials, cache a mixed-provider bar or do live orders.
    Unexpected adapter exceptions are propagated, not silently reclassified
    as a missing source.
    """
    if not isinstance(request, D1ReferenceRequest):
        raise TypeError("Typed request required")
    if not callable(fetch_ssi) or not callable(fetch_dnse):
        raise TypeError("Read-only source adapters required")

    def finish(state, reason, source=None, quote=None, ssi_called=False, dnse_called=False):
        return D1ReferenceAudit(state, reason, source, quote, ssi_called, dnse_called)

    if request.timeframe is not Timeframe.D1:
        return finish(D1ReadState.BLOCKED, "NO_DNSE_INTRADAY_SUBSTITUTION")
    if request.session_date_local >= request.as_of_utc.astimezone(_VN).date():
        return finish(D1ReadState.BLOCKED, "SAME_DAY_D1_CLOSE_NOT_INDEPENDENTLY_KNOWN")

    try:
        primary = fetch_ssi(request)
    except D1SourceUnavailable:
        primary = None
    if primary is not None:
        if not isinstance(primary, D1ProviderQuote):
            return finish(D1ReadState.BLOCKED, "INVALID_SSI_ADAPTER_TYPE", ssi_called=True)
        if (primary.provider is not D1Provider.SSI
                or primary.symbol != request.symbol or primary.exchange != request.exchange
                or primary.session_date_local != request.session_date_local):
            return finish(D1ReadState.BLOCKED, "SSI_IDENTITY_OR_DATE_MISMATCH", ssi_called=True)
        if primary.observed_at_utc > request.as_of_utc:
            return finish(D1ReadState.BLOCKED, "SSI_RECEIPT_NOT_KNOWN_AT_AUDIT_CLOCK", ssi_called=True)
        return finish(D1ReadState.PRIMARY_SSI_REFERENCE_ONLY,
                      "SSI_D1_RECEIPT_ONLY_SOURCE_CERTIFICATION_OPEN",
                      D1Provider.SSI, primary, True, False)

    try:
        alternate = fetch_dnse(request)
    except D1SourceUnavailable:
        alternate = None
    if alternate is None:
        return finish(D1ReadState.BLOCKED, "BOTH_D1_ENDPOINTS_EMPTY_OR_UNAVAILABLE",
                      ssi_called=True, dnse_called=True)
    if not isinstance(alternate, DNSEHistorySnapshot):
        return finish(D1ReadState.BLOCKED, "INVALID_DNSE_ADAPTER_TYPE",
                      ssi_called=True, dnse_called=True)
    if alternate.observed_at_utc > request.as_of_utc:
        return finish(D1ReadState.BLOCKED, "DNSE_SNAPSHOT_NOT_KNOWN_AT_AUDIT_CLOCK",
                      ssi_called=True, dnse_called=True)
    try:
        candidate = select_dnse_d1_from_history(
            alternate, symbol=request.symbol, exchange=request.exchange,
            session_date_local=request.session_date_local,
        )
    except (ValueError, OverflowError):
        return finish(D1ReadState.BLOCKED, "DNSE_D1_HISTORY_INVALID",
                      ssi_called=True, dnse_called=True)
    if candidate is None:
        return finish(D1ReadState.BLOCKED, "DNSE_TARGET_D1_NOT_IN_SNAPSHOT",
                      ssi_called=True, dnse_called=True)
    return finish(D1ReadState.FALLBACK_DNSE_REFERENCE_ONLY,
                  "DNSE_D1_FALLBACK_UNCALIBRATED_NO_SOURCE_RIGHTS_BASIS_OR_POINT_IN_TIME",
                  D1Provider.DNSE, candidate, True, True)


@dataclass(frozen=True)
class D1ComparisonAudit:
    state: D1ComparisonState
    reason: str
    volume_equal: bool | None
    normalized_ohlc_equal: bool | None
    price_basis_qualified: bool = False
    source_independent: bool = False
    data_certified: bool = False
    actionable: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.state, D1ComparisonState) or not self.reason:
            raise ValueError("Explicit comparison state required")
        if any((self.price_basis_qualified, self.source_independent,
                self.data_certified, self.actionable)):
            raise ValueError("No P0.15 cross-source certification")


def compare_ssi_dnse_d1(ssi: D1ProviderQuote, dnse: D1ProviderQuote) -> D1ComparisonAudit:
    """Diagnostic only; even exact numeric agreement is NOT price-basis parity."""
    if not isinstance(ssi, D1ProviderQuote) or not isinstance(dnse, D1ProviderQuote):
        raise TypeError("Two typed provider receipts required")
    if ssi.provider is not D1Provider.SSI or dnse.provider is not D1Provider.DNSE:
        return D1ComparisonAudit(D1ComparisonState.BLOCKED, "WRONG_PROVIDER_PAIR", None, None)
    if (ssi.symbol != dnse.symbol or ssi.exchange != dnse.exchange
            or ssi.session_date_local != dnse.session_date_local):
        return D1ComparisonAudit(D1ComparisonState.BLOCKED,
                                 "SYMBOL_EXCHANGE_OR_SESSION_MISMATCH", None, None)
    v_equal = ssi.volume == dnse.volume
    p_equal = ssi.vnd_prices() == dnse.vnd_prices()
    if not v_equal:
        return D1ComparisonAudit(D1ComparisonState.SOURCE_VOLUME_OR_PRICE_CONFLICT,
                                 "D1_MATCHED_VOLUME_CONFLICT", False, p_equal)
    # DNSE stock history does not expose unambiguous adjusted/raw basis.
    if ssi.price_basis is PriceBasis.UNKNOWN or dnse.price_basis is PriceBasis.UNKNOWN:
        return D1ComparisonAudit(D1ComparisonState.VOLUME_EQUAL_PRICE_BASIS_UNVERIFIED,
                                 "D1_VOLUME_MATCH_ONLY_PRICE_BASIS_UNKNOWN",
                                 True, p_equal)
    if not p_equal:
        return D1ComparisonAudit(D1ComparisonState.SOURCE_VOLUME_OR_PRICE_CONFLICT,
                                 "D1_PRICE_CONFLICT", True, False)
    return D1ComparisonAudit(D1ComparisonState.SAME_KNOWN_BASIS_EXACT_PARITY_UNCERTIFIED,
                             "D1_NUMERIC_AGREEMENT_UNCERTIFIED", True, True)
