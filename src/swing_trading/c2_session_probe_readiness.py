"""C2C: offline, metadata-only readiness contract for future VN live-session probes.

Never calls SSI/DNSE/VCBS, schedules polling, persists vendor data, grants
entitlements, authenticates venue/clock finality, ranks providers or trades.
Reported timings/bytes/source timestamps are untrusted caller observations.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from math import ceil
from statistics import median
from zoneinfo import ZoneInfo

from .incremental_cache import Provider
from .c2_source_capability_audit import ConnectedEndpoint, DataNeed, endpoint_contract

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


class EvidenceKind(str, Enum):
    SYNTHETIC = "SYNTHETIC"
    CALLER_REPORTED_READ_ONLY = "CALLER_REPORTED_READ_ONLY"


class SessionPhase(str, Enum):
    PREOPEN = "PREOPEN"
    ATO = "ATO"
    CONTINUOUS_AM = "CONTINUOUS_AM"
    LUNCH = "LUNCH"
    CONTINUOUS_PM = "CONTINUOUS_PM"
    ATC = "ATC"
    POSTCLOSE = "POSTCLOSE"
    UNKNOWN = "UNKNOWN"


class ProbeError(str, Enum):
    NONE = "NONE"
    TRANSPORT = "TRANSPORT"
    TIMEOUT = "TIMEOUT"
    RATE_LIMIT = "RATE_LIMIT"
    PROVIDER = "PROVIDER"
    SCHEMA = "SCHEMA"
    UNKNOWN = "UNKNOWN"


class ByteMeasurement(str, Enum):
    UNMEASURED = "UNMEASURED"
    HTTP_RESPONSE_BODY = "HTTP_RESPONSE_BODY"
    NETWORK_WIRE_TOTAL = "NETWORK_WIRE_TOTAL"


def _require_utc(t: datetime) -> datetime:
    if (not isinstance(t, datetime) or t.tzinfo is None
            or t.utcoffset() != timedelta(0)):
        raise ValueError("Explicit UTC clock required")
    return t.astimezone(timezone.utc)


def _natural(n: int, field: str) -> None:
    if type(n) is not int or n < 0:
        raise ValueError(field + " must be a nonnegative integer")


@dataclass(frozen=True)
class SessionProbe:
    """A single untrusted, caller-supplied metadata observation, never a quote."""
    provider: Provider
    endpoint: ConnectedEndpoint
    need: DataNeed
    target_symbol: str
    venue: str
    requested_scope: str
    session_date: date
    phase: SessionPhase
    origin: EvidenceKind
    observed_at_utc: datetime
    client_monotonic_elapsed_ns: int
    success: bool
    error: ProbeError
    returned_rows: int
    provisional_rows: int = 0
    changed_closed_rows_reported: int = 0
    byte_measurement: ByteMeasurement = ByteMeasurement.UNMEASURED
    measured_bytes: int | None = None
    estimated_serialized_json_bytes: int | None = None
    reported_provider_timestamp_utc: datetime | None = None
    calendar_verified: bool = False
    source_authenticated: bool = False
    retention_authorized: bool = False

    def __post_init__(self) -> None:
        if (not isinstance(self.provider, Provider)
                or not isinstance(self.endpoint, ConnectedEndpoint)
                or not isinstance(self.need, DataNeed)
                or not isinstance(self.phase, SessionPhase)
                or not isinstance(self.origin, EvidenceKind)
                or not isinstance(self.error, ProbeError)
                or not isinstance(self.byte_measurement, ByteMeasurement)):
            raise TypeError("Typed provider/endpoint/task/phase/evidence/error/byte mode required")
        contract = endpoint_contract(self.endpoint)
        if contract.provider is not self.provider or contract.need is not self.need:
            raise ValueError("Connected endpoint does not serve this provider/task")
        if (not isinstance(self.target_symbol, str)
                or not (1 <= len(self.target_symbol) <= 15)
                or not self.target_symbol.isalnum()
                or not self.target_symbol.isupper()):
            raise ValueError("Normalized uppercase instrument required")
        if self.venue not in ("HOSE", "HNX", "UPCOM"):
            raise ValueError("Explicit Vietnam exchange required")
        if not isinstance(self.requested_scope, str) or not self.requested_scope.strip():
            raise ValueError("Explicit endpoint request scope required")
        if type(self.session_date) is not date:
            raise TypeError("Explicit local calendar date required")
        clock = _require_utc(self.observed_at_utc)
        if clock.astimezone(VN_TZ).date() != self.session_date:
            raise ValueError("Caller session date must match Vietnam-local observation date")
        if type(self.client_monotonic_elapsed_ns) is not int or self.client_monotonic_elapsed_ns <= 0:
            raise ValueError("Positive client monotonic elapsed nanoseconds required")
        if type(self.success) is not bool:
            raise TypeError("Explicit success boolean required")
        if self.success != (self.error is ProbeError.NONE):
            raise ValueError("Error code and success disagree")
        for name in ("returned_rows", "provisional_rows", "changed_closed_rows_reported"):
            _natural(getattr(self, name), name)
        if (self.provisional_rows > self.returned_rows
                or self.changed_closed_rows_reported > self.returned_rows
                or (not self.success and self.returned_rows != 0)):
            raise ValueError("Impossible success/row count combination")
        if not isinstance(self.byte_measurement, ByteMeasurement):
            raise TypeError("Typed byte basis required")
        if self.byte_measurement is ByteMeasurement.UNMEASURED:
            if self.measured_bytes is not None:
                raise ValueError("Unmeasured bytes must be absent")
        elif (type(self.measured_bytes) is not int or self.measured_bytes <= 0):
            raise ValueError("Measured transfer must be a positive integer")
        if self.estimated_serialized_json_bytes is not None:
            _natural(self.estimated_serialized_json_bytes, "estimated_serialized_json_bytes")
        if self.reported_provider_timestamp_utc is not None:
            source_clock = _require_utc(self.reported_provider_timestamp_utc)
            if source_clock > clock:
                raise ValueError("Future claimed source timestamp cannot establish freshness")
        if any(type(x) is not bool for x in
               (self.calendar_verified, self.source_authenticated, self.retention_authorized)):
            raise TypeError("Explicit authority flags required")
        if self.calendar_verified or self.source_authenticated or self.retention_authorized:
            raise ValueError("Caller-reported metadata cannot grant provider or venue authority")

    @property
    def elapsed_ms(self) -> float:
        return self.client_monotonic_elapsed_ns / 1_000_000


@dataclass(frozen=True)
class SessionProbeSummary:
    """Per identical source/task/instrument/venue/scope/phase statistics only."""
    provider: Provider
    endpoint: ConnectedEndpoint
    need: DataNeed
    venue: str
    phase: SessionPhase
    attempted: int
    succeeded: int
    failed: int
    empty_successes: int
    distinct_local_dates: int
    median_elapsed_ms: float | None
    p95_elapsed_ms: float | None
    measured_network_wire_samples: int
    median_network_wire_bytes: float | None
    reported_corrections: int
    reported_provisional_rows: int
    reported_source_older_than_5m: int
    official_session_verified: bool = False
    independent_source_freshness_verified: bool = False
    provider_sla_verified: bool = False
    equal_server_workload_verified: bool = False
    cache_rights_verified: bool = False
    network_delta_supported: bool = False
    router_eligible: bool = False

    def __post_init__(self) -> None:
        if any((self.official_session_verified, self.independent_source_freshness_verified,
                self.provider_sla_verified, self.equal_server_workload_verified,
                self.cache_rights_verified, self.network_delta_supported,
                self.router_eligible)):
            raise ValueError("Untrusted C2C probe cannot certify market, rights or router")


def summarize_session_probes(samples: tuple[SessionProbe, ...], *,
                             min_successes: int = 5) -> tuple[SessionProbeSummary, ...]:
    """No network calls. No cross-source ranking. No quote values in results."""
    if not isinstance(samples, tuple) or any(not isinstance(s, SessionProbe) for s in samples):
        raise TypeError("Immutable typed probe tuple required")
    if type(min_successes) is not int or min_successes < 5:
        raise ValueError("At least five successful samples for descriptive statistics")
    if len(samples) > 2000:
        raise ValueError("Bound transient benchmark sample count")
    groups: dict[tuple, list[SessionProbe]] = {}
    for s in samples:
        key = (s.provider, s.endpoint, s.need, s.target_symbol, s.venue,
               s.requested_scope, s.phase)
        groups.setdefault(key, []).append(s)
    output: list[SessionProbeSummary] = []
    for key, group in sorted(groups.items(), key=lambda pair: tuple(str(v) for v in pair[0])):
        ok = [s for s in group if s.success and s.returned_rows > 0]
        elapsed = sorted(s.elapsed_ms for s in ok)
        enough = len(elapsed) >= min_successes
        wire = sorted(s.measured_bytes for s in ok
                      if s.byte_measurement is ByteMeasurement.NETWORK_WIRE_TOTAL
                      and s.measured_bytes is not None)
        old = sum(1 for s in ok if s.reported_provider_timestamp_utc is not None
                  and (s.observed_at_utc-s.reported_provider_timestamp_utc).total_seconds() > 300)
        output.append(SessionProbeSummary(
            provider=key[0], endpoint=key[1], need=key[2], venue=key[4], phase=key[6],
            attempted=len(group), succeeded=len(ok),
            failed=sum(not s.success for s in group),
            empty_successes=sum(s.success and s.returned_rows == 0 for s in group),
            distinct_local_dates=len({s.session_date for s in group}),
            median_elapsed_ms=float(median(elapsed)) if enough else None,
            p95_elapsed_ms=elapsed[ceil(0.95*len(elapsed))-1] if enough else None,
            measured_network_wire_samples=len(wire),
            median_network_wire_bytes=float(median(wire)) if enough and len(wire)>=min_successes else None,
            reported_corrections=sum(s.changed_closed_rows_reported for s in ok),
            reported_provisional_rows=sum(s.provisional_rows for s in ok),
            reported_source_older_than_5m=old))
    return tuple(output)


@dataclass(frozen=True)
class SessionCoverage:
    """Review checklist, NOT certification of a live trading-session sample."""
    provider: Provider
    endpoint: ConnectedEndpoint
    venue: str
    observed_dates: int
    observed_phases: tuple[SessionPhase, ...]
    weekend_observations: int
    auction_observations: int
    measured_wire_observations: int
    missing_review_gates: tuple[str, ...]
    validated_market_session: bool = False
    authorized_for_router: bool = False

    def __post_init__(self) -> None:
        if self.validated_market_session or self.authorized_for_router:
            raise ValueError("Caller data cannot certify official session or trading route")


def session_coverage(samples: tuple[SessionProbe, ...]) -> tuple[SessionCoverage, ...]:
    """Explicitly surface evidence gaps; weekends are not live market sessions."""
    if not isinstance(samples, tuple) or any(not isinstance(s, SessionProbe) for s in samples):
        raise TypeError("Immutable typed probe tuple required")
    if len(samples) > 2000:
        raise ValueError("Bound transient sample count")
    groups: dict[tuple, list[SessionProbe]] = {}
    for s in samples:
        groups.setdefault((s.provider, s.endpoint, s.venue), []).append(s)
    out = []
    for (provider, endpoint, venue), g in sorted(groups.items(), key=lambda item: tuple(str(v) for v in item[0])):
        weekdays = [s for s in g if s.session_date.weekday() < 5]
        phases = tuple(sorted({s.phase for s in weekdays}, key=lambda phase: phase.value))
        auction = sum(s.phase in (SessionPhase.ATO, SessionPhase.ATC) for s in weekdays)
        wire = sum(s.byte_measurement is ByteMeasurement.NETWORK_WIRE_TOTAL for s in weekdays)
        gates = []
        if len({s.session_date for s in weekdays}) < 2:
            gates.append("MULTIPLE_WEEKDAY_SESSIONS_MISSING")
        if not (SessionPhase.CONTINUOUS_AM in phases or SessionPhase.CONTINUOUS_PM in phases):
            gates.append("CONTINUOUS_PHASE_MISSING")
        if auction == 0:
            gates.append("AUCTION_PHASE_MISSING")
        if wire == 0:
            gates.append("ACTUAL_CLIENT_WIRE_MEASUREMENTS_MISSING")
        gates.extend(("INDEPENDENT_EXCHANGE_CALENDAR_AND_FINALITY_MISSING",
                      "PROVIDER_ENTITLEMENT_AND_SOURCE_REVISION_PROOF_MISSING",
                      "COMPARABLE_SERVER_SCOPE_AND_LIVE_SLI_VALIDATION_MISSING"))
        out.append(SessionCoverage(provider, endpoint, venue,
                                   len({s.session_date for s in weekdays}), phases,
                                   len(g)-len(weekdays), auction, wire, tuple(gates)))
    return tuple(out)


def require_authorized_session_metrics(*_args: object, **_kwargs: object) -> None:
    raise PermissionError("C2C caller-reported measurements cannot authorize provider routing, caching or trading")
