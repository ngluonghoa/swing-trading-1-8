"""Versioned replay event identity; no lookahead by discovery or correction."""
from dataclasses import dataclass
from datetime import datetime

from .replay import require_utc


@dataclass(frozen=True)
class CausalMarketEvent:
    event_id: str
    revision_id: str
    event_time_utc: datetime
    first_known_time_utc: datetime
    payload: object

    def __post_init__(self) -> None:
        require_utc(self.event_time_utc)
        require_utc(self.first_known_time_utc)
        if not self.event_id or not self.revision_id:
            raise ValueError("Event and revision IDs are mandatory")
        if self.first_known_time_utc < self.event_time_utc:
            raise ValueError("Market event cannot be known before its event-time")
