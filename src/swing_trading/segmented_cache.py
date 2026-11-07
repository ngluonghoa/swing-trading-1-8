"""C4A: synthetic-only weekly time-window chunks over existing SSI/DNSE/VCBS partitions.

This is a local in-memory model; no real Drive requests, licensed prices, real
provider change tokens, distributed compare-and-swap or cloud key custody.
Window boundaries use UTC calendar Mondays as *storage buckets only*, not a
claim about HOSE/HNX/UPCOM trading sessions or corporate-action semantics.

The original C3B fixture chunk recomputes EMA/ATR within each encoded window;
that local seed is NOT a globally valid indicator checkpoint. On full restore,
the underlying SQLite store rebuilds/validates the GLOBAL indicator series.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re

from .incremental_cache import CacheIdentity, FixtureBar, SyntheticIncrementalStore, full_recompute
from .partition_chunk_cache import encode_fixture_chunk, decode_fixture_chunk

_SHA = re.compile(r"^[0-9a-f]{64}$")
_WINDOW = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_LIMIT_WINDOWS = 256


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("Aware UTC timestamp required")
    return value.astimezone(timezone.utc)


def _canon(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False)


def _sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _weekly_id(bar: FixtureBar) -> str:
    start = _utc(bar.start_utc).date()
    monday = start - timedelta(days=start.weekday())
    return monday.isoformat()


@dataclass(frozen=True)
class FixtureWindowRef:
    monday_utc: str
    name: str
    sha256: str
    byte_count: int
    rows: int

    def __post_init__(self) -> None:
        if not isinstance(self.monday_utc, str) or not _WINDOW.fullmatch(self.monday_utc):
            raise ValueError("Invalid weekly window ID")
        monday = datetime.fromisoformat(self.monday_utc).date()
        if monday.weekday() != 0:
            raise ValueError("Window must start on UTC Monday")
        if not isinstance(self.sha256, str) or not _SHA.fullmatch(self.sha256):
            raise ValueError("Invalid chunk digest")
        if self.name != f"st18-w-{self.monday_utc}-{self.sha256}.fixture.json":
            raise ValueError("Content-addressed window filename mismatch")
        if type(self.byte_count) is not int or not 0 < self.byte_count <= 4*1024*1024:
            raise ValueError("Invalid chunk length")
        if type(self.rows) is not int or not 0 < self.rows <= 5000:
            raise ValueError("Invalid fixture window row count")


@dataclass(frozen=True)
class FixtureWindowIndex:
    partition_sha256: str
    generation: int
    parent_sha256: str | None
    created_at_utc: datetime
    windows: tuple[FixtureWindowRef, ...]
    fixture_only: bool = True
    actual_drive_upload: bool = False
    real_data_approved: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.partition_sha256, str) or not _SHA.fullmatch(self.partition_sha256):
            raise ValueError("Invalid partition hash")
        if type(self.generation) is not int or self.generation < 1:
            raise ValueError("Invalid generation")
        if (self.generation == 1) != (self.parent_sha256 is None):
            raise ValueError("Only genesis index has no previous parent")
        if self.parent_sha256 is not None and not _SHA.fullmatch(self.parent_sha256):
            raise ValueError("Invalid parent digest")
        _utc(self.created_at_utc)
        if (not isinstance(self.windows, tuple) or not 0 < len(self.windows) <= _LIMIT_WINDOWS
                or any(not isinstance(x, FixtureWindowRef) for x in self.windows)):
            raise ValueError("Bounded typed windows required")
        keys = tuple(x.monday_utc for x in self.windows)
        if tuple(sorted(set(keys))) != keys:
            raise ValueError("Strictly ordered unique windows required")
        if self.fixture_only is not True or self.actual_drive_upload is not False or self.real_data_approved is not False:
            raise PermissionError("Synthetic fixture only; no production/Drive authorization")

    @property
    def canonical_json(self) -> str:
        payload = asdict(self)
        payload["created_at_utc"] = _utc(self.created_at_utc).isoformat(timespec="microseconds")
        return _canon(payload)

    @property
    def digest(self) -> str:
        return _sha(self.canonical_json.encode("ascii"))


@dataclass(frozen=True)
class WindowSync:
    created_windows: int
    reused_windows: int
    manifest_changed: bool
    actual_drive_calls: int = 0
    market_data_calls: int = 0
    live_cache_approved: bool = False


class SyntheticWeeklyChunkStore:
    """In-process immutable window objects and manifest-chain *test-double*."""

    def __init__(self) -> None:
        self._chunks: dict[str, bytes] = {}
        self._indexes: dict[str, FixtureWindowIndex] = {}
        self._history: dict[str, list[str]] = {}
        self._heads: dict[str, str] = {}

    @property
    def object_count(self) -> int:
        return len(self._chunks)

    def head(self, identity: CacheIdentity) -> str | None:
        if not isinstance(identity, CacheIdentity):
            raise TypeError("Typed identity required")
        return self._heads.get(identity.fingerprint)

    def _lineage(self, identity: CacheIdentity) -> tuple[FixtureWindowIndex, ...]:
        history = self._history.get(identity.fingerprint, [])
        if not history:
            if identity.fingerprint in self._heads:
                raise ValueError("Pointer without a verified manifest lineage")
            return ()
        if self._heads.get(identity.fingerprint) != history[-1]:
            raise ValueError("Forged or stale local active pointer")
        previous = None
        valid = []
        for generation, digest in enumerate(history, 1):
            m = self._indexes.get(digest)
            if m is None or m.digest != digest or m.partition_sha256 != identity.fingerprint:
                raise ValueError("Missing or corrupt index manifest")
            if m.generation != generation or m.parent_sha256 != previous:
                raise ValueError("Broken generation ancestry")
            valid.append(m)
            previous = digest
        return tuple(valid)

    def commit(self, identity: CacheIdentity, bars: tuple[FixtureBar, ...], *,
               expected_head: str | None, observed_at_utc: datetime,
               fail_after_staging: bool = False) -> WindowSync:
        now = _utc(observed_at_utc)
        if not isinstance(bars, tuple) or not bars:
            raise ValueError("Full nonempty synthetic partition snapshot required")
        if type(fail_after_staging) is not bool:
            raise TypeError("Typed fault injection required")
        lineage = self._lineage(identity)
        if expected_head != self.head(identity):
            raise ValueError("Stale synthetic writer")
        if expected_head is not None and not _SHA.fullmatch(expected_head):
            raise ValueError("Expected head digest")
        previous = lineage[-1] if lineage else None
        grouped: dict[str, list[FixtureBar]] = {}
        last = None
        for b in bars:
            if not isinstance(b, FixtureBar) or not b.closed or b.end_utc > now or b.first_known_utc > now:
                raise ValueError("Closed, as-known fake bars required")
            if last is not None and b.start_utc <= last:
                raise ValueError("Strictly increasing distinct fake bars required")
            last = b.start_utc
            grouped.setdefault(_weekly_id(b), []).append(b)
        if len(grouped) > _LIMIT_WINDOWS:
            raise ValueError("Too many chunk windows")
        prev_refs = {w.monday_utc: w for w in previous.windows} if previous else {}
        if any(w not in grouped for w in prev_refs):
            raise ValueError("Whole window deletion requires separately qualified authoritative scope")
        refs = []
        created = reused = 0
        for window, items in sorted(grouped.items()):
            raw = encode_fixture_chunk(identity, tuple(items))
            digest = _sha(raw)
            ref = FixtureWindowRef(window, f"st18-w-{window}-{digest}.fixture.json",
                                   digest, len(raw), len(items))
            prior = prev_refs.get(window)
            if prior is not None and prior == ref:
                self._verify_window(identity, prior)
                reused += 1
            else:
                if ref.name in self._chunks and self._chunks[ref.name] != raw:
                    raise ValueError("Content-addressed window name collision")
                self._chunks.setdefault(ref.name, raw)
                created += 1
            refs.append(ref)
        if not created:
            return WindowSync(0, reused, False)
        if fail_after_staging:
            raise RuntimeError("Synthetic crash between staging immutable chunks and manifest")
        for ref in refs:
            self._verify_window(identity, ref)
        index = FixtureWindowIndex(identity.fingerprint,
                                   len(lineage)+1, previous.digest if previous else None,
                                   now, tuple(refs))
        self._indexes[index.digest] = index
        self._history.setdefault(identity.fingerprint, []).append(index.digest)
        self._heads[identity.fingerprint] = index.digest
        return WindowSync(created, reused, True)

    def _verify_window(self, identity: CacheIdentity, ref: FixtureWindowRef) -> tuple[FixtureBar, ...]:
        raw = self._chunks.get(ref.name)
        if raw is None or len(raw) != ref.byte_count or _sha(raw) != ref.sha256:
            raise ValueError("Missing, truncated or corrupted immutable weekly chunk")
        rows = decode_fixture_chunk(raw, expected_identity=identity)
        if len(rows) != ref.rows or any(_weekly_id(b) != ref.monday_utc for b in rows):
            raise ValueError("Window membership / metadata mismatch")
        return rows

    def load(self, identity: CacheIdentity, *, pinned_head: str,
             windows: tuple[str, ...] | None = None,
             minimum_generation: int = 1) -> tuple[FixtureBar, ...]:
        if not isinstance(pinned_head, str) or not _SHA.fullmatch(pinned_head):
            raise ValueError("Pinned SHA256 required")
        if type(minimum_generation) is not int or minimum_generation < 1:
            raise ValueError("Positive generation floor required")
        history = self._lineage(identity)
        if not history or pinned_head != history[-1].digest or history[-1].generation < minimum_generation:
            raise ValueError("Stale or rolled-back fixture index")
        manifest = history[-1]
        available = {w.monday_utc: w for w in manifest.windows}
        if windows is not None:
            if (not isinstance(windows, tuple) or not windows
                    or len(windows) != len(set(windows))
                    or any(w not in available for w in windows)):
                raise ValueError("Explicit selected windows must exist exactly once")
            selected = sorted(windows)
        else:
            selected = sorted(available)
        bars = tuple(b for w in selected for b in self._verify_window(identity, available[w]))
        if any(a.start_utc >= b.start_utc for a,b in zip(bars,bars[1:])):
            raise ValueError("Reassembled fixture partition is not ordered")
        if any(b.first_known_utc > manifest.created_at_utc or b.end_utc > manifest.created_at_utc for b in bars):
            raise ValueError("Window index predates source information")
        return bars

    def restore_full(self, store: SyntheticIncrementalStore, identity: CacheIdentity, *,
                     pinned_head: str) -> int:
        if not isinstance(store, SyntheticIncrementalStore):
            raise TypeError("Typed local fixture SQLite store only")
        if store.read_bars(identity):
            raise ValueError("Refuse to overwrite existing local partition")
        bars = self.load(identity, pinned_head=pinned_head)
        now = self._lineage(identity)[-1].created_at_utc
        result = store.apply_fixture_window(identity, bars,
                     observed_at_utc=now, scope_start_utc=bars[0].start_utc,
                     scope_end_utc=max(b.end_utc for b in bars),
                     complete_scope=False)
        if result.inserted != len(bars) or store.read_checkpoints(identity) != full_recompute(bars):
            raise ValueError("Global EMA/ATR parity / SQLite restore failed")
        return result.inserted

    def corrupt_latest_window_for_test(self, identity: CacheIdentity) -> None:
        latest = self._lineage(identity)[-1]
        self._chunks[latest.windows[-1].name] += b"TAMPER"


def require_authorized_window_cache(*_args: object, **_kwargs: object) -> None:
    raise PermissionError("Live storage, cloud uploads, and vendor entitlements NOT authorized")
