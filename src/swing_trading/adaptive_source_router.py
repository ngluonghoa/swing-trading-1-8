"""C1C conservative, offline Adaptive Source Router for Swing Trading 1.8.

This chooses only REFERENCE CANDIDATES. Inputs are caller-supplied diagnostic
claims and ephemeral performance observations, not authenticated exchange,
vendor-rights, or market-data proof. No MCP I/O, licensed persistence,
actionable signals, broker calls, or background tasks occur in this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from statistics import median

from .incremental_cache import Provider


class SourceTask(str, Enum):
    D1_OHLCV = "D1_OHLCV"
    M1_OHLCV = "M1_OHLCV"  # Feed for derived M5/M15; not M5-native certification.


class PriceBasis(str, Enum):
    RAW = "RAW"
    ADJUSTED = "ADJUSTED"


class PriceUnit(str, Enum):
    VND = "VND"
    THOUSAND_VND = "THOUSAND_VND"


class RouteMode(str, Enum):
    REFERENCE_CANDIDATE = "REFERENCE_CANDIDATE"
    BLOCKED = "BLOCKED"


def _utc(value: datetime) -> datetime:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() != timedelta(0)):
        raise ValueError("Explicit UTC-aware timestamp required")
    return value.astimezone(timezone.utc)


# Contractually advertised feed scope, NOT independently verified rights/quality.
_D1 = (Provider.DNSE, Provider.SSI, Provider.VCBS)
_M1 = (Provider.SSI,)
_PRECEDENCE = {SourceTask.D1_OHLCV: _D1, SourceTask.M1_OHLCV: _M1}


def candidate_precedence(task: SourceTask) -> tuple[Provider, ...]:
    """DNSE D1; SSI M1-derived M5/M15; VCBS D1 reference verification.

    Not a global provider preference, and not permission to call/use the feed.
    """
    if not isinstance(task, SourceTask):
        raise TypeError("Explicit SourceTask required")
    return _PRECEDENCE[task]


@dataclass(frozen=True)
class DiagnosticObservation:
    """Caller-asserted normalization checks; never independently verified.

    No OHLCV, names, account positions, credentials, or source payload stored.
    Required booleans fail closed when any prerequisite is unconfirmed.
    """
    provider: Provider
    task: SourceTask
    price_basis: PriceBasis
    price_unit: PriceUnit
    observed_at_utc: datetime
    valid_until_utc: datetime
    native_ohlcv: bool
    complete: bool
    non_provisional: bool
    clock_and_calendar_checked: bool
    price_basis_checked: bool
    volume_scope_checked: bool
    corporate_action_checked: bool
    ohlc_invariants_checked: bool
    comparative_quality_checked: bool
    error_code: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.provider, Provider) or not isinstance(self.task, SourceTask):
            raise TypeError("Explicit provider/task enum required")
        if not isinstance(self.price_basis, PriceBasis) or not isinstance(self.price_unit, PriceUnit):
            raise TypeError("Explicit source unit and price basis required")
        if _utc(self.valid_until_utc) < _utc(self.observed_at_utc):
            raise ValueError("Observation expiry must not predate its clock")
        for name in ("native_ohlcv", "complete", "non_provisional",
                     "clock_and_calendar_checked", "price_basis_checked",
                     "volume_scope_checked", "corporate_action_checked",
                     "ohlc_invariants_checked", "comparative_quality_checked"):
            if type(getattr(self, name)) is not bool:
                raise TypeError("Explicit boolean diagnostic: " + name)
        if self.error_code is not None and (not isinstance(self.error_code, str)
                                            or not self.error_code.strip()):
            raise ValueError("Nonempty source error code required")


@dataclass(frozen=True)
class ProviderProbe:
    """Synthetic/reported timings for one provider+task, never a source receipt."""
    provider: Provider
    task: SourceTask
    measured_at_utc: datetime
    success: bool
    elapsed_ms: int

    def __post_init__(self) -> None:
        if not isinstance(self.provider, Provider) or not isinstance(self.task, SourceTask):
            raise TypeError("Typed provider and task required")
        _utc(self.measured_at_utc)
        if type(self.success) is not bool or type(self.elapsed_ms) is not int or self.elapsed_ms < 0:
            raise ValueError("Typed probe with nonnegative integer elapsed_ms required")
        if self.success and self.elapsed_ms == 0:
            raise ValueError("Successful measured request cannot claim zero milliseconds")


@dataclass(frozen=True)
class ProviderHealth:
    count: int
    successes: int
    failure_ratio: float
    median_success_ms: float | None
    consecutive_failures: int
    recent_circuit_open: bool


@dataclass(frozen=True)
class RouteDecision:
    mode: RouteMode
    task: SourceTask
    selected: Provider | None
    ordered_eligible: tuple[Provider, ...]
    rejected: tuple[tuple[Provider, str], ...]
    ranking_reason: str
    # This is a prototype decision over caller assertions, never authority.
    reference_only: bool = True
    source_authority_verified: bool = False
    rights_verified: bool = False
    persistence_authorized: bool = False
    indicator_eligible: bool = False
    trading_actionable: bool = False
    live_adapter_deployed: bool = False

    def __post_init__(self) -> None:
        if any((not self.reference_only, self.source_authority_verified,
                self.rights_verified, self.persistence_authorized,
                self.indicator_eligible, self.trading_actionable,
                self.live_adapter_deployed)):
            raise ValueError("Reference-only route cannot elevate source authorization")
        if self.mode is RouteMode.BLOCKED and (self.selected is not None or self.ordered_eligible):
            raise ValueError("Blocked route cannot select a source")
        if self.mode is RouteMode.REFERENCE_CANDIDATE and (
                self.selected is None or not self.ordered_eligible
                or self.selected is not self.ordered_eligible[0]):
            raise ValueError("Candidate selection must match first eligible")


def _gate(obs: DiagnosticObservation, task: SourceTask, basis: PriceBasis,
          now: datetime) -> str | None:
    if obs.task is not task:
        return "TASK_MISMATCH"
    if obs.provider not in candidate_precedence(task):
        return "FEED_DOES_NOT_PROVIDE_NATIVE_REQUIRED_OHLCV"
    if obs.price_basis is not basis:
        return "PRICE_BASIS_MISMATCH_OR_ADJUSTMENT_UNPROVEN"
    if obs.price_unit is not PriceUnit.VND:
        return "PRICE_UNIT_NOT_NORMALIZED_TO_VND"
    if obs.error_code is not None:
        return "SOURCE_ERROR:" + obs.error_code
    if obs.observed_at_utc > now or obs.valid_until_utc < now:
        return "SOURCE_FRESHNESS_UNCONFIRMED"
    fields = (
        ("native_ohlcv", "NATIVE_OHLCV_UNVERIFIED"),
        ("complete", "INCOMPLETE_COVERAGE"),
        ("non_provisional", "OPEN_BAR_NOT_FINAL"),
        ("clock_and_calendar_checked", "CALENDAR_OR_CLOCK_UNVERIFIED"),
        ("price_basis_checked", "PRICE_BASIS_UNVERIFIED"),
        ("volume_scope_checked", "VOLUME_SCOPE_UNVERIFIED"),
        ("corporate_action_checked", "CORPORATE_ACTION_REVISION_UNVERIFIED"),
        ("ohlc_invariants_checked", "INVALID_OR_UNVERIFIED_OHLC"),
        ("comparative_quality_checked", "SOURCE_PARITY_UNVERIFIED"),
    )
    for field, reason in fields:
        if getattr(obs, field) is not True:
            return reason
    return None


def _health(probes: tuple[ProviderProbe, ...], provider: Provider, task: SourceTask,
            now: datetime, *, horizon: timedelta, max_samples: int,
            cooldown: timedelta) -> ProviderHealth:
    relevant = sorted(
        (p for p in probes if p.provider is provider and p.task is task
         and now - horizon <= p.measured_at_utc <= now),
        key=lambda p: p.measured_at_utc,
    )[-max_samples:]
    n = len(relevant)
    successes = [p.elapsed_ms for p in relevant if p.success]
    consecutive = 0
    for item in reversed(relevant):
        if item.success:
            break
        consecutive += 1
    circuit = bool(relevant and consecutive >= 3 and now - relevant[-1].measured_at_utc <= cooldown)
    return ProviderHealth(n, len(successes), (n - len(successes)) / n if n else 0.0,
                          median(successes) if successes else None,
                          consecutive, circuit)


def preview_adaptive_route(
    *, task: SourceTask, price_basis: PriceBasis, as_of_utc: datetime,
    observations: tuple[DiagnosticObservation, ...],
    probes: tuple[ProviderProbe, ...] = (),
    metric_horizon: timedelta = timedelta(minutes=60),
    cooldown: timedelta = timedelta(minutes=10),
    minimum_comparable_samples: int = 5,
    max_samples: int = 20,
) -> RouteDecision:
    """Select a *reference candidate*, not actual source access or certification.

    Quality, compatibility and freshness gates run before performance ranking.
    Dynamic ranking is enabled only with enough *comparable* recent probes for
    every eligible provider. Otherwise conservative task precedence is used.
    An unstable source with 3 consecutive reported failures is cooled down.
    """
    if not isinstance(task, SourceTask) or not isinstance(price_basis, PriceBasis):
        raise TypeError("Typed task/basis required")
    now = _utc(as_of_utc)
    if (not isinstance(observations, tuple) or
            any(not isinstance(x, DiagnosticObservation) for x in observations) or
            not isinstance(probes, tuple) or any(not isinstance(x, ProviderProbe) for x in probes)):
        raise TypeError("Immutable typed diagnostics and probes required")
    if not isinstance(metric_horizon, timedelta) or metric_horizon <= timedelta(0):
        raise ValueError("Positive metric horizon required")
    if not isinstance(cooldown, timedelta) or cooldown <= timedelta(0):
        raise ValueError("Positive cooldown required")
    if (type(minimum_comparable_samples) is not int or minimum_comparable_samples < 3
            or type(max_samples) is not int or max_samples < minimum_comparable_samples):
        raise ValueError("Enough bounded comparable probe samples required")
    if len(set(x.provider for x in observations)) != len(observations):
        raise ValueError("Duplicate provider diagnostics cannot overwrite source evidence")

    accepted = []
    rejected: list[tuple[Provider, str]] = []
    stats = {}
    for source in candidate_precedence(task):
        observation = next((o for o in observations if o.provider is source), None)
        if observation is None:
            rejected.append((source, "NO_DIAGNOSTIC_OBSERVATION"))
            continue
        reason = _gate(observation, task, price_basis, now)
        if reason:
            rejected.append((source, reason))
            continue
        health = _health(probes, source, task, now,
                         horizon=metric_horizon, cooldown=cooldown,
                         max_samples=max_samples)
        stats[source] = health
        if health.recent_circuit_open:
            rejected.append((source, "RECENT_FAILURE_CIRCUIT_OPEN"))
            continue
        accepted.append(source)

    for obs in observations:
        if obs.provider not in candidate_precedence(task):
            rejected.append((obs.provider, "FEED_DOES_NOT_PROVIDE_NATIVE_REQUIRED_OHLCV"))

    if not accepted:
        return RouteDecision(RouteMode.BLOCKED, task, None, (), tuple(rejected),
                             "NO_COMPATIBLE_FRESH_DIAGNOSTIC_SOURCE")

    enough = all(stats[p].count >= minimum_comparable_samples and
                 stats[p].successes >= 1 for p in accepted)
    if enough and len(accepted) > 1:
        ranks = {p: i for i, p in enumerate(candidate_precedence(task))}
        # Latency measures are caller-supplied observed end-to-end probe time;
        # failures penalize instability. No static "DNSE is always faster" claim.
        accepted.sort(key=lambda p: (stats[p].median_success_ms +
                                     2500 * stats[p].failure_ratio, ranks[p]))
        ranking = "RECENT_COMPARABLE_LATENCY_AND_FAILURE_FEEDBACK_REFERENCE_ONLY"
    else:
        ranking = "TASK_SPECIFIC_DEFAULT_WHILE_PERFORMANCE_INSUFFICIENT"
    return RouteDecision(RouteMode.REFERENCE_CANDIDATE, task, accepted[0],
                         tuple(accepted), tuple(rejected), ranking)
