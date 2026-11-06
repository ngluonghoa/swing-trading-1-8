"""GĐ4/P0.22 — offline MCP host-envelope conformance harness.

FIXTURE_ONLY: accepts static SSI/DNSE response envelopes, never callback
transports, credentials, sockets, connected tools or persistent market cache.
Routes through the existing P0.16 SSI-first/DNSE-fallback D1 reference bridge
to test endpoint arguments, boundaries, provenance and source isolation.
NOT a deployed or authenticated MCP client, not real market data.
"""
from dataclasses import dataclass
from datetime import datetime
import json
from typing import Mapping

from .d1_mcp_transport_bridge import (
    BridgeRun, ProviderSeparatedReferenceCache, ReadOnlyMcpD1Bridge,
)
from .dnse_d1_reference_fallback import D1Provider, D1ReferenceRequest
from .reference_journal import _utc

_ALLOWED = {
    D1Provider.SSI: "marketdata_list_daily_stock_infor",
    D1Provider.DNSE: "price_get_history",
}
_FORBIDDEN = frozenset({
    "authorization", "api_key", "apikey", "secret", "password", "token",
    "access_token", "refresh_token", "cookie", "credential", "client_secret",
})
_MAX_BYTES = 128 * 1024


def _no_credentials(value):
    if isinstance(value, dict):
        for k, v in value.items():
            if not isinstance(k, str):
                raise ValueError("Fixture JSON keys must be text")
            if k.lower().replace("-", "_") in _FORBIDDEN:
                raise ValueError("Credential-bearing fixture key forbidden")
            _no_credentials(v)
    elif isinstance(value, list):
        for v in value:
            _no_credentials(v)


@dataclass(frozen=True)
class StaticMcpFixture:
    provider: D1Provider
    endpoint: str
    canonical_response_json: str

    def __post_init__(self):
        if not isinstance(self.provider, D1Provider):
            raise TypeError("Typed provider required")
        if self.endpoint != _ALLOWED[self.provider]:
            raise ValueError("Only two known read-only D1 MCP endpoint IDs allowed")
        if type(self.canonical_response_json) is not str:
            raise TypeError("Only frozen static canonical JSON permitted")
        if len(self.canonical_response_json.encode("utf-8")) > _MAX_BYTES:
            raise ValueError("Fixture response exceeds 128KiB")
        try:
            parsed = json.loads(self.canonical_response_json)
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid static MCP fixture") from exc
        if not isinstance(parsed, dict):
            raise ValueError("MCP response must be a JSON object")
        _no_credentials(parsed)
        if json.dumps(parsed,sort_keys=True,separators=(",",":"),
                      ensure_ascii=False,allow_nan=False) != self.canonical_response_json:
            raise ValueError("Fixture JSON must be canonical and unambiguous")

    @classmethod
    def from_payload(cls, provider, endpoint, payload):
        if callable(payload):
            raise TypeError("Live connector callback is forbidden in fixture harness")
        if not isinstance(payload, dict):
            raise TypeError("Static dict fixture required")
        _no_credentials(payload)
        canonical = json.dumps(payload, sort_keys=True, separators=(",",":"),
                               ensure_ascii=False, allow_nan=False)
        return cls(provider, endpoint, canonical)

    def parsed(self):
        # Return new object each time. Never expose a mutable internal dict.
        return json.loads(self.canonical_response_json)


@dataclass(frozen=True)
class DryRunConformance:
    run: BridgeRun
    endpoint_order: tuple[str, ...]
    fixture_only: bool = True

    @property
    def live_mcp_deployed(self):
        return False

    @property
    def data_rights_verified(self):
        return False

    @property
    def production_authorized(self):
        return False

    @property
    def actionable(self):
        return False


class FixtureOnlyD1HostHarness:
    """Test the exact P0.16 callbacks as static envelopes, with no network."""
    def __init__(self, *, ssi: StaticMcpFixture,
                 dnse: StaticMcpFixture | None, clock_utc: datetime):
        if not isinstance(ssi, StaticMcpFixture) or ssi.provider is not D1Provider.SSI:
            raise TypeError("Explicit SSI fixture required")
        if dnse is not None and (
            not isinstance(dnse, StaticMcpFixture)
            or dnse.provider is not D1Provider.DNSE
        ):
            raise TypeError("Optional fallback must be typed DNSE fixture")
        _utc(clock_utc)
        self._ssi = ssi
        self._dnse = dnse
        self._clock = clock_utc
        self._used = False

    def run_once(self, request: D1ReferenceRequest) -> DryRunConformance:
        if self._used:
            raise PermissionError("Fixture session is one-shot; replay is explicit")
        if not isinstance(request, D1ReferenceRequest):
            raise TypeError("Typed D1 reference request required")
        self._used = True
        calls = []
        def ssi_call(args):
            calls.append("SSI.marketdata_list_daily_stock_infor")
            if args != {
                "symbol":request.symbol, "range":"1d",
                "toDate":request.session_date_local.strftime("%d/%m/%Y"),
                "pageSize":5, "pageIndex":1,
            }:
                raise PermissionError("Non-allowlisted SSI method args")
            return self._ssi.parsed()
        def dnse_call(args):
            calls.append("DNSE.price_get_history")
            if args != {"symbol":request.symbol}:
                raise PermissionError("Non-allowlisted DNSE method args")
            if self._dnse is None:
                raise PermissionError("DNSE not provisioned for this fixture")
            return self._dnse.parsed()
        bridge = ReadOnlyMcpD1Bridge(
            ssi_call, dnse_call, lambda: self._clock,
            ProviderSeparatedReferenceCache(),
        )
        result = bridge.run(request)
        return DryRunConformance(result, tuple(calls))
