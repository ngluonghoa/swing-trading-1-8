"""P0.14 SSI read-only historical endpoint availability classification.

A successful empty intraday response for a date with positive daily matched
volume is an *unresolved source availability gap*, not a zero-volume day,
licence conclusion, deleted archive or completed minute coverage proof.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .replay import require_utc
from .ssi_volume_parity import (
    ParityState, SsiDailyMatchedReceipt, SsiIntradaySample,
    audit_ssi_intraday_daily_volume,
)


class HistoricalAvailabilityState(str, Enum):
    BLOCKED = "BLOCKED"
    INTRADAY_EMPTY_DAILY_TRADES_UNCERTIFIED = "INTRADAY_EMPTY_DAILY_TRADES_UNCERTIFIED"
    NONEMPTY_MATCHED_UNCERTIFIED = "NONEMPTY_MATCHED_UNCERTIFIED"


@dataclass(frozen=True)
class HistoricalAvailabilityReview:
    state: HistoricalAvailabilityState
    reason: str
    intraday_count: int
    daily_matched_volume: int | None
    intraday_total: int | None
    retention_limit_verified: bool = False
    provider_clock_certified: bool = False
    complete_m1_history_certified: bool = False
    source_entitlement_certified: bool = False
    actionable: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.state, HistoricalAvailabilityState) or not self.reason:
            raise ValueError("Typed historical audit required")
        if type(self.intraday_count) is not int or self.intraday_count < 0:
            raise ValueError("Nonnegative source row count required")
        for v in (self.daily_matched_volume, self.intraday_total):
            if v is not None and (type(v) is not int or v < 0):
                raise ValueError("Nonnegative integer volume or missing required")
        if any((self.retention_limit_verified, self.provider_clock_certified,
                self.complete_m1_history_certified,
                self.source_entitlement_certified, self.actionable)):
            raise ValueError("Read-only endpoint sample is not historical data certification")


def review_ssi_historical_day(
    intraday: SsiIntradaySample,
    daily: SsiDailyMatchedReceipt,
    *,
    as_of_utc: datetime,
) -> HistoricalAvailabilityReview:
    require_utc(as_of_utc)
    if not isinstance(intraday, SsiIntradaySample) or not isinstance(
        daily, SsiDailyMatchedReceipt
    ):
        raise TypeError("Typed SSI source receipts required")

    def finish(state, reason, total=None):
        return HistoricalAvailabilityReview(
            state, reason, len(intraday.rows), daily.total_match_volume, total
        )

    if (intraday.symbol != daily.symbol or intraday.exchange != daily.exchange
            or intraday.expected_trading_date != daily.trading_date):
        return finish(HistoricalAvailabilityState.BLOCKED, "INSTRUMENT_VENUE_DATE_MISMATCH")
    if (intraday.fetched_at_utc > as_of_utc
            or daily.fetched_at_utc > as_of_utc):
        return finish(HistoricalAvailabilityState.BLOCKED, "SOURCE_RECEIPT_AFTER_AUDIT_CLOCK")
    if daily.total_match_volume is None:
        return finish(HistoricalAvailabilityState.BLOCKED, "DAILY_MATCHED_VOLUME_MISSING")
    if not intraday.rows:
        if daily.total_match_volume > 0:
            return finish(
                HistoricalAvailabilityState.INTRADAY_EMPTY_DAILY_TRADES_UNCERTIFIED,
                "DAILY_MATCHED_TRADES_EXIST_BUT_INTRADAY_ENDPOINT_RETURNED_EMPTY",
            )
        return finish(HistoricalAvailabilityState.BLOCKED,
                      "BOTH_ZERO_OR_EMPTY_DOES_NOT_PROVE_OFFICIAL_NONTRADING_DAY")
    detail = audit_ssi_intraday_daily_volume(
        intraday, daily, as_of_utc=as_of_utc,
    )
    if detail.state is not ParityState.MATCH_UNCERTIFIED:
        return finish(HistoricalAvailabilityState.BLOCKED,
                      "INTRADAY_PARITY_" + detail.reason,
                      detail.summed_intraday_matched_volume)
    return finish(
        HistoricalAvailabilityState.NONEMPTY_MATCHED_UNCERTIFIED,
        "VOLUME_EQUAL_ONLY_HISTORY_LICENSE_AND_COMPLETENESS_OPEN",
        detail.summed_intraday_matched_volume,
    )
