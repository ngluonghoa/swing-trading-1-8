"""Backtest foundation ONLY. No historical validation or fill simulator implemented."""
from dataclasses import dataclass
from datetime import datetime

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
    """Typed dependency boundary only. Must not imply validated trading performance."""

    clock: ReplayClock
    market_data: MarketDataPort
    rules: ZoneRuleRegistry

    def visible_events(self) -> tuple[object, ...]:
        return tuple(self.market_data.available_events(self.clock.as_of_utc))
