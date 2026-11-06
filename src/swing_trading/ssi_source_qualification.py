"""P0.5 source qualification primitives for SSI MCP read-only observations.

No network calls and no runtime data ingestion. This module is a conservative
pre-adapter that preserves contradictory endpoint date evidence and missing data
as BLOCKED/UNKNOWN. Only separately verified source semantics can authorize a
timestamp translation; it cannot authorize signals, historical backtests or use
of market-data rights.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from decimal import Decimal
from enum import Enum
import re
from zoneinfo import ZoneInfo

from .market_data import PriceBasis
from .replay import require_utc


_VN = ZoneInfo("Asia/Ho_Chi_Minh")
_DAY = re.compile(r"^([0-9]{2})/([0-9]{2})/([0-9]{4})$")
_STAMP = re.compile(
    r"^([0-9]{2})/([0-9]{2})/([0-9]{4}) ([0-9]{2}):([0-9]{2}):([0-9]{2})$"
)


class DateOrder(str, Enum):
    DAY_FIRST = "DD/MM/YYYY"
    MONTH_FIRST = "MM/DD/YYYY"
    UNKNOWN = "UNKNOWN"


class RecordAvailability(str, Enum):
    OBSERVED_UNVERIFIED = "OBSERVED_UNVERIFIED"
    EMPTY_UNKNOWN = "EMPTY_UNKNOWN"
    ERROR_BLOCKED = "ERROR_BLOCKED"


class ParityState(str, Enum):
    MISMATCH_BLOCKED = "MISMATCH_BLOCKED"
    MATCH_UNVERIFIED = "MATCH_UNVERIFIED"
    MISSING_UNKNOWN = "MISSING_UNKNOWN"


class SourceGate(str, Enum):
    BLOCKED = "BLOCKED"
    OBSERVED_UNVERIFIED = "OBSERVED_UNVERIFIED"


def _text(value: str, field: str):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(field + " must be nonempty text")


def _day(value: date):
    if type(value) is not date:
        raise TypeError("Trading day must be datetime.date, not datetime")


def _decimal(value: Decimal):
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise ValueError("Price must be finite nonnegative Decimal, never float")


@dataclass(frozen=True)
class EndpointTimestampPolicy:
    """Documented and observed conventions are intentionally separate.

    independently_confirmed only becomes True after external source review.
    timestamp_label_confirmed is distinct: minute start/end/last-trade semantics
    cannot be deduced from matching date strings.
    """
    endpoint_id: str
    policy_version: str
    documented_date_order: DateOrder
    observed_date_order: DateOrder
    independently_confirmed: bool
    timestamp_label_confirmed: bool

    def __post_init__(self):
        _text(self.endpoint_id, "endpoint_id")
        _text(self.policy_version, "policy_version")
        if not isinstance(self.documented_date_order, DateOrder) or not isinstance(
            self.observed_date_order, DateOrder
        ):
            raise TypeError("Date formats must be explicit typed conventions")
        if type(self.independently_confirmed) is not bool or type(
            self.timestamp_label_confirmed
        ) is not bool:
            raise TypeError("Both verification statuses must be explicit bool")

    @property
    def date_policy_consistent(self) -> bool:
        return (self.documented_date_order is not DateOrder.UNKNOWN
                and self.documented_date_order is self.observed_date_order)


@dataclass(frozen=True)
class TimestampAssessment:
    endpoint_id: str
    raw_text: str
    requested_day: date
    date_candidates: tuple[date, ...]
    interpreted_time_utc: datetime | None
    reason_code: str

    @property
    def usable_for_market_time(self) -> bool:
        return self.reason_code == "DATE_AND_CLOCK_SEMANTICS_VERIFIED"


def _candidate_day(first: int, second: int, year: int, order: DateOrder) -> date | None:
    if order is DateOrder.UNKNOWN:
        return None
    try:
        month, day = (second, first) if order is DateOrder.DAY_FIRST else (first, second)
        return date(year, month, day)
    except ValueError:
        return None


def inspect_timestamp(
    raw_text: str, requested_day: date, policy: EndpointTimestampPolicy, *,
    intraday: bool,
) -> TimestampAssessment:
    """Fail closed on documented/observed date-format conflict.

    Nonempty data and a date matching a query are NOT provider authenticity.
    Intraday date/time stays unusable until endpoint clock label (start/end/
    last-event) is independently reviewed as well as the date convention.
    """
    _day(requested_day)
    if not isinstance(policy, EndpointTimestampPolicy):
        raise TypeError("Expected EndpointTimestampPolicy")
    if type(intraday) is not bool:
        raise TypeError("intraday must be bool")
    if not isinstance(raw_text, str):
        raise TypeError("Raw provider date must be text")
    match = (_STAMP if intraday else _DAY).fullmatch(raw_text)
    if match is None:
        return TimestampAssessment(
            policy.endpoint_id, raw_text, requested_day, (), None,
            "INVALID_DATE_SHAPE",
        )
    first, second, year = map(int, match.groups()[:3])
    candidates = tuple(dict.fromkeys(
        d for d in (
            _candidate_day(first, second, year, DateOrder.DAY_FIRST),
            _candidate_day(first, second, year, DateOrder.MONTH_FIRST),
        ) if d is not None
    ))
    if not candidates:
        reason = "INVALID_CALENDAR_DATE"
    elif not policy.date_policy_consistent:
        reason = "DATE_ORDER_CONFLICT_OR_UNKNOWN"
    elif not policy.independently_confirmed:
        reason = "DATE_ORDER_NOT_INDEPENDENTLY_CONFIRMED"
    else:
        agreed = _candidate_day(first, second, year, policy.documented_date_order)
        if agreed != requested_day:
            reason = "DATE_DOES_NOT_MATCH_QUERY"
        elif intraday and not policy.timestamp_label_confirmed:
            reason = "INTRADAY_CLOCK_LABEL_NOT_CONFIRMED"
        else:
            reason = "DATE_AND_CLOCK_SEMANTICS_VERIFIED"

    instant = None
    if reason == "DATE_AND_CLOCK_SEMANTICS_VERIFIED":
        agreed = _candidate_day(first, second, year, policy.documented_date_order)
        if intraday:
            hour, minute, second_value = map(int, match.groups()[3:6])
            try:
                local = datetime.combine(
                    agreed, time(hour, minute, second_value), tzinfo=_VN
                )
                instant = local.astimezone(timezone.utc)
            except ValueError:
                reason = "INVALID_SESSION_CLOCK"
        else:
            # A D1 trading date is NOT an instant. Never invent a bar cutoff
            # or attach midnight to daily bars.
            reason = "DAILY_DATE_ONLY_NO_MARKET_CUTOFF"
    return TimestampAssessment(
        policy.endpoint_id, raw_text, requested_day, candidates, instant, reason
    )


@dataclass(frozen=True)
class SourceCoverageObservation:
    endpoint_id: str
    instrument_id: str
    trading_day: date
    record_count: int
    retrieved_at_utc: datetime
    pagination_complete: bool
    request_succeeded: bool

    def __post_init__(self):
        _text(self.endpoint_id, "endpoint_id")
        _text(self.instrument_id, "instrument_id")
        _day(self.trading_day)
        require_utc(self.retrieved_at_utc)
        if type(self.record_count) is not int or self.record_count < 0:
            raise ValueError("record_count must be nonnegative integer")
        if type(self.pagination_complete) is not bool or type(
            self.request_succeeded
        ) is not bool:
            raise TypeError("Source request and pagination need explicit bool")

    @property
    def availability(self) -> RecordAvailability:
        if not self.request_succeeded:
            return RecordAvailability.ERROR_BLOCKED
        if self.record_count == 0:
            return RecordAvailability.EMPTY_UNKNOWN
        return RecordAvailability.OBSERVED_UNVERIFIED

    @property
    def usable_history_coverage(self) -> bool:
        """Never infer complete history from one page/day, even with rows."""
        return False


@dataclass(frozen=True)
class DailyFirstRecordParity:
    """Structural D1-versus-first-observation check, not session open truth."""
    instrument_id: str
    trading_day: date
    daily_open: Decimal | None
    first_intraday_open: Decimal | None
    first_record_time_label: str | None

    def __post_init__(self):
        _text(self.instrument_id, "instrument_id")
        _day(self.trading_day)
        for value in (self.daily_open, self.first_intraday_open):
            if value is not None:
                _decimal(value)
        if self.first_record_time_label is not None:
            _text(self.first_record_time_label, "first_record_time_label")

    @property
    def parity_state(self) -> ParityState:
        if self.daily_open is None or self.first_intraday_open is None:
            return ParityState.MISSING_UNKNOWN
        return (ParityState.MATCH_UNVERIFIED
                if self.daily_open == self.first_intraday_open
                else ParityState.MISMATCH_BLOCKED)

    @property
    def delta(self) -> Decimal | None:
        if self.parity_state is ParityState.MISSING_UNKNOWN:
            return None
        return self.daily_open - self.first_intraday_open


def cross_timeframe_price_basis(
    daily_basis: PriceBasis, minute_basis: PriceBasis, *,
    independently_verified_adjustment_mapping: bool
) -> SourceGate:
    """Different basis blocks joins until approved adjustment lineage exists.

    Even when basis values align, this is only OBSERVED_UNVERIFIED.
    """
    if not isinstance(daily_basis, PriceBasis) or not isinstance(minute_basis, PriceBasis):
        raise TypeError("Price bases must be explicit")
    if type(independently_verified_adjustment_mapping) is not bool:
        raise TypeError("Mapping approval must be an explicit bool")
    if daily_basis is PriceBasis.UNKNOWN or minute_basis is PriceBasis.UNKNOWN:
        return SourceGate.BLOCKED
    if daily_basis != minute_basis and not independently_verified_adjustment_mapping:
        return SourceGate.BLOCKED
    return SourceGate.OBSERVED_UNVERIFIED

class MinuteSlotState(str, Enum):
    COMPLETE_OBSERVED_UNVERIFIED = "COMPLETE_OBSERVED_UNVERIFIED"
    MISSING_UNCLASSIFIED = "MISSING_UNCLASSIFIED"


@dataclass(frozen=True)
class SessionMinuteSlots:
    """Missing records are never classified as no-trade without separate proof."""
    instrument_id: str
    trading_day: date
    scheduled_slots: int
    observed_slots: int
    calendar_verified: bool

    def __post_init__(self):
        _text(self.instrument_id, "instrument_id")
        _day(self.trading_day)
        for name in ("scheduled_slots", "observed_slots"):
            n = getattr(self, name)
            if type(n) is not int or n < 0:
                raise ValueError(name + " must be a nonnegative integer")
        if self.scheduled_slots == 0 or self.observed_slots > self.scheduled_slots:
            raise ValueError("Invalid number of scheduled/observed slots")
        if type(self.calendar_verified) is not bool:
            raise TypeError("Calendar verification must be explicit")

    @property
    def missing_slots(self) -> int:
        return self.scheduled_slots - self.observed_slots

    @property
    def state(self) -> MinuteSlotState:
        return (MinuteSlotState.COMPLETE_OBSERVED_UNVERIFIED
                if self.missing_slots == 0 else MinuteSlotState.MISSING_UNCLASSIFIED)


@dataclass(frozen=True)
class DailyVsMinuteVolumeParity:
    """An unexplained +95 mismatch blocks parity even when otherwise tiny."""
    instrument_id: str
    trading_day: date
    daily_volume: int | None
    minute_sum_volume: int | None
    minute_pagination_complete: bool
    aggregation_policy_verified: bool

    def __post_init__(self):
        _text(self.instrument_id, "instrument_id")
        _day(self.trading_day)
        for name in ("daily_volume", "minute_sum_volume"):
            n = getattr(self, name)
            if n is not None and (type(n) is not int or n < 0):
                raise ValueError(name + " must be integer/nonnegative or unknown")
        for name in ("minute_pagination_complete", "aggregation_policy_verified"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(name + " must be explicit bool")

    @property
    def parity_state(self) -> ParityState:
        if (self.daily_volume is None or self.minute_sum_volume is None
                or not self.minute_pagination_complete):
            return ParityState.MISSING_UNKNOWN
        return (ParityState.MATCH_UNVERIFIED
                if self.daily_volume == self.minute_sum_volume
                else ParityState.MISMATCH_BLOCKED)

    @property
    def delta(self) -> int | None:
        if self.parity_state is ParityState.MISSING_UNKNOWN:
            return None
        return self.daily_volume - self.minute_sum_volume
