"""GĐ4/P0.24 — SSI intraday timestamp-surface DIAGNOSTICS, never bar qualification.

Transiently inspect a supplied read-only SSI MCP response, emit only counts
and clock-label geometry. A difference between labels is NOT proof of a lost
minute bar: holidays, market phases, lunch, no trades and provider semantics
remain unverified. Never parse conditional labels into market instants.
No network, file writes, raw price output, or executable signals.
"""
from dataclasses import dataclass
from datetime import date, datetime, time
from enum import Enum
import re

from .source_capability_evidence import (
    ProbeEndpoint, ProbeState, summarize_source_capability,
)
from .ssi_source_qualification import DateOrder

_STAMP = re.compile(
    r"^(\d{2})/(\d{2})/(\d{4}) (\d{2}):(\d{2}):(\d{2})$"
)
_MAX_ROWS = 10000


class LabelOrderEvidence(str, Enum):
    EMPTY_OR_UNAVAILABLE = "EMPTY_OR_UNAVAILABLE"
    DAY_FIRST_POSSIBLE_ONLY = "DAY_FIRST_POSSIBLE_ONLY"
    MONTH_FIRST_POSSIBLE_ONLY = "MONTH_FIRST_POSSIBLE_ONLY"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True)
class IntradayLabelDiagnostics:
    endpoint: ProbeEndpoint
    symbol: str
    requested_day: date
    checked_at_utc: datetime
    state: ProbeState
    observed_rows: int
    unique_text_labels: int
    date_order_evidence: LabelOrderEvidence
    observed_order: str
    unique_minute_labels: int | None
    duplicate_minute_labels: int | None
    gaps_over_one_minute: int | None
    longest_label_gap_minutes: int | None
    unobserved_minutes_between_labels: int | None
    earliest_minute_of_day: int | None
    latest_minute_of_day: int | None

    @property
    def timestamp_semantics_verified(self):
        return False

    @property
    def observed_gap_is_missing_candle(self):
        return False

    @property
    def publisher_first_known_verified(self):
        return False

    @property
    def source_retention_rights_verified(self):
        return False

    @property
    def eligible_for_m1_m5_m15(self):
        return False

    @property
    def historical_backtest_qualified(self):
        return False

    @property
    def actionable(self):
        return False


def _date_candidate(a: int, b: int, year: int, day_first: bool):
    try:
        return date(year, b if day_first else a, a if day_first else b)
    except ValueError:
        return None


def _order(values):
    if not values:
        return "NONE"
    descending = all(a >= b for a, b in zip(values, values[1:]))
    ascending = all(a <= b for a, b in zip(values, values[1:]))
    return "DESCENDING" if descending else "ASCENDING" if ascending else "MIXED"


def inspect_ssi_intraday_surface(
    endpoint: ProbeEndpoint, response: dict, *,
    symbol: str, requested_day: date, checked_at_utc: datetime,
) -> IntradayLabelDiagnostics:
    """Only conditionally parse local clock labels; NEVER create UTC bars.

    If both DD/MM and MM/DD are valid for a requested day, even a seemingly
    matching date is ambiguous. If source descriptions conflict with observed
    labels, conditional geometry cannot certify a provider timestamp policy.
    """
    if endpoint not in (
        ProbeEndpoint.SSI_INTRADAY, ProbeEndpoint.SSI_FULL_INTRADAY
    ) or not isinstance(endpoint, ProbeEndpoint):
        raise TypeError("Explicit typed SSI intraday endpoint required")
    if type(requested_day) is not date:
        raise TypeError("Explicit trading date required, not datetime")
    summary = summarize_source_capability(
        endpoint, response, symbol=symbol, checked_at_utc=checked_at_utc
    )
    if summary.state is not ProbeState.RETURNED_ROWS:
        return IntradayLabelDiagnostics(
            endpoint, symbol, requested_day, checked_at_utc,
            summary.state, 0, 0, LabelOrderEvidence.EMPTY_OR_UNAVAILABLE,
            "NONE", None, None, None, None, None, None, None,
        )

    ticks = response["data"]["ticks"]
    if len(ticks) > _MAX_ROWS:
        raise ValueError("Only up to 10,000 ephemeral time labels allowed")
    text_labels = []
    time_minutes = []
    valid_order = []
    for tick in ticks:
        raw = tick["trading_date"]  # Existing source audit checked type/symbol.
        match = _STAMP.fullmatch(raw)
        if match is None:
            raise ValueError("Unexpected intraday date/clock text")
        a, b, year, hour, minute, second = map(int, match.groups())
        try:
            time(hour, minute, second)
        except ValueError as exc:
            raise ValueError("Invalid intraday clock components") from exc
        day_first = _date_candidate(a, b, year, True)
        month_first = _date_candidate(a, b, year, False)
        choices = (
            day_first == requested_day,
            month_first == requested_day,
        )
        if not any(choices):
            raise ValueError("Intraday date does not match requested session")
        valid_order.append(choices)
        text_labels.append(raw)
        time_minutes.append(hour * 60 + minute)

    unique_labels = len(set(text_labels))
    possible_day = all(x[0] for x in valid_order)
    possible_month = all(x[1] for x in valid_order)
    if not possible_day and not possible_month:
        raise ValueError("Mixed or conflicting date-order labels in a session")

    if possible_day and possible_month:
        evidence = LabelOrderEvidence.AMBIGUOUS
    elif possible_day:
        evidence = LabelOrderEvidence.DAY_FIRST_POSSIBLE_ONLY
    else:
        evidence = LabelOrderEvidence.MONTH_FIRST_POSSIBLE_ONLY

    # A date-order ambiguity makes all computed geometry undecidable. Even
    # the unique case is CONDITIONAL and NEVER proves bar label semantics.
    if evidence is LabelOrderEvidence.AMBIGUOUS:
        return IntradayLabelDiagnostics(
            endpoint, symbol, requested_day, checked_at_utc, summary.state,
            len(ticks), unique_labels, evidence, "UNDECIDABLE",
            None, None, None, None, None, None, None,
        )

    unique_minutes = sorted(set(time_minutes))
    deltas = [b-a for a, b in zip(unique_minutes, unique_minutes[1:])]
    gaps = [d for d in deltas if d > 1]
    return IntradayLabelDiagnostics(
        endpoint, symbol, requested_day, checked_at_utc, summary.state,
        len(ticks), unique_labels, evidence, _order(time_minutes),
        len(unique_minutes), len(ticks) - len(unique_minutes),
        len(gaps), max(gaps, default=0),
        sum(d-1 for d in gaps),
        unique_minutes[0], unique_minutes[-1],
    )
