"""GĐ4/P0.25 — source-native minute bar discovery/blueprint, no live transport.

Official product documentation identifies native OHLC endpoints, but a public
API capability is not a connected MCP tool, account entitlement, historical
first-known proof, cache licence or backtest certification. No credential
handling, HTTP/MCP call, raw OHLCV retention, market-bar construction or order.
"""
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
import re
from zoneinfo import ZoneInfo

from .dnse_d1_reference_fallback import D1Provider
from .market_data import Timeframe
from .replay import require_utc

_VN = ZoneInfo("Asia/Ho_Chi_Minh")
_SYMBOL = re.compile(r"^[A-Z][A-Z0-9]{1,14}$")


class SourceBarGateClosed(PermissionError):
    """A documented product must not be promoted to a production source."""


class BarProduct(str, Enum):
    SSI_CONNECTED_INTRADAY_TICKS = "SSI_MCP.marketdata_list_intraday_stock_infor"
    SSI_FASTCONNECT_INTRADAY_OHLC = "SSI_FASTCONNECT.Market/IntradayOhlc"
    DNSE_CONNECTED_DAY_ONLY = "DNSE_MCP.price_get_history"
    DNSE_OPENAPI_OHLC = "DNSE_OPENAPI./price/ohlc"


class ResolutionEvidence(str, Enum):
    NOT_NATIVE_MINUTE_BARS = "NOT_NATIVE_MINUTE_BARS"
    DEFAULT_1M_DOCUMENTED_ONLY = "DEFAULT_1M_DOCUMENTED_ONLY"
    INTEGER_PARAMETER_VALUE_NOT_ENUMERATED = "INTEGER_PARAMETER_VALUE_NOT_ENUMERATED"
    EXPLICIT_TIMEFRAME_LISTED = "EXPLICIT_TIMEFRAME_LISTED"


@dataclass(frozen=True)
class BarProductDescription:
    product: BarProduct
    provider: D1Provider
    endpoint: str
    documentation_url: str | None
    documented_native_ohlc: bool
    available_as_connected_mcp: bool
    required_auth_fields: tuple[str, ...]
    # Both status flags are deliberately derived and never user-settable.
    @property
    def authenticated_to_product(self):
        return False

    @property
    def licensed_historical_retention(self):
        return False

    @property
    def source_native_history_verified(self):
        return False


_PRODUCT_SPECS = {
    BarProduct.SSI_CONNECTED_INTRADAY_TICKS: BarProductDescription(
        BarProduct.SSI_CONNECTED_INTRADAY_TICKS, D1Provider.SSI,
        "marketdata_list_intraday_stock_infor", None,
        False, True, (),
    ),
    BarProduct.SSI_FASTCONNECT_INTRADAY_OHLC: BarProductDescription(
        BarProduct.SSI_FASTCONNECT_INTRADAY_OHLC, D1Provider.SSI,
        "Market/IntradayOhlc",
        "https://guide.ssi.com.vn/ssi-products/fastconnect-data/api-specs",
        True, False, ("consumerID", "consumerSecret", "accessToken"),
    ),
    BarProduct.DNSE_CONNECTED_DAY_ONLY: BarProductDescription(
        BarProduct.DNSE_CONNECTED_DAY_ONLY, D1Provider.DNSE,
        "price_get_history", None, False, True, (),
    ),
    BarProduct.DNSE_OPENAPI_OHLC: BarProductDescription(
        BarProduct.DNSE_OPENAPI_OHLC, D1Provider.DNSE,
        "/price/ohlc",
        "https://developers.dnse.com.vn/docs/dnse/get-ohlc-history/",
        True, False, ("X-API-Key", "X-Aux-Date", "X-Signature"),
    ),
}


def describe_bar_product(product: BarProduct):
    if not isinstance(product, BarProduct):
        raise TypeError("Typed BarProduct required")
    return _PRODUCT_SPECS[product]


def resolution_evidence(product: BarProduct, timeframe: Timeframe):
    """Distinguish explicitly documented timeframe vs unenumerated integer."""
    describe_bar_product(product)
    if not isinstance(timeframe, Timeframe) or timeframe not in (
        Timeframe.M1, Timeframe.M5, Timeframe.M15
    ):
        raise ValueError("P0.25 only audits M1, M5 and M15")
    if product in (BarProduct.SSI_CONNECTED_INTRADAY_TICKS,
                   BarProduct.DNSE_CONNECTED_DAY_ONLY):
        return ResolutionEvidence.NOT_NATIVE_MINUTE_BARS
    if product is BarProduct.DNSE_OPENAPI_OHLC:
        return ResolutionEvidence.EXPLICIT_TIMEFRAME_LISTED
    if timeframe is Timeframe.M1:
        return ResolutionEvidence.DEFAULT_1M_DOCUMENTED_ONLY
    return ResolutionEvidence.INTEGER_PARAMETER_VALUE_NOT_ENUMERATED


_OPEN_GATES = (
    "NO_CONNECTED_NATIVE_MINUTE_BAR_ENDPOINT",
    "NO_ACCOUNT_LEVEL_ENDPOINT_ENTITLEMENT",
    "NO_PROVIDER_LICENSED_HISTORICAL_RETENTION_EVIDENCE",
    "NO_INDEPENDENT_TIMESTAMP_LABEL_AND_BAR_CLOSURE_SEMANTICS",
    "NO_HISTORICAL_PUBLICATION_FIRST_KNOWN_OR_REVISION_PROVENANCE",
    "NO_ADJUSTMENT_BASIS_CORPORATE_ACTION_AND_EXCHANGE_CALENDAR_PROOF",
    "NO_COMPLETE_PAGINATION_AND_SESSION_COVERAGE",
    "NO_APPROVED_HOST_SQLITE_WAL_STORAGE_AND_CUSTODY",
    "NO_EXECUTABLE_CALIBRATED_B5_AND_REALISTIC_TRADE_SIMULATOR",
)


@dataclass(frozen=True)
class NativeBarCandidate:
    product: BarProduct
    timeframe: Timeframe
    resolution_evidence: ResolutionEvidence
    unresolved: tuple[str, ...]

    @property
    def executable(self):
        return False

    @property
    def entitled(self):
        return False

    @property
    def usable_for_indicators(self):
        return False

    @property
    def historical_backtest_qualified(self):
        return False

    @property
    def actionable(self):
        return False


def candidate_native_bar_sources(timeframe: Timeframe):
    """Source catalog, not source selection or live data feed."""
    if not isinstance(timeframe, Timeframe) or timeframe not in (
        Timeframe.M1, Timeframe.M5, Timeframe.M15
    ):
        raise ValueError("Explicit supported minute timeframe required")
    return tuple(NativeBarCandidate(
        product, timeframe, resolution_evidence(product, timeframe), _OPEN_GATES,
    ) for product in BarProduct)


@dataclass(frozen=True)
class UnsentReadOnlyQuery:
    """Sanitized first-page query sketch; never supplies credentials or calls."""
    product: BarProduct
    timeframe: Timeframe
    symbol: str
    session_day: date
    parameter_pairs: tuple[tuple[str, str | int | bool], ...]
    required_auth_fields: tuple[str, ...]
    method_from_public_docs: str
    first_page_only: bool = True

    @property
    def connected(self):
        return False

    @property
    def ready_to_send(self):
        return False

    @property
    def retention_approved(self):
        return False

    @property
    def actionable(self):
        return False


def sketch_first_page_query(
    product: BarProduct, timeframe: Timeframe, *,
    symbol: str, session_day: date,
    start_utc: datetime | None = None,
    end_utc: datetime | None = None,
):
    """Make only an inert, metadata-only *query sketch*, with hard-closed gates.

    This is not an HTTP command or connector binding. For DNSE, "from"/"to"
    are caller-provided UTC Unix timestamps; range edge inclusivity is unknown.
    SSI documentation spells integer field "resollution" and does not
    enumerate legal M5/M15 values. Do NOT guess them.
    """
    spec = describe_bar_product(product)
    evidence = resolution_evidence(product, timeframe)
    if not isinstance(symbol, str) or not _SYMBOL.fullmatch(symbol):
        raise ValueError("Symbol must be uppercase and simple")
    if type(session_day) is not date:
        raise TypeError("An explicit session day is required")
    if not spec.documented_native_ohlc:
        raise SourceBarGateClosed("Connected MCP action has no native minute-bar contract")
    if product is BarProduct.SSI_FASTCONNECT_INTRADAY_OHLC:
        if evidence is not ResolutionEvidence.DEFAULT_1M_DOCUMENTED_ONLY:
            raise SourceBarGateClosed("SSI integer 5/15 resolutions unenumerated by source")
        if start_utc is not None or end_utc is not None:
            raise ValueError("SSI API sketch is date-based, not Unix range-based")
        params = (
            ("symbol", symbol),
            ("fromDate", session_day.strftime("%d/%m/%Y")),
            ("toDate", session_day.strftime("%d/%m/%Y")),
            ("pageIndex", 1), ("pageSize", 1000),
            ("ascending", True), ("resollution", 1),
        )
        # Newer public documentation says GET, older PDF describes POST:
        # method/version needs provider confirmation before any connector.
        method = "GET_DOCUMENTED_METHOD_UNCONFIRMED"
    else:
        if start_utc is None or end_utc is None:
            raise ValueError("DNSE requires bounded explicit UTC start/end")
        require_utc(start_utc)
        require_utc(end_utc)
        if not start_utc < end_utc:
            raise ValueError("End must follow start")
        if start_utc.astimezone(_VN).date() != session_day:
            raise ValueError("Start must match requested Vietnam session day")
        if (end_utc.astimezone(_VN).date() != session_day
                or (end_utc - start_utc).total_seconds() > 86400):
            raise ValueError("Single-session local query only")
        params = (
            ("symbol", symbol), ("type", "STOCK"),
            ("resolution", {Timeframe.M1: "1",
                            Timeframe.M5: "5",
                            Timeframe.M15: "15"}[timeframe]),
            ("from", int(start_utc.timestamp())),
            ("to", int(end_utc.timestamp())),
        )
        method = "GET_DOCUMENTED_NOT_CONNECTED"
    return UnsentReadOnlyQuery(
        product, timeframe, symbol, session_day, params,
        spec.required_auth_fields, method,
    )
