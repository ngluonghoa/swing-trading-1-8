"""Synthetic-only causal replay harness. No trading P&L claim or fill model."""
from dataclasses import dataclass
from datetime import datetime

from .causal import CausalMarketEvent
from .contracts import ZoneRuleRegistry, MarketDataPort
from .replay import ReplayClock, require_utc


@dataclass(frozen=True)
class ExperimentManifest:
    experiment_id: str
    as_of_utc: datetime
    source_snapshot_id: str
    rule_version: str

    def __post_init__(self) -> None:
        require_utc(self.as_of_utc)
        if not all((self.experiment_id, self.source_snapshot_id, self.rule_version)):
            raise ValueError("Manifest fields cannot be empty")


@dataclass
class BacktestHarness:
    """Shared dependency boundaries; executable detector and simulator NOT_IMPLEMENTED.

    Filtering here is defence in depth: a port must itself provide correct
    source-revision snapshots and provenance. Results are ENGINE_FIXTURE_ONLY.
    """
    clock: ReplayClock
    market_data: MarketDataPort
    rules: ZoneRuleRegistry

    def visible_events(self) -> tuple[CausalMarketEvent, ...]:
        events = self.market_data.available_events(self.clock.as_of_utc)
        if any(not isinstance(e, CausalMarketEvent) for e in events):
            raise TypeError("Replay source must return typed causal events")
        visible = [
            e for e in events
            if self.clock.known(e.first_known_time_utc)
            and self.clock.known(e.event_time_utc)
        ]
        return tuple(sorted(visible, key=lambda e: (
            e.first_known_time_utc, e.event_time_utc, e.event_id, e.revision_id
        )))
