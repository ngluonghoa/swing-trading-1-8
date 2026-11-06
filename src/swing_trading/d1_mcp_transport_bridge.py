"""P0.16 injected, read-only SSI/DNSE MCP transport adapters + isolated receipts.

No connector credentials live in this module. An authorized host must inject
the two already authenticated MCP read functions and a trustworthy UTC receipt
clock. No persistence, trading source qualification, orders or background jobs.
"""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from hashlib import sha256
import json
from typing import Callable

from .dnse_d1_reference_fallback import (
    D1Provider, D1ProviderQuote, D1PriceUnit, D1ReferenceRequest,
    D1ReferenceAudit, D1SourceUnavailable, DNSEHistorySnapshot,
    route_d1_reference, _decimal, _volume,
)
from .market_data import PriceBasis
from .replay import require_utc


class ReceiptState(str, Enum):
    FETCHED = "FETCHED"
    UNAVAILABLE = "UNAVAILABLE"
    TARGET_DATE_ABSENT = "TARGET_DATE_ABSENT"


@dataclass(frozen=True)
class SourceFetchReceipt:
    """Minimal metadata-only audit record, no raw provider payload or secrets."""
    provider: D1Provider
    endpoint: str
    symbol: str
    exchange: str
    requested_date: date
    retrieved_at_utc: datetime
    state: ReceiptState
    raw_payload_digest_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.provider, D1Provider) or not isinstance(self.state, ReceiptState):
            raise TypeError("Explicit provider and fetch state required")
        if not isinstance(self.requested_date, date) or isinstance(self.requested_date, datetime):
            raise TypeError("Explicit local date required")
        for attr in ("symbol", "exchange", "endpoint"):
            if not isinstance(getattr(self, attr), str) or not getattr(self, attr).strip():
                raise ValueError("Missing source fetch identity")
        require_utc(self.retrieved_at_utc)
        h = self.raw_payload_digest_sha256
        if not isinstance(h, str) or len(h) != 64 or any(c not in "0123456789abcdef" for c in h):
            raise ValueError("Require lowercase SHA256 of raw provider response")


def _response(raw) -> dict:
    """Accept parsed mapping or JSON string; no response/text guessing."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Transport did not return valid JSON") from exc
    if not isinstance(raw, dict):
        raise ValueError("Transport response must be a JSON object")
    return raw


def _digest(payload: dict) -> str:
    """Stable ingestion digest, NOT a provider source-event ID."""
    try:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("Provider payload cannot be canonically serialized") from exc
    return sha256(raw.encode("utf-8")).hexdigest()


def _ssi_unavailable(response: dict) -> bool:
    if response.get("status") == "ok":
        return False
    error = response.get("error")
    if isinstance(error, dict):
        code = error.get("code")
    elif isinstance(error, str):
        code = error
    else:
        code = None
    if code == "DOWNSTREAM_UNAVAILABLE":
        return True
    raise ValueError("SSI provider response failed with unapproved error classification")


def _ssi_target(response: dict, req: D1ReferenceRequest, now: datetime,
                digest: str) -> D1ProviderQuote | None:
    data = response.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("stocks"), list):
        raise ValueError("SSI detailed daily response lacks stocks list")
    day_text = req.session_date_local.strftime("%d/%m/%Y")
    matches = [row for row in data["stocks"]
               if isinstance(row, dict) and row.get("trading_date") == day_text]
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError("SSI duplicate same trading date")
    row = matches[0]
    if row.get("symbol") != req.symbol:
        raise ValueError("SSI detailed daily symbol mismatch")
    # SSI detailed daily's open/high/low/close price-basis semantics remain
    # unconfirmed across corporate actions; never assume adjusted or raw.
    return D1ProviderQuote(
        D1Provider.SSI, req.symbol, req.exchange, req.session_date_local,
        now, digest, "marketdata_list_daily_stock_infor",
        D1PriceUnit.VND, PriceBasis.UNKNOWN,
        _decimal(row.get("open")), _decimal(row.get("high")),
        _decimal(row.get("low")), _decimal(row.get("close")),
        _volume(row.get("total_match_volume")),
    )


class ProviderSeparatedReferenceCache:
    """Volatile diagnostic quote cache, ALWAYS keyed explicitly by provider.

    Never used as a source substitute by the router; cannot promote a quote
    into actionable/verified data or collapse SSI/DNSE stream identities.
    """
    def __init__(self):
        self._data = {provider: {} for provider in D1Provider}

    def put(self, quote: D1ProviderQuote) -> None:
        if not isinstance(quote, D1ProviderQuote):
            raise TypeError("Typed provider quote required")
        key = (quote.symbol, quote.exchange, quote.session_date_local,
               quote.source_snapshot_id)
        self._data[quote.provider][key] = quote

    def get(self, provider: D1Provider, symbol: str, exchange: str,
            day: date, source_snapshot_id: str) -> D1ProviderQuote | None:
        if not isinstance(provider, D1Provider):
            raise TypeError("Provider must be explicit; cross-source lookup forbidden")
        return self._data[provider].get((symbol, exchange, day, source_snapshot_id))

    def count(self, provider: D1Provider) -> int:
        if not isinstance(provider, D1Provider):
            raise TypeError("Provider must be explicit")
        return len(self._data[provider])


@dataclass(frozen=True)
class BridgeRun:
    audit: D1ReferenceAudit
    receipts: tuple[SourceFetchReceipt, ...]
    reference_only: bool = True
    live_adapter_deployed: bool = False
    actionable: bool = False
    historical_backtest_qualified: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.audit, D1ReferenceAudit):
            raise TypeError("Underlying route audit required")
        if (not isinstance(self.receipts, tuple)
                or any(not isinstance(x, SourceFetchReceipt) for x in self.receipts)):
            raise TypeError("Immutable receipt inventory required")
        if (self.reference_only is not True or self.live_adapter_deployed
                or self.actionable or self.historical_backtest_qualified):
            raise ValueError("MCP adapter test bridge cannot certify production use")
        providers = tuple(x.provider for x in self.receipts)
        if providers not in ((), (D1Provider.SSI,), (D1Provider.SSI, D1Provider.DNSE)):
            raise ValueError("Source events must follow SSI-first route")


class ReadOnlyMcpD1Bridge:
    """Parses real MCP envelope shapes with injected authorized host callbacks.

    The callback names/arguments match SSI marketdata_list_daily_stock_infor
    and DNSE price_get_history, but no connector is imported or called by this
    library on its own. Only returned, selected reference quote is cached.
    """
    def __init__(self, ssi_call: Callable[[dict], dict], dnse_call: Callable[[dict], dict],
                 clock: Callable[[], datetime], cache: ProviderSeparatedReferenceCache):
        if not all(callable(x) for x in (ssi_call, dnse_call, clock)):
            raise TypeError("Authenticated read-only callable transports and clock required")
        if not isinstance(cache, ProviderSeparatedReferenceCache):
            raise TypeError("Provider separated diagnostic cache required")
        self.ssi_call, self.dnse_call, self.clock, self.cache = (
            ssi_call, dnse_call, clock, cache,
        )

    def run(self, request: D1ReferenceRequest) -> BridgeRun:
        if not isinstance(request, D1ReferenceRequest):
            raise TypeError("Typed request required")
        events = []

        def receipt(provider, endpoint, req, now, state, digest):
            events.append(SourceFetchReceipt(provider, endpoint, req.symbol,
                                             req.exchange, req.session_date_local,
                                             now, state, digest))

        def fetch_ssi(req):
            response = _response(self.ssi_call({
                "symbol": req.symbol, "range": "1d",
                "toDate": req.session_date_local.strftime("%d/%m/%Y"),
                "pageSize": 5, "pageIndex": 1,
            }))
            now = self.clock()
            require_utc(now)
            digest = _digest(response)
            if _ssi_unavailable(response):
                receipt(D1Provider.SSI, "marketdata_list_daily_stock_infor",
                        req, now, ReceiptState.UNAVAILABLE, digest)
                raise D1SourceUnavailable("SSI DOWNSTREAM_UNAVAILABLE")
            quote = _ssi_target(response, req, now, digest)
            receipt(D1Provider.SSI, "marketdata_list_daily_stock_infor", req, now,
                    ReceiptState.FETCHED if quote else ReceiptState.TARGET_DATE_ABSENT,
                    digest)
            return quote

        def fetch_dnse(req):
            response = _response(self.dnse_call({"symbol": req.symbol}))
            now = self.clock()
            require_utc(now)
            digest = _digest(response)
            if not isinstance(response.get("data"), dict):
                raise ValueError("DNSE price_get_history lacks data arrays")
            receipt(D1Provider.DNSE, "price_get_history", req, now,
                    ReceiptState.FETCHED, digest)
            return DNSEHistorySnapshot(response["data"], now, digest)

        result = route_d1_reference(request, fetch_ssi, fetch_dnse)
        if result.reference_quote is not None:
            self.cache.put(result.reference_quote)
        return BridgeRun(result, tuple(events))
