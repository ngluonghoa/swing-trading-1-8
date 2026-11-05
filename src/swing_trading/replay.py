"""Deterministic event-time replay clock; no wall-clock or future-data fallback."""
from dataclasses import dataclass
from datetime import datetime, timezone


def require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError("Expected timezone-aware UTC")
    return value


@dataclass
class ReplayClock:
    as_of_utc: datetime

    def __post_init__(self) -> None:
        require_utc(self.as_of_utc)

    def advance_to(self, next_time_utc: datetime) -> None:
        require_utc(next_time_utc)
        if next_time_utc < self.as_of_utc:
            raise ValueError("Replay clock cannot go backwards")
        self.as_of_utc = next_time_utc

    def known(self, first_known_time_utc: datetime) -> bool:
        return require_utc(first_known_time_utc) <= self.as_of_utc
