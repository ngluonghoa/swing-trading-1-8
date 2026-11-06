"""GĐ4/P0.23 — non-persisting SSI/DNSE source capability observations.

A read-only response shape and row count do NOT establish licensed retention,
complete intraday bars, historical first-known times, or usable backtest data.
Never returns raw OHLCV, writes data, connects to MCP or approves signals.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import json
import re
from zoneinfo import ZoneInfo

from .dnse_d1_reference_fallback import D1Provider
from .replay import require_utc

_VN = ZoneInfo("Asia/Ho_Chi_Minh")
_SYMBOL = re.compile(r"^[A-Z][A-Z0-9]{1,14}$")
_MAX_PAYLOAD = 4 * 1024 * 1024


class ProbeEndpoint(str, Enum):
    SSI_FULL_INTRADAY = "marketdata_list_stock_infor"
    SSI_INTRADAY = "marketdata_list_intraday_stock_infor"
    SSI_DAILY = "marketdata_list_daily_stock_infor"
    DNSE_DAY = "price_get_history"

    @property
    def provider(self):
        return D1Provider.DNSE if self is ProbeEndpoint.DNSE_DAY else D1Provider.SSI

    @property
    def response_kind(self):
        if self is ProbeEndpoint.DNSE_DAY:
            return "DAY_SESSION_LABEL"
        if self is ProbeEndpoint.SSI_DAILY:
            return "DAY_ROW"
        return "INTRADAY_TICK_UNQUALIFIED"


class ProbeState(str, Enum):
    RETURNED_ROWS = "RETURNED_ROWS"
    RETURNED_EMPTY = "RETURNED_EMPTY"
    DOWNSTREAM_UNAVAILABLE = "DOWNSTREAM_UNAVAILABLE"
    UNCLASSIFIED_ERROR = "UNCLASSIFIED_ERROR"


@dataclass(frozen=True)
class SourceCapabilityObservation:
    provider: D1Provider
    endpoint: ProbeEndpoint
    symbol: str
    checked_at_utc: datetime
    state: ProbeState
    observed_rows: int
    time_label_class: str
    reference_only: bool = True

    def __post_init__(self):
        if (not isinstance(self.provider, D1Provider)
                or not isinstance(self.endpoint, ProbeEndpoint)
                or self.endpoint.provider is not self.provider):
            raise TypeError("Endpoint/provider mismatch")
        if not isinstance(self.symbol, str) or not _SYMBOL.fullmatch(self.symbol):
            raise ValueError("Uppercase symbol required")
        require_utc(self.checked_at_utc)
        if not isinstance(self.state, ProbeState):
            raise TypeError("ProbeState enum required")
        if type(self.observed_rows) is not int or self.observed_rows < 0:
            raise ValueError("Nonnegative exact observed row count required")
        if (self.state is ProbeState.RETURNED_ROWS) != (self.observed_rows > 0):
            raise ValueError("Row count and outcome disagree")
        if (self.time_label_class != self.endpoint.response_kind
                or self.reference_only is not True):
            raise ValueError("Source observations cannot be certified or elevated")

    @property
    def source_rights_verified(self):
        return False

    @property
    def retention_approved(self):
        return False

    @property
    def historical_first_known_verified(self):
        return False

    @property
    def adjustment_basis_verified(self):
        return False

    @property
    def continuous_m1_m5_m15_coverage_verified(self):
        return False

    @property
    def full_source_pagination_verified(self):
        return False

    @property
    def clock_independently_attested(self):
        return False

    @property
    def production_qualified(self):
        return False

    @property
    def eligible_for_indicators(self):
        return False

    @property
    def eligible_for_backtest(self):
        return False

    @property
    def actionable(self):
        return False


def summarize_source_capability(
    endpoint: ProbeEndpoint, response: dict, *,
    symbol: str, checked_at_utc: datetime,
) -> SourceCapabilityObservation:
    """Only in-memory response shape/count audit; never store quote values.

    Handles explicit SSI statuses and DNSE DAY arrays. SSI intraday timestamp
    formats have differed between endpoint descriptions and observed examples;
    therefore labels are deliberately NOT parsed into bar instants.
    """
    if not isinstance(endpoint, ProbeEndpoint):
        raise TypeError("Allowlisted endpoint enum required")
    if not isinstance(symbol, str) or not _SYMBOL.fullmatch(symbol):
        raise ValueError("Explicit uppercase stock symbol required")
    require_utc(checked_at_utc)
    if not isinstance(response, dict):
        raise TypeError("Parsed response dictionary required")
    try:
        size = len(json.dumps(response, allow_nan=False, separators=(",", ":"),
                              ensure_ascii=False).encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Response cannot be canonically serialized") from exc
    if size > _MAX_PAYLOAD:
        raise ValueError("Payload exceeds 4MiB transient audit bound")

    if endpoint.provider is D1Provider.SSI:
        if response.get("status") != "ok":
            error = response.get("error")
            code = (error.get("code") if isinstance(error, dict)
                    else error if isinstance(error, str) else None)
            state = (ProbeState.DOWNSTREAM_UNAVAILABLE if
                     code == "DOWNSTREAM_UNAVAILABLE" else
                     ProbeState.UNCLASSIFIED_ERROR)
            count = 0
        else:
            data = response.get("data")
            key = "stocks" if endpoint is ProbeEndpoint.SSI_DAILY else "ticks"
            rows = data.get(key) if isinstance(data, dict) else None
            if not isinstance(rows, list):
                raise ValueError("SSI endpoint missing documented row list")
            for row in rows:
                if (not isinstance(row, dict)
                        or row.get("symbol") != symbol
                        or not isinstance(row.get("trading_date"), str)
                        or not row["trading_date"]):
                    raise ValueError("SSI row identity/date label mismatch")
            count = len(rows)
            state = ProbeState.RETURNED_ROWS if count else ProbeState.RETURNED_EMPTY
    else:
        data = response.get("data")
        names = ("t", "o", "h", "l", "c", "v")
        if not isinstance(data, dict) or any(
            not isinstance(data.get(k), list) for k in names
        ):
            raise ValueError("DNSE DAY missing six parallel arrays")
        count = len(data["t"])
        if any(len(data[k]) != count for k in names):
            raise ValueError("DNSE history arrays must align")
        previous = None
        for timestamp in data["t"]:
            if type(timestamp) is not int or timestamp < 0:
                raise ValueError("DNSE session label must be Unix seconds")
            if previous is not None and timestamp <= previous:
                raise ValueError("DNSE DAY labels not strictly ascending")
            previous = timestamp
            try:
                local = datetime.fromtimestamp(timestamp, _VN)
            except (OverflowError, OSError, ValueError) as exc:
                raise ValueError("Invalid DAY session label") from exc
            if (local.hour, local.minute, local.second) != (9, 0, 0):
                raise ValueError("DNSE history label is not 09:00 local DAY label")
        state = ProbeState.RETURNED_ROWS if count else ProbeState.RETURNED_EMPTY
    return SourceCapabilityObservation(
        endpoint.provider, endpoint, symbol, checked_at_utc,
        state, count, endpoint.response_kind,
    )


@dataclass(frozen=True)
class BacktestEvidenceBlockers:
    observed_source_endpoints: tuple[str, ...]
    unresolved: tuple[str, ...]

    @property
    def ready_for_historical_backtest(self):
        return False

    @property
    def actionable(self):
        return False


def audit_backtest_evidence(probes: tuple[SourceCapabilityObservation, ...]):
    """No observed endpoint may silently promote source or strategy readiness."""
    if not isinstance(probes, tuple) or any(
        not isinstance(x, SourceCapabilityObservation) for x in probes
    ):
        raise TypeError("Typed source observations required")
    seen = tuple(sorted({x.provider.value + "." + x.endpoint.value
                         for x in probes if x.state is ProbeState.RETURNED_ROWS}))
    return BacktestEvidenceBlockers(seen, (
        "PROVIDER_RETENTION_RIGHTS_NOT_INDEPENDENTLY_VERIFIED",
        "SOURCE_NATIVE_HISTORICAL_M1_M5_M15_COVERAGE_UNVERIFIED",
        "HISTORICAL_FIRST_KNOWN_AND_REVISIONS_UNVERIFIED",
        "PRICE_ADJUSTMENT_AND_CORPORATE_ACTION_POLICY_UNVERIFIED",
        "SESSION_CALENDAR_AND_PAGINATION_COMPLETENESS_UNVERIFIED",
        "HOST_STORAGE_AND_RUNTIME_NOT_APPROVED",
        "B5_CALIBRATED_EXECUTABLE_DETECTOR_NOT_READY",
        "FILL_FEES_SLIPPAGE_TAX_TPLUS2_SIMULATOR_NOT_READY",
    ))
