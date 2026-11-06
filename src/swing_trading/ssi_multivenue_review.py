"""P0.13 cross-venue SSI read-only parity evidence review.

This aggregation only checks internal consistency of separately observed
intraday/daily SSI responses. It is not provider-independent source
verification, market coverage/entitlement or trade/backtest authorization.
"""
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from .replay import require_utc
from .ssi_volume_parity import (
    ParityState, SsiIntradaySample, SsiDailyMatchedReceipt,
    audit_ssi_intraday_daily_volume,
)

VENUES = ("HOSE", "HNX", "UPCOM")


class MatrixState(str, Enum):
    BLOCKED = "BLOCKED"
    PARTIAL_UNCERTIFIED = "PARTIAL_UNCERTIFIED"
    ALL_VENUES_OBSERVED_UNCERTIFIED = "ALL_VENUES_OBSERVED_UNCERTIFIED"


@dataclass(frozen=True)
class SsiVenueSample:
    intraday: SsiIntradaySample
    daily: SsiDailyMatchedReceipt

    def __post_init__(self) -> None:
        if not isinstance(self.intraday, SsiIntradaySample):
            raise TypeError("Typed intraday sample required")
        if not isinstance(self.daily, SsiDailyMatchedReceipt):
            raise TypeError("Typed daily receipt required")


@dataclass(frozen=True)
class SsiMatrixReview:
    state: MatrixState
    reason: str
    sample_count: int
    matched_count: int
    counts_by_venue: tuple[tuple[str, int], ...]
    blocked_samples: tuple[tuple[str, str, date, str], ...]
    provider_independent: bool = False
    timestamp_semantics_certified: bool = False
    full_minutes_certified: bool = False
    source_entitlement_certified: bool = False
    suitable_for_rvol_tod: bool = False
    actionable: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.state, MatrixState) or not self.reason:
            raise ValueError("Explicit state and reason required")
        if (type(self.sample_count) is not int or type(self.matched_count) is not int
                or self.sample_count < 0 or self.matched_count < 0
                or self.matched_count > self.sample_count):
            raise ValueError("Invalid matrix counts")
        if (not isinstance(self.counts_by_venue, tuple)
                or not isinstance(self.blocked_samples, tuple)):
            raise TypeError("Immutable audit inventories required")
        if any((
            self.provider_independent, self.timestamp_semantics_certified,
            self.full_minutes_certified, self.source_entitlement_certified,
            self.suitable_for_rvol_tod, self.actionable,
        )):
            raise ValueError("P0.13 matrix never certifies data or actions")


def evaluate_ssi_venue_matrix(
    samples: tuple[SsiVenueSample, ...], *, as_of_utc: datetime,
) -> SsiMatrixReview:
    """Re-run all P0.12 checks, not accept caller-supplied pass flags.

    All venues observed is about *sample distribution*, NOT an exchange
    calendar, first-known backtest replay or independent source parity.
    """
    require_utc(as_of_utc)
    if (not isinstance(samples, tuple)
            or any(not isinstance(item, SsiVenueSample) for item in samples)):
        raise TypeError("Immutable typed SSI sample tuple required")

    def finish(state, reason, matched, counts, blocked):
        return SsiMatrixReview(
            state, reason, len(samples), matched,
            tuple((exchange, counts[exchange]) for exchange in VENUES),
            tuple(blocked),
        )

    counts = {exchange: 0 for exchange in VENUES}
    seen = set()
    blocked = []
    matched = 0
    for item in samples:
        i = item.intraday
        key = (i.exchange, i.symbol, i.expected_trading_date)
        if i.exchange not in VENUES:
            blocked.append((i.exchange, i.symbol, i.expected_trading_date,
                            "UNSUPPORTED_OR_UNVERIFIED_EXCHANGE"))
            continue
        if key in seen:
            blocked.append((i.exchange, i.symbol, i.expected_trading_date,
                            "DUPLICATE_SYMBOL_VENUE_DATE_SAMPLE"))
            continue
        seen.add(key)
        counts[i.exchange] += 1
        result = audit_ssi_intraday_daily_volume(
            item.intraday, item.daily, as_of_utc=as_of_utc,
        )
        if result.state is not ParityState.MATCH_UNCERTIFIED:
            blocked.append((i.exchange, i.symbol, i.expected_trading_date,
                            result.reason))
        else:
            matched += 1
    if blocked:
        return finish(MatrixState.BLOCKED,
                      "ONE_OR_MORE_SAMPLES_NOT_CAUSALLY_DIAGNOSTIC_MATCHED",
                      matched, counts, blocked)
    if len(samples) == 0:
        return finish(MatrixState.BLOCKED, "NO_OBSERVED_SSI_SAMPLES",
                      0, counts, ())
    if any(counts[venue] == 0 for venue in VENUES):
        return finish(MatrixState.PARTIAL_UNCERTIFIED,
                      "MISSING_ONE_OR_MORE_VENUE_SAMPLE_GROUPS",
                      matched, counts, ())
    return finish(MatrixState.ALL_VENUES_OBSERVED_UNCERTIFIED,
                  "AGGREGATE_TOTALS_EQUAL_BUT_PROVIDER_AND_CALENDAR_UNCERTIFIED",
                  matched, counts, ())
