"""H2-C: fail-closed semantic cache-backend substitution preview.

REAL cache migration is NOT implemented. This module compares fabricated
closed candle/revision records in the two existing in-memory test doubles:
C3B immutable partitions and C4A weekly segments. No provider, cloud or
broker calls; no external custody, retention or release authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
import re

from .engineering_contracts import PortDescriptor, require_compatible_port
from .incremental_cache import CacheIdentity, FixtureBar, full_recompute
from .partition_chunk_cache import SyntheticDrivePartitionIndex
from .segmented_cache import SyntheticWeeklyChunkStore

_READ_PORT = PortDescriptor(
    "cache.readonly_fixture", "1.0.0", "SYNTHETIC_TEST_ONLY",
    ("get_head", "read_partition"),
)
_SHA = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED = (SyntheticDrivePartitionIndex, SyntheticWeeklyChunkStore)


def _checked_digest(value: str) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise ValueError("Explicit pinned lowercase SHA256 required")
    return value


def _bar_digest(bars: tuple[FixtureBar, ...]) -> str:
    """Include revision and first-known clock (not just numeric OHLCV)."""
    payload = [
        {
            "raw_digest": b.normalized_digest,
            "revision": b.revision,
            "known": b.first_known_utc.isoformat(timespec="microseconds"),
            "start": b.start_utc.isoformat(timespec="microseconds"),
            "end": b.end_utc.isoformat(timespec="microseconds"),
        }
        for b in bars
    ]
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256(raw.encode("ascii")).hexdigest()


@dataclass(frozen=True)
class FixtureCacheSwitchReview:
    partition_sha256: str
    old_head_sha256: str
    candidate_head_sha256: str
    old_rows: int
    candidate_rows: int
    old_content_sha256: str
    candidate_content_sha256: str
    fixture_equivalent: bool
    reasons: tuple[str, ...]
    non_market_fixture_only: bool = True
    licensed_data_authorized: bool = False
    real_migration_approved: bool = False
    trading_authorized: bool = False

    def __post_init__(self) -> None:
        for field in (
            "partition_sha256", "old_head_sha256", "candidate_head_sha256",
            "old_content_sha256", "candidate_content_sha256",
        ):
            _checked_digest(getattr(self, field))
        if (self.non_market_fixture_only is not True
                or self.licensed_data_authorized is not False
                or self.real_migration_approved is not False
                or self.trading_authorized is not False):
            raise PermissionError("A synthetic cache comparison never authorizes operations")
        if type(self.fixture_equivalent) is not bool:
            raise TypeError("Explicit fixture comparison result required")
        if type(self.old_rows) is not int or type(self.candidate_rows) is not int:
            raise TypeError("Explicit nonnegative integer row counts")
        if self.old_rows < 1 or self.candidate_rows < 1:
            raise ValueError("Nonempty fixture snapshots required")
        if not isinstance(self.reasons, tuple) or self.fixture_equivalent == bool(self.reasons):
            raise ValueError("Equivalent iff no reasons")


def compare_synthetic_cache_backends(
    identity: CacheIdentity, *,
    old_backend: SyntheticDrivePartitionIndex | SyntheticWeeklyChunkStore,
    candidate_backend: SyntheticDrivePartitionIndex | SyntheticWeeklyChunkStore,
    pinned_old_sha256: str, pinned_candidate_sha256: str,
) -> FixtureCacheSwitchReview:
    """Read/verify both pinned heads; compare bytes' semantic bar/revision outputs.

    The caller supplies digests. They are not externally signed or witnessed:
    even a successful preview is NOT production rollback/upgrade permission.
    Do not mutate either backend. Only the two audited old test-double types
    are allowed, so no arbitrary callback can be executed by inspection.
    """
    if not isinstance(identity, CacheIdentity):
        raise TypeError("Typed synthetic cache identity required")
    if type(old_backend) not in _ALLOWED or type(candidate_backend) not in _ALLOWED:
        raise TypeError("Only the two existing synthetic in-memory backends")
    if old_backend is candidate_backend:
        raise ValueError("A replacement preview needs distinct backends")
    old_pin = _checked_digest(pinned_old_sha256)
    candidate_pin = _checked_digest(pinned_candidate_sha256)
    for backend in (old_backend, candidate_backend):
        require_compatible_port(_READ_PORT, backend.read_port_descriptor, backend)
    if old_backend.get_head(identity) != old_pin:
        raise ValueError("STALE_OR_MISSING_OLD_HEAD")
    if candidate_backend.get_head(identity) != candidate_pin:
        raise ValueError("STALE_OR_MISSING_CANDIDATE_HEAD")
    old = old_backend.read_partition(identity, pinned_digest=old_pin)
    candidate = candidate_backend.read_partition(identity, pinned_digest=candidate_pin)
    if (not isinstance(old, tuple) or not isinstance(candidate, tuple)
            or not old or not candidate
            or any(not isinstance(b, FixtureBar) or not b.closed for b in old + candidate)):
        raise ValueError("Only nonempty typed closed fixture histories can be compared")
    old_checkpoints = full_recompute(old)
    candidate_checkpoints = full_recompute(candidate)
    reasons = []
    if old != candidate:
        reasons.append("BAR_OR_REVISION_OR_FIRST_KNOWN_MISMATCH")
    if old_checkpoints != candidate_checkpoints:
        reasons.append("GLOBAL_EMA_ATR_CHECKPOINT_MISMATCH")
    return FixtureCacheSwitchReview(
        partition_sha256=identity.fingerprint,
        old_head_sha256=old_pin, candidate_head_sha256=candidate_pin,
        old_rows=len(old), candidate_rows=len(candidate),
        old_content_sha256=_bar_digest(old), candidate_content_sha256=_bar_digest(candidate),
        fixture_equivalent=not reasons, reasons=tuple(reasons),
    )
