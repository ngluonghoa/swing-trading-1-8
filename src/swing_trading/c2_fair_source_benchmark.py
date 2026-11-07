"""C2B: offline, metadata-only, quality-first three-provider comparison.

No MCP I/O, raw market-data persistence, authorization, source certification,
trade execution, automatic polling or actual trading-session benchmark.
All inputs are caller-supplied, so every output remains REFERENCE_ONLY.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from math import ceil
from statistics import median
from typing import Iterable

from .incremental_cache import Provider
from .c2_source_capability_audit import ConnectedEndpoint, DataNeed, endpoint_contract


class EvidenceOrigin(str, Enum):
    SYNTHETIC = "SYNTHETIC"
    CONNECTED_READ_ONLY_CALLER_REPORTED = "CONNECTED_READ_ONLY_CALLER_REPORTED"


class PriceBasis(str, Enum):
    RAW = "RAW"
    ADJUSTED = "ADJUSTED"
    UNVERIFIED = "UNVERIFIED"


class VolumeBasis(str, Enum):
    MATCHED = "MATCHED"
    TOTAL_WITH_DEALS = "TOTAL_WITH_DEALS"
    UNVERIFIED = "UNVERIFIED"


class ComparisonStatus(str, Enum):
    COMPARABLE_REPORTED = "COMPARABLE_REPORTED"
    BLOCKED_BASIS = "BLOCKED_BASIS"
    BLOCKED_VOLUME_SCOPE = "BLOCKED_VOLUME_SCOPE"
    BLOCKED_NO_OVERLAP = "BLOCKED_NO_OVERLAP"


class ComparisonAxis(str, Enum):
    PRICE = "PRICE"
    VOLUME = "VOLUME"


def _utc(value: datetime) -> datetime:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() != timedelta(0)):
        raise ValueError("Explicit UTC timestamp required")
    return value.astimezone(timezone.utc)


def _positive_money(x: Decimal) -> Decimal:
    if not isinstance(x, Decimal) or not x.is_finite() or x <= 0:
        raise ValueError("Positive finite Decimal price in VND required")
    return x


@dataclass(frozen=True)
class D1Target:
    symbol: str
    exchange: str
    first_session: date
    last_session: date

    def __post_init__(self):
        if (not isinstance(self.symbol, str) or not self.symbol.isupper()
                or not 1 <= len(self.symbol) <= 15 or not self.symbol.isalnum()):
            raise ValueError("Uppercase normalized ticker required")
        if self.exchange not in ("HOSE", "HNX", "UPCOM"):
            raise ValueError("Explicit VN venue required")
        if (type(self.first_session) is not date or type(self.last_session) is not date
                or self.first_session > self.last_session):
            raise ValueError("Ordered calendar date range required")
        if self.last_session - self.first_session > timedelta(days=93):
            raise ValueError("Bound C2B observation horizon to <=93 days")


@dataclass(frozen=True)
class CallerReportedProbe:
    """No raw response, symbol-specific prices, credentials or account fields."""
    provider: Provider
    endpoint: ConnectedEndpoint
    task: DataNeed
    origin: EvidenceOrigin
    target: D1Target
    observed_at_utc: datetime
    elapsed_ms: int
    success: bool
    returned_rows: int
    common_target_rows: int
    approximate_json_bytes: int | None
    requested_scope: str
    market_session_probe: bool = False
    source_timestamp_authenticated: bool = False
    rights_verified: bool = False

    def __post_init__(self):
        if (not isinstance(self.provider, Provider) or not isinstance(self.endpoint, ConnectedEndpoint)
                or not isinstance(self.task, DataNeed) or not isinstance(self.origin, EvidenceOrigin)):
            raise TypeError("Typed provider/endpoint/task/origin required")
        if not isinstance(self.target, D1Target):
            raise TypeError("Exact workload target required")
        _utc(self.observed_at_utc)
        contract = endpoint_contract(self.endpoint)
        if contract.provider is not self.provider:
            raise ValueError("Endpoint/provider mismatch")
        if self.task not in (DataNeed.D1_OHLCV, DataNeed.MINUTE_OHLCV):
            raise ValueError("No quote/price-point substitution into OHLCV benchmark")
        if (self.endpoint in (ConnectedEndpoint.SSI_D1_DETAILED,
                              ConnectedEndpoint.DNSE_D1_HISTORY,
                              ConnectedEndpoint.VCBS_D1_WINDOW)) != (self.task is DataNeed.D1_OHLCV):
            raise ValueError("Endpoint/task mismatch: minute OHLCV not D1")
        if self.task is DataNeed.MINUTE_OHLCV and self.endpoint is not ConnectedEndpoint.SSI_INTRADAY_SESSION:
            raise ValueError("Only SSI session endpoint is minute OHLCV-style candidate")
        if type(self.elapsed_ms) is not int or self.elapsed_ms < 1:
            raise ValueError("Nonzero positive elapsed time required")
        if (type(self.returned_rows) is not int or type(self.common_target_rows) is not int
                or self.returned_rows < 0 or not 0 <= self.common_target_rows <= self.returned_rows):
            raise ValueError("Row counts must be consistent")
        if type(self.success) is not bool or (self.success and self.returned_rows == 0):
            raise ValueError("Successful observation requires rows")
        if (self.approximate_json_bytes is not None and
                (type(self.approximate_json_bytes) is not int or self.approximate_json_bytes < 0)):
            raise ValueError("Estimated bytes must be nonnegative integer")
        if not isinstance(self.requested_scope, str) or not self.requested_scope.strip():
            raise ValueError("Exact method request scope label required")
        if any(type(z) is not bool for z in (self.market_session_probe,
               self.source_timestamp_authenticated, self.rights_verified)):
            raise TypeError("Explicit capability flags required")
        if self.source_timestamp_authenticated or self.rights_verified:
            raise ValueError("Caller-reported benchmark cannot grant trust or source rights")


@dataclass(frozen=True)
class EndpointTimingSummary:
    provider: Provider
    endpoint: ConnectedEndpoint
    total: int
    failures: int
    median_ms: float | None
    p95_ms: int | None
    median_payload_json_estimate: float | None
    comparable_cross_provider_latency: bool = False
    verified_market_session_p95: bool = False
    provider_sla_verified: bool = False
    authorized_for_router: bool = False

    def __post_init__(self):
        if any((self.comparable_cross_provider_latency, self.verified_market_session_p95,
                self.provider_sla_verified, self.authorized_for_router)):
            raise ValueError("Offline benchmark cannot authorize or establish fair API latency")


def summarize_endpoint_probes(observations: tuple[CallerReportedProbe, ...], *,
                              minimum_samples: int = 5) -> tuple[EndpointTimingSummary, ...]:
    """Descriptive per-endpoint statistics; NEVER ranks incompatible response scopes."""
    if not isinstance(observations, tuple) or any(not isinstance(p, CallerReportedProbe) for p in observations):
        raise TypeError("Immutable typed probe tuple required")
    if type(minimum_samples) is not int or minimum_samples < 5:
        raise ValueError("At least 5 probes for descriptive distribution")
    if len(observations) > 1000:
        raise ValueError("Bound observed probe count")
    groups: dict[tuple[Provider, ConnectedEndpoint, DataNeed, D1Target, str], list[CallerReportedProbe]] = {}
    for item in observations:
        key = (item.provider, item.endpoint, item.task, item.target, item.requested_scope)
        groups.setdefault(key, []).append(item)
    output: list[EndpointTimingSummary] = []
    for (provider, endpoint, _task, _target, _scope), records in sorted(groups.items(), key=lambda x: tuple(str(z) for z in x[0])):
        successful = sorted(p.elapsed_ms for p in records if p.success)
        bytes_count = [p.approximate_json_bytes for p in records if p.success and p.approximate_json_bytes is not None]
        ready = len(records) >= minimum_samples and len(successful) >= minimum_samples
        output.append(EndpointTimingSummary(provider, endpoint, len(records),
                                            len(records)-len(successful),
                                            float(median(successful)) if ready else None,
                                            successful[ceil(0.95*len(successful))-1] if ready else None,
                                            float(median(bytes_count)) if ready and len(bytes_count)>=minimum_samples else None))
    return tuple(output)


@dataclass(frozen=True)
class TransientD1Row:
    """In-memory cross-source comparison input; never returned or saved by C2B."""
    provider: Provider
    target: D1Target
    session: date
    price_basis: PriceBasis
    volume_basis: VolumeBasis
    o_vnd: Decimal
    h_vnd: Decimal
    l_vnd: Decimal
    c_vnd: Decimal
    volume_shares: int
    provisional: bool = False
    provider_metadata_authenticated: bool = False
    venue_session_finality_verified: bool = False

    def __post_init__(self):
        if not isinstance(self.provider, Provider) or not isinstance(self.target, D1Target):
            raise TypeError("Typed source/target required")
        if type(self.session) is not date or not self.target.first_session <= self.session <= self.target.last_session:
            raise ValueError("Session outside comparison window")
        if not isinstance(self.price_basis, PriceBasis) or not isinstance(self.volume_basis, VolumeBasis):
            raise TypeError("Explicit price/volume basis required")
        o,h,l,c=(_positive_money(p) for p in (self.o_vnd,self.h_vnd,self.l_vnd,self.c_vnd))
        if not (l <= min(o,c) <= max(o,c) <= h):
            raise ValueError("Impossible OHLC order, reject row rather than include in parity")
        if type(self.volume_shares) is not int or self.volume_shares < 0:
            raise ValueError("Nonnegative integer shares required")
        if any(type(x) is not bool for x in (self.provisional,self.provider_metadata_authenticated,
                                          self.venue_session_finality_verified)):
            raise TypeError("Boolean flags required")
        if self.provider_metadata_authenticated or self.venue_session_finality_verified:
            raise ValueError("Transient caller input cannot authenticate source or finality")


@dataclass(frozen=True)
class ConditionalParity:
    provider_a: Provider
    provider_b: Provider
    axis: ComparisonAxis
    status: ComparisonStatus
    common_sessions: int
    comparable_sessions: int
    equal_sessions: int
    different_sessions: int
    provisional_excluded: int
    unknown_basis_excluded: int
    source_integrity_verified: bool = False
    exchange_authoritative: bool = False
    legal_retention_allowed: bool = False
    actionable: bool = False

    def __post_init__(self):
        if any((self.source_integrity_verified,self.exchange_authoritative,
                self.legal_retention_allowed,self.actionable)):
            raise ValueError("Caller-reported parity does not certify any source or trade")
        if self.equal_sessions+self.different_sessions != self.comparable_sessions:
            raise ValueError("Parity count disagreement")
        if self.comparable_sessions+self.provisional_excluded+self.unknown_basis_excluded != self.common_sessions:
            raise ValueError("Parity exclusions mismatch")


def compare_transient_d1_pair(a: tuple[TransientD1Row, ...], b: tuple[TransientD1Row, ...],
                              *, axis: ComparisonAxis) -> ConditionalParity:
    """Summarize comparable session counts ONLY, never expose market prices or dates.

    All source/basis fields are caller assertions. Equality is CONDITIONAL and
    cannot approve signals, licensing, source reliability, or cache retention.
    """
    if not isinstance(a, tuple) or not isinstance(b, tuple) or not isinstance(axis, ComparisonAxis):
        raise TypeError("Typed tuples and explicit axis required")
    if not a or not b or len(a)>500 or len(b)>500:
        raise ValueError("Both bounded source sequences required")
    if any(not isinstance(x,TransientD1Row) for x in (*a,*b)):
        raise TypeError("Typed market rows required")
    sa, sb = a[0].provider, b[0].provider
    if sa is sb:
        raise ValueError("Independent source pair required")
    target = a[0].target
    if any(z.provider is not sa or z.target != target for z in a) or any(z.provider is not sb or z.target != target for z in b):
        raise ValueError("Mixed provider/target/venue not comparable")
    da = {x.session:x for x in a}; db = {x.session:x for x in b}
    if len(da)!=len(a) or len(db)!=len(b):
        raise ValueError("Duplicate source session")
    common = sorted(set(da)&set(db))
    equal=different=provisional=unknown=0
    for session in common:
        x,y=da[session],db[session]
        if x.provisional or y.provisional:
            provisional+=1;continue
        basis=(x.price_basis,y.price_basis) if axis is ComparisonAxis.PRICE else (x.volume_basis,y.volume_basis)
        if basis[0] is not basis[1] or basis[0] in (PriceBasis.UNVERIFIED,VolumeBasis.UNVERIFIED):
            unknown+=1;continue
        if axis is ComparisonAxis.PRICE:
            same=(x.o_vnd,x.h_vnd,x.l_vnd,x.c_vnd)==(y.o_vnd,y.h_vnd,y.l_vnd,y.c_vnd)
        else:
            same=x.volume_shares==y.volume_shares
        if same:equal+=1
        else:different+=1
    status=(ComparisonStatus.BLOCKED_NO_OVERLAP if not common else
            ComparisonStatus.COMPARABLE_REPORTED if equal+different else
            ComparisonStatus.BLOCKED_BASIS if axis is ComparisonAxis.PRICE else ComparisonStatus.BLOCKED_VOLUME_SCOPE)
    return ConditionalParity(sa,sb,axis,status,len(common),equal+different,equal,different,provisional,unknown)


def require_benchmark_source_authority(_result: object) -> None:
    raise PermissionError("C2B benchmark is REFERENCE_ONLY; vendor rights, full source finality and storage are unverified")
