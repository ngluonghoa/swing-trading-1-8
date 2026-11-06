"""P0.11 source-aligned intraday cumulative-volume RVOL_TOD candidate.

The true same-local-slot denominator is the mean cumulative volume of
20 distinct PRIOR sessions, not 20 prior candles, not RVOL_TF and not
daily volume. All quality claims remain supplied evidence, not SSI
entitlement/calendar validation. NO live signals/trading authority.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum

from .causal_indicators import (
    CausalIndicatorResult, IndicatorState, VolumeSessionClass,
    _source_context, _qualified,
)
from .market_data import Timeframe
from .replay import require_utc
from .source_quality import ResolvedBarSnapshotV12


_VN_OFFSET = timezone(timedelta(hours=7))
_SUPPORTED_TF = frozenset({Timeframe.M1, Timeframe.M5, Timeframe.M15})


class CumulativeVolumeDefinition(str, Enum):
    MATCHED_CONTINUOUS_ONLY = "MATCHED_CONTINUOUS_ONLY"
    MATCHED_INCLUDING_AUCTIONS = "MATCHED_INCLUDING_AUCTIONS"


@dataclass(frozen=True)
class TODCumulativeObservation:
    """Synthetic-friendly, source-referenced *claim* for one closed slot.

    A complete minute-by-minute source reconstruction/parity proof
    and a versioned official exchange calendar are not provided here.
    """
    snapshot: ResolvedBarSnapshotV12
    trading_date_local: date
    slot_end_local_hhmm: str
    session_class: VolumeSessionClass
    elapsed_trading_minutes: int
    cumulative_matched_volume: int | None
    volume_definition: CumulativeVolumeDefinition
    volume_event_id: str
    cumulative_first_known_utc: datetime
    cumulative_verified_utc: datetime
    volume_policy_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot, ResolvedBarSnapshotV12):
            raise TypeError("v1.2 resolved bar required")
        if not isinstance(self.trading_date_local, date) or isinstance(
            self.trading_date_local, datetime
        ):
            raise TypeError("Explicit local trading date required")
        if (not isinstance(self.slot_end_local_hhmm, str)
                or len(self.slot_end_local_hhmm) != 5
                or self.slot_end_local_hhmm[2] != ":"):
            raise ValueError("Slot must use local HH:MM")
        try:
            hour, minute = map(int, (
                self.slot_end_local_hhmm[:2], self.slot_end_local_hhmm[3:]
            ))
            if not 0 <= hour <= 23 or not 0 <= minute <= 59:
                raise ValueError("Invalid time")
        except (TypeError, ValueError) as exc:
            raise ValueError("Slot must use valid local HH:MM") from exc
        if not isinstance(self.session_class, VolumeSessionClass):
            raise TypeError("Explicit session segment class required")
        if (type(self.elapsed_trading_minutes) is not int
                or self.elapsed_trading_minutes <= 0):
            raise ValueError("Positive explicit elapsed trading minutes required")
        if (self.cumulative_matched_volume is not None
                and (type(self.cumulative_matched_volume) is not int
                     or self.cumulative_matched_volume < 0)):
            raise ValueError("Cumulative volume must be nonnegative int or unknown")
        if not isinstance(self.volume_definition, CumulativeVolumeDefinition):
            raise TypeError("Explicit matched-volume definition required")
        for name in ("volume_event_id", "volume_policy_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(name + " must be explicit nonempty text")
        require_utc(self.cumulative_first_known_utc)
        require_utc(self.cumulative_verified_utc)
        if self.cumulative_verified_utc < self.cumulative_first_known_utc:
            raise ValueError("Cumulative verification predates first knowledge")


def _validate_observation(item, *, as_of_utc, cutoff_utc):
    """Return (row, reason); never silently fix source conflicts."""
    row = _qualified(item.snapshot, as_of_utc, cutoff_utc)
    if row is None:
        return None, "CLOSED_BAR_OR_SOURCE_NOT_QUALIFIED"
    if row.market_bar_key.timeframe not in _SUPPORTED_TF:
        return None, "RVOL_TOD_REQUIRES_NATIVE_INTRADAY_TF"
    local_end = row.bar_end_utc.astimezone(_VN_OFFSET)
    if (local_end.date() != item.trading_date_local
            or local_end.strftime("%H:%M") != item.slot_end_local_hhmm):
        return None, "SLOT_END_NOT_EXCHANGE_LOCAL_CLOCK"
    if item.session_class is VolumeSessionClass.DAILY:
        return None, "DAILY_SESSION_CLASS_NOT_TOD"
    if (item.cumulative_matched_volume is None
            or row.volume is None
            or item.cumulative_matched_volume < row.volume):
        return None, "CUMULATIVE_VOLUME_NOT_SOURCE_USABLE"
    if item.volume_event_id not in row.source_event_ids:
        return None, "CUMULATIVE_EVENT_NOT_LINKED_TO_SOURCE_BAR"
    if (item.cumulative_first_known_utc < row.bar_end_utc
            or item.cumulative_verified_utc < row.verified_at_utc
            or item.cumulative_first_known_utc > cutoff_utc
            or item.cumulative_verified_utc > cutoff_utc):
        return None, "CUMULATIVE_EVIDENCE_NOT_CAUSALLY_KNOWN"
    return row, ""


def calculate_rvol_tod20(
    target: TODCumulativeObservation,
    prior_sessions: tuple[TODCumulativeObservation, ...],
    *,
    as_of_utc: datetime,
) -> CausalIndicatorResult:
    """Source-lineage-gated SAME-LOCAL-SLOT cumulative RVOL (N=20).

    The 20 prior observations must belong to 20 DIFFERENT market dates.
    Their selected price-bar and cumulative snapshots have to be known before
    the target bar STARTS. There is no approval of historical completeness.
    """
    require_utc(as_of_utc)

    def finish(state, reason, value=None, count=0):
        return CausalIndicatorResult(
            "RVOL_TOD20", as_of_utc, state, reason, value, count,
            "RVOL_TOD_SAME_SLOT_20_CANDIDATE_V0_1",
        )

    if not isinstance(target, TODCumulativeObservation):
        return finish(IndicatorState.BLOCKED, "INVALID_TARGET_TYPE")
    if (not isinstance(prior_sessions, tuple)
            or any(not isinstance(x, TODCumulativeObservation) for x in prior_sessions)):
        return finish(IndicatorState.BLOCKED, "INVALID_IMMUTABLE_PRIOR_SESSIONS")
    if len(prior_sessions) != 20:
        return finish(IndicatorState.BLOCKED, "REQUIRE_EXACTLY_20_PRIOR_SESSIONS")

    current, issue = _validate_observation(
        target, as_of_utc=as_of_utc, cutoff_utc=as_of_utc,
    )
    if current is None:
        return finish(IndicatorState.BLOCKED, "TARGET_" + issue)

    cutoff_utc = current.market_bar_key.bar_start_utc
    context = _source_context(current)
    previous_date = None
    previous_end = None
    total = 0
    seen_sessions = set()
    for item in prior_sessions:
        bar, issue = _validate_observation(
            item, as_of_utc=as_of_utc, cutoff_utc=cutoff_utc,
        )
        if bar is None:
            return finish(IndicatorState.BLOCKED, "PRIOR_" + issue)
        if _source_context(bar) != context:
            return finish(IndicatorState.BLOCKED, "PRIOR_SOURCE_BASIS_OR_POLICY_MISMATCH")
        if (item.slot_end_local_hhmm != target.slot_end_local_hhmm
                or item.session_class is not target.session_class
                or item.elapsed_trading_minutes != target.elapsed_trading_minutes
                or item.volume_definition is not target.volume_definition
                or item.volume_policy_version != target.volume_policy_version):
            return finish(IndicatorState.BLOCKED, "LOCAL_SLOT_SEGMENT_OR_VOLUME_POLICY_MISMATCH")
        session_id = bar.market_bar_key.session_period_id
        if (item.trading_date_local >= target.trading_date_local
                or session_id in seen_sessions
                or (previous_date is not None
                    and item.trading_date_local <= previous_date)
                or (previous_end is not None
                    and bar.market_bar_key.bar_start_utc < previous_end)):
            return finish(IndicatorState.BLOCKED, "DUPLICATE_OR_NONPRIOR_MARKET_SESSION")
        seen_sessions.add(session_id)
        previous_date = item.trading_date_local
        previous_end = bar.bar_end_utc
        total += item.cumulative_matched_volume

    if total <= 0:
        return finish(IndicatorState.BLOCKED, "ZERO_PRIOR_CUMULATIVE_DENOMINATOR")
    value = Decimal(target.cumulative_matched_volume) * Decimal(20) / Decimal(total)
    return finish(
        IndicatorState.COMPUTED_UNCALIBRATED,
        "SAME_LOCAL_SLOT_MATH_ONLY_CUMULATIVE_SOURCE_AND_MARKET_UNVERIFIED",
        value, 21,
    )
