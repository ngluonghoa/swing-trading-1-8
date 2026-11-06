"""P0.6 deterministic M5/M15-aware replay of v1.2 source observations.

This is a read-only engineering bridge. It deduplicates EXACT retransmissions
before using existing fail-closed as-of resolution. It never approves source
rights, resolves different revisions/providers, makes a detector decision,
aggregates intraday bars or authorizes a trade.
"""
from dataclasses import dataclass
from datetime import datetime

from .market_data import MarketBarKey
from .replay import ReplayClock, require_utc
from .source_quality import CanonicalCandleV12, ResolvedBarSnapshotV12, resolve_as_known


def _sort_key(key: MarketBarKey) -> tuple:
    return (
        key.exchange, key.instrument_id, key.instrument_class.value,
        key.timeframe.value, key.bar_start_utc, key.session_period_id,
        key.price_basis.value, key.calendar_version,
        key.aggregation_policy_version,
    )


def _revision_identity(row: CanonicalCandleV12) -> tuple:
    """Source-qualified identity; NOT a claim of authentic provider bytes."""
    revision = row.observation_revision
    return (
        row.observation_key, revision.source_revision_or_payload_digest,
        revision.adjustment_revision, revision.ingestion_revision,
    )


@dataclass(frozen=True)
class ReplayBar:
    resolution: ResolvedBarSnapshotV12
    exact_retransmissions_removed: int
    revision_identity_collision: bool

    def __post_init__(self) -> None:
        if not isinstance(self.resolution, ResolvedBarSnapshotV12):
            raise TypeError("ReplayBar requires a versioned resolution")
        if (type(self.exact_retransmissions_removed) is not int
                or self.exact_retransmissions_removed < 0):
            raise ValueError("Invalid retransmission count")
        if type(self.revision_identity_collision) is not bool:
            raise TypeError("Identity collision must be an explicit bool")
        if self.revision_identity_collision and self.resolution.selected is not None:
            raise ValueError("Colliding source identity cannot have a selected revision")

    def source_prerequisites_at(self, as_of_utc: datetime) -> bool:
        """Necessary source checks only; not an actionable trading gate."""
        require_utc(as_of_utc)
        return (not self.revision_identity_collision
                and self.resolution.confirmation_prerequisites(as_of_utc))


@dataclass(frozen=True)
class ReplayFrame:
    as_of_utc: datetime
    bars: tuple[ReplayBar, ...]

    def __post_init__(self) -> None:
        require_utc(self.as_of_utc)
        if not isinstance(self.bars, tuple) or not all(
            isinstance(item, ReplayBar) for item in self.bars
        ):
            raise TypeError("ReplayFrame requires immutable ReplayBar tuple")

    def find(self, market_bar_key: MarketBarKey) -> ReplayBar:
        for bar in self.bars:
            if bar.resolution.market_bar_key == market_bar_key:
                return bar
        raise KeyError("Market bar was not requested")


def replay_frame(
    market_bar_keys: tuple[MarketBarKey, ...],
    source_rows: tuple[CanonicalCandleV12, ...],
    as_of_utc: datetime,
) -> ReplayFrame:
    """Resolve requested bars causally with exact duplicate collapse.

    Equal retransmitted rows have identical values, provenance, digests and
    timestamps. Equal source+revision identity with DIFFERENT payload must
    remain a visible conflict; no automatic latest-wins repair is permitted.
    Distinct source or revision identities are never silently preferred.
    """
    require_utc(as_of_utc)
    if not isinstance(market_bar_keys, tuple) or not isinstance(source_rows, tuple):
        raise TypeError("Replay inputs must be immutable tuples")
    if any(not isinstance(key, MarketBarKey) for key in market_bar_keys):
        raise TypeError("Expected MarketBarKey")
    if any(not isinstance(row, CanonicalCandleV12) for row in source_rows):
        raise TypeError("Expected CanonicalCandleV12")
    if len(set(market_bar_keys)) != len(market_bar_keys):
        raise ValueError("Duplicate requested market bar key")
    requested = set(market_bar_keys)
    if any(row.market_bar_key not in requested for row in source_rows):
        raise ValueError("An unrequested market bar was supplied")

    results = []
    for key in sorted(market_bar_keys, key=_sort_key):
        visible = (row for row in source_rows
                   if row.market_bar_key == key
                   and row.observation_revision.first_known_time_utc <= as_of_utc)
        deduplicated = []
        by_identity = {}
        retransmissions = 0
        identity_collision = False
        for row in visible:
            identity = _revision_identity(row)
            seen = by_identity.setdefault(identity, [])
            if any(previous == row for previous in seen):
                retransmissions += 1
                continue
            if seen:
                identity_collision = True
            seen.append(row)
            deduplicated.append(row)
        resolution = resolve_as_known(key, tuple(deduplicated), as_of_utc)
        results.append(ReplayBar(resolution, retransmissions, identity_collision))
    return ReplayFrame(as_of_utc, tuple(results))


def replay_sequence(
    market_bar_keys: tuple[MarketBarKey, ...],
    source_rows: tuple[CanonicalCandleV12, ...],
    checkpoints_utc: tuple[datetime, ...],
) -> tuple[ReplayFrame, ...]:
    """Recreate monotonically ordered, as-known frames without a wall clock."""
    if not isinstance(checkpoints_utc, tuple) or not checkpoints_utc:
        raise ValueError("Nonempty immutable replay checkpoints required")
    clock = ReplayClock(require_utc(checkpoints_utc[0]))
    frames = []
    for as_of in checkpoints_utc:
        clock.advance_to(require_utc(as_of))
        frames.append(replay_frame(market_bar_keys, source_rows, clock.as_of_utc))
    return tuple(frames)
