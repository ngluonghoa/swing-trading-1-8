"""GĐ4/C3B — partitioned, content-addressed SYNTHETIC fixture cache prototype.

Pure in-memory test-double for a future Google Drive chunk+manifest adapter.
No Google API, OAuth, real licensed SSI/DNSE/VCBS records, production cache,
time-series polling or trading authority. SQLite remains transient working store.
A self-consistent fixture marker cannot prove data provenance or entitlement.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from hashlib import sha256
import json
import re

from .engineering_contracts import PortDescriptor
from .incremental_cache import (
    CacheIdentity, FixtureBar, IndicatorCheckpoint, Provider,
    SyntheticIncrementalStore, full_recompute,
)

MAGIC = b"SWING18_FAKE_PARTITION_V1\n"
MAX_CHUNK_BYTES = 4 * 1024 * 1024
MAX_BARS = 5000
MAX_PARTITIONS_PER_SYNC = 100
_SHA = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_BAR_FIELDS = {
    "start_utc", "end_utc", "open", "high", "low", "close", "volume",
    "revision", "first_known_utc", "closed", "digest",
}
_CHECKPOINT_FIELDS = {
    "start_utc", "ema20", "atr14", "atr_seen", "atr_seed_sum", "last_close",
}
_MANIFEST_FIELDS = {
    "schema_version", "project_id", "environment", "storage_class",
    "partition_sha256", "chunk_name", "chunk_sha256", "chunk_bytes",
    "bar_count", "checkpoint_count", "generation",
    "previous_manifest_sha256", "created_at_utc",
    "drive_upload_performed", "live_market_data_authorized",
}


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("Strict timezone-aware UTC required")
    return value.astimezone(timezone.utc)


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _checked_sha(value: str) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise ValueError("Expected exact lowercase SHA256")
    return value


def _json(data: object) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False,
                      ensure_ascii=True).encode("ascii")


def _decode_json(raw: bytes, *, max_size: int) -> dict:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= max_size:
        raise ValueError("Canonical bounded bytes required")
    def no_duplicates(pairs):
        d = {}
        for k, v in pairs:
            if k in d:
                raise ValueError("Duplicate JSON key")
            d[k] = v
        return d
    obj = json.loads(raw, object_pairs_hook=no_duplicates,
                     parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite numeric value")))
    if type(obj) is not dict or _json(obj) != raw:
        raise ValueError("Canonical JSON object required")
    return obj


def _serialized_identity(identity: CacheIdentity) -> dict:
    if not isinstance(identity, CacheIdentity):
        raise TypeError("Typed synthetic CacheIdentity required")
    d = asdict(identity)
    d["provider"] = identity.provider.value
    return d


def _serialized_bar(bar: FixtureBar) -> dict:
    return {
        "start_utc": _utc(bar.start_utc).isoformat(timespec="microseconds"),
        "end_utc": _utc(bar.end_utc).isoformat(timespec="microseconds"),
        "open": str(bar.open), "high": str(bar.high), "low": str(bar.low),
        "close": str(bar.close), "volume": bar.volume,
        "revision": bar.revision,
        "first_known_utc": _utc(bar.first_known_utc).isoformat(timespec="microseconds"),
        "closed": bar.closed, "digest": bar.normalized_digest,
    }


def _serialized_checkpoint(item: IndicatorCheckpoint) -> dict:
    return {
        "start_utc": _utc(item.start_utc).isoformat(timespec="microseconds"),
        "ema20": str(item.ema20),
        "atr14": str(item.atr14) if item.atr14 is not None else None,
        "atr_seen": item.atr_seen,
        "atr_seed_sum": str(item.atr_seed_sum),
        "last_close": str(item.last_close),
    }


def encode_fixture_chunk(identity: CacheIdentity, bars: tuple[FixtureBar, ...]) -> bytes:
    """Deterministic partition artifact; identical observations yield identical bytes.

    No creation clock is included: repeated five-minute checks that find no
    changes reuse the content-addressed chunk without an extra upload.
    """
    if not isinstance(bars, tuple) or not 0 < len(bars) <= MAX_BARS:
        raise ValueError("Nonempty bounded fixture partition required")
    seen = set()
    previous = None
    for bar in bars:
        if not isinstance(bar, FixtureBar) or not bar.closed:
            raise ValueError("Only fully closed synthetic fixture bars")
        if previous is not None and _utc(bar.start_utc) <= previous:
            raise ValueError("Unique strictly ordered bar timestamps required")
        previous = _utc(bar.start_utc)
        if previous in seen:
            raise ValueError("Duplicate fixture bar")
        seen.add(previous)
    payload = {
        "format": "SWING18_FAKE_PARTITION_V1",
        "fixture_only": True,
        "market_data_authorized": False,
        "identity": _serialized_identity(identity),
        "partition_sha256": identity.fingerprint,
        "bars": [_serialized_bar(item) for item in bars],
        "checkpoints": [_serialized_checkpoint(item) for item in full_recompute(bars)],
    }
    artifact = MAGIC + _json(payload)
    if len(artifact) > MAX_CHUNK_BYTES:
        raise ValueError("Too many fixture rows/bytes for a Drive chunk")
    return artifact


def decode_fixture_chunk(raw: bytes, *, expected_identity: CacheIdentity) -> tuple[FixtureBar, ...]:
    """Strictly validate all contents, identity, source and indicator parity."""
    expected = _serialized_identity(expected_identity)
    if not isinstance(raw, bytes) or not raw.startswith(MAGIC) or len(raw) > MAX_CHUNK_BYTES:
        raise ValueError("Missing synthetic-only marker or oversize chunk")
    payload = _decode_json(raw[len(MAGIC):], max_size=MAX_CHUNK_BYTES)
    if set(payload) != {"format", "fixture_only", "market_data_authorized", "identity",
                        "partition_sha256", "bars", "checkpoints"}:
        raise ValueError("Unknown partition fields")
    if (payload["format"] != "SWING18_FAKE_PARTITION_V1"
            or payload["fixture_only"] is not True or payload["market_data_authorized"] is not False
            or payload["identity"] != expected or payload["partition_sha256"] != expected_identity.fingerprint):
        raise ValueError("Incompatible fixture namespace or asserted live-data rights")
    if (type(payload["identity"]) is not dict
            or set(payload["identity"]) != {f.name for f in fields(CacheIdentity)}):
        raise ValueError("Exact identity schema required")
    if type(payload["bars"]) is not list or not 0 < len(payload["bars"]) <= MAX_BARS:
        raise ValueError("Nonempty bounded fixture bars required")
    parsed = []
    for item in payload["bars"]:
        if type(item) is not dict or set(item) != _BAR_FIELDS:
            raise ValueError("Unexpected fixture bar fields")
        if item["closed"] is not True:
            raise ValueError("OPEN observations must not persist in a closed cache chunk")
        if type(item["volume"]) is not int:
            raise ValueError("Matched volume must be an integer")
        if not all(isinstance(item[k], str) for k in
                   ("open", "high", "low", "close", "revision", "start_utc",
                    "end_utc", "first_known_utc")):
            raise ValueError("Explicit fixture fields required")
        b = FixtureBar(
            datetime.fromisoformat(item["start_utc"]),
            datetime.fromisoformat(item["end_utc"]),
            Decimal(item["open"]), Decimal(item["high"]), Decimal(item["low"]),
            Decimal(item["close"]), item["volume"], item["revision"],
            datetime.fromisoformat(item["first_known_utc"]), item["closed"],
        )
        if _serialized_bar(b) != item:
            raise ValueError("Canonical fixture bar/digest mismatch")
        parsed.append(b)
    if any(parsed[i-1].start_utc >= parsed[i].start_utc for i in range(1, len(parsed))):
        raise ValueError("Partition bars must be time ordered")
    expected_checkpoints = [_serialized_checkpoint(x) for x in full_recompute(tuple(parsed))]
    if payload["checkpoints"] != expected_checkpoints:
        raise ValueError("Dependent EMA20/ATR14 checkpoints were corrupted or stale")
    if type(payload["checkpoints"]) is not list or any(
            type(x) is not dict or set(x) != _CHECKPOINT_FIELDS for x in payload["checkpoints"]):
        raise ValueError("Exact checkpoint schema required")
    return tuple(parsed)


@dataclass(frozen=True)
class FixturePartitionManifest:
    partition_sha256: str
    chunk_name: str
    chunk_sha256: str
    chunk_bytes: int
    bar_count: int
    checkpoint_count: int
    generation: int
    previous_manifest_sha256: str | None
    created_at_utc: datetime
    schema_version: int = 1
    project_id: str = "SwingTrading1.8"
    environment: str = "SYNTHETIC_TEST_ONLY"
    storage_class: str = "DRIVE_CHUNK_STAGING"
    drive_upload_performed: bool = False
    live_market_data_authorized: bool = False

    def __post_init__(self) -> None:
        _checked_sha(self.partition_sha256)
        _checked_sha(self.chunk_sha256)
        if self.chunk_name != f"st18-{self.partition_sha256}-{self.chunk_sha256}.fixture.json":
            raise ValueError("Content-addressed fixture chunk name required")
        if (type(self.chunk_bytes) is not int or self.chunk_bytes <= len(MAGIC)
                or self.chunk_bytes > MAX_CHUNK_BYTES):
            raise ValueError("Bounded chunk bytes required")
        if (type(self.bar_count) is not int or not 0 < self.bar_count <= MAX_BARS
                or type(self.checkpoint_count) is not int or self.checkpoint_count != self.bar_count):
            raise ValueError("Exact bar and checkpoint counts required")
        if type(self.generation) is not int or not 1 <= self.generation < 2**63:
            raise ValueError("Valid generation required")
        if (self.generation == 1) != (self.previous_manifest_sha256 is None):
            raise ValueError("Only genesis manifest has no predecessor")
        if self.previous_manifest_sha256 is not None:
            _checked_sha(self.previous_manifest_sha256)
        _utc(self.created_at_utc)
        if (type(self.schema_version) is not int or self.schema_version != 1
                or self.project_id != "SwingTrading1.8" or self.environment != "SYNTHETIC_TEST_ONLY"
                or self.storage_class != "DRIVE_CHUNK_STAGING"
                or self.drive_upload_performed is not False or self.live_market_data_authorized is not False):
            raise ValueError("No production or Drive-upload authorization from a fixture manifest")

    def canonical_json(self) -> str:
        obj = asdict(self)
        obj["created_at_utc"] = self.created_at_utc.isoformat(timespec="microseconds")
        return _json(obj).decode("ascii")

    @property
    def digest(self) -> str:
        return _sha(self.canonical_json().encode("ascii"))

    @classmethod
    def parse_json(cls, raw: str) -> "FixturePartitionManifest":
        if not isinstance(raw, str) or len(raw) > 4096:
            raise ValueError("Bounded manifest required")
        obj = _decode_json(raw.encode("utf-8"), max_size=4096)
        if set(obj) != _MANIFEST_FIELDS or not isinstance(obj["created_at_utc"], str):
            raise ValueError("Exact manifest fields required")
        obj["created_at_utc"] = datetime.fromisoformat(obj["created_at_utc"])
        result = cls(**obj)
        if result.canonical_json() != raw:
            raise ValueError("Canonical manifest required")
        return result


class PartitionWrite(str, Enum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    REUSED = "REUSED"


@dataclass(frozen=True)
class PartitionSyncResult:
    created: int
    updated: int
    reused: int
    source_api_calls: int = 0
    actual_drive_api_calls: int = 0
    live_cache_authorized: bool = False

    def __post_init__(self):
        if self.source_api_calls or self.actual_drive_api_calls or self.live_cache_authorized:
            raise ValueError("Memory fixture simulator may never report real API calls or rights")


class SyntheticDrivePartitionIndex:
    """Immutable chunk+per-partition manifest *simulation*, NOT Google Drive API.

    All heads and pins are mutable same-process test state, NOT an independently
    anchored anti-rollback or distributed CAS/lease. Stale writes are rejected
    only relative to this in-memory state.
    """
    def __init__(self) -> None:
        self._chunks: dict[str, bytes] = {}
        self._manifests: dict[str, str] = {}
        self._history: dict[str, list[str]] = {}
        self._active: dict[str, str] = {}

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    @property
    def manifest_count(self) -> int:
        return len(self._manifests)

    def active_manifest_sha(self, identity: CacheIdentity) -> str | None:
        return self._active.get(identity.fingerprint)

    @property
    def read_port_descriptor(self) -> PortDescriptor:
        """Read-only structural fixture contract; not a licensed storage port."""
        return PortDescriptor("cache.readonly_fixture", "1.0.0",
                              "SYNTHETIC_TEST_ONLY", ("get_head", "read_partition"))

    def get_head(self, identity: CacheIdentity) -> str | None:
        """Untrusted candidate head; verified only by read_partition."""
        if not isinstance(identity, CacheIdentity):
            raise TypeError("Typed cache namespace required")
        return self.active_manifest_sha(identity)

    def read_partition(self, identity: CacheIdentity, *, pinned_digest: str
                       ) -> tuple[FixtureBar, ...]:
        """Unified H2 read contract, preserving the existing C3B wire format."""
        return self.load(identity, pinned_manifest_sha256=pinned_digest)

    def _manifest_chain(self, identity: CacheIdentity) -> tuple[FixturePartitionManifest, ...]:
        key = identity.fingerprint
        history = self._history.get(key, [])
        head = self._active.get(key)
        if not history:
            if head is not None:
                raise ValueError("Active pointer without history")
            return ()
        if head != history[-1]:
            raise ValueError("Active pointer not at end of witnessed fixture history")
        result = []
        previous = None
        for index, sha in enumerate(history, 1):
            content = self._manifests.get(sha)
            if content is None or _sha(content.encode("utf-8")) != sha:
                raise ValueError("Missing/corrupt fixture manifest")
            m = FixturePartitionManifest.parse_json(content)
            if (m.partition_sha256 != key or m.generation != index
                    or m.previous_manifest_sha256 != previous):
                raise ValueError("Broken fixture manifest generation chain")
            result.append(m)
            previous = sha
        return tuple(result)

    def stage_and_publish(self, identity: CacheIdentity, bars: tuple[FixtureBar, ...], *,
                          expected_head_sha256: str | None,
                          created_at_utc: datetime,
                          simulate_crash_after_chunk: bool = False) -> PartitionWrite:
        _utc(created_at_utc)
        if expected_head_sha256 is not None:
            _checked_sha(expected_head_sha256)
        history = self._manifest_chain(identity)
        current = history[-1] if history else None
        if expected_head_sha256 != self._active.get(identity.fingerprint):
            raise ValueError("Stale synthetic writer: expected manifest head changed")
        if type(simulate_crash_after_chunk) is not bool:
            raise TypeError("Synthetic crash flag must be boolean")
        raw = encode_fixture_chunk(identity, bars)
        if any(b.end_utc > created_at_utc or b.first_known_utc > created_at_utc for b in bars):
            raise ValueError("Cannot archive future or not-yet-known fixture rows")
        content_sha = _sha(raw)
        name = f"st18-{identity.fingerprint}-{content_sha}.fixture.json"
        if name in self._chunks and self._chunks[name] != raw:
            raise ValueError("Content-addressed name has mismatching fixture bytes")
        if current is not None and current.chunk_sha256 == content_sha:
            # Even on an unchanged five-minute scan, reject missing/corrupt
            # previously published cache bytes instead of silently reusing.
            self.load(identity, pinned_manifest_sha256=current.digest,
                      minimum_generation=current.generation)
            return PartitionWrite.REUSED
        self._chunks.setdefault(name, raw)
        if simulate_crash_after_chunk:
            raise RuntimeError("Simulated failure after immutable chunk staging; orphan chunk only")
        manifest = FixturePartitionManifest(
            partition_sha256=identity.fingerprint,
            chunk_name=name, chunk_sha256=content_sha, chunk_bytes=len(raw),
            bar_count=len(bars), checkpoint_count=len(bars),
            generation=len(history)+1,
            previous_manifest_sha256=history[-1].digest if history else None,
            created_at_utc=created_at_utc,
        )
        # Validate materialization and full indicator parity before pointer publish.
        if len(self._chunks[name]) != manifest.chunk_bytes or _sha(self._chunks[name]) != manifest.chunk_sha256:
            raise ValueError("Staged fixture content mismatch")
        if decode_fixture_chunk(self._chunks[name], expected_identity=identity) != bars:
            raise ValueError("Staged fixture is not identical to source fixture partition")
        self._manifests[manifest.digest] = manifest.canonical_json()
        self._history.setdefault(identity.fingerprint, []).append(manifest.digest)
        self._active[identity.fingerprint] = manifest.digest
        return PartitionWrite.CREATED if current is None else PartitionWrite.UPDATED

    def load(self, identity: CacheIdentity, *, pinned_manifest_sha256: str,
             minimum_generation: int = 1) -> tuple[FixtureBar, ...]:
        _checked_sha(pinned_manifest_sha256)
        if type(minimum_generation) is not int or minimum_generation < 1:
            raise ValueError("Positive caller-supplied generation floor required")
        history = self._manifest_chain(identity)
        if not history or pinned_manifest_sha256 != self._active.get(identity.fingerprint):
            raise ValueError("Missing or changed independently pinned fixture manifest head")
        manifest = history[-1]
        if manifest.generation < minimum_generation:
            raise ValueError("Pinned fixture generation rolls back below caller floor")
        raw = self._chunks.get(manifest.chunk_name)
        if raw is None or len(raw) != manifest.chunk_bytes or _sha(raw) != manifest.chunk_sha256:
            raise ValueError("Pinned fixture chunk missing or checksum mismatch")
        bars = decode_fixture_chunk(raw, expected_identity=identity)
        if len(bars) != manifest.bar_count:
            raise ValueError("Pinned fixture row count mismatch")
        if any(b.end_utc > manifest.created_at_utc or b.first_known_utc > manifest.created_at_utc for b in bars):
            raise ValueError("Fixture manifest predates stored observations")
        return bars

    def sync_selected(self, store: SyntheticIncrementalStore,
                      identities: tuple[CacheIdentity, ...], *,
                      created_at_utc: datetime) -> PartitionSyncResult:
        """Only inspect requested local partitions; no provider or Drive requests."""
        if not isinstance(store, SyntheticIncrementalStore) or not isinstance(identities, tuple):
            raise TypeError("Synthetic store and tuple of requested identities required")
        if not 0 < len(identities) <= MAX_PARTITIONS_PER_SYNC:
            raise ValueError("Bounded nonempty partition selection required")
        fingerprints = [identity.fingerprint for identity in identities]
        if len(set(fingerprints)) != len(fingerprints):
            raise ValueError("Duplicate requested fixture partition")
        counts = {x:0 for x in PartitionWrite}
        for identity in identities:
            bars = store.read_bars(identity)
            if not bars:
                continue
            outcome = self.stage_and_publish(
                identity, bars,
                expected_head_sha256=self.active_manifest_sha(identity),
                created_at_utc=created_at_utc,
            )
            counts[outcome] += 1
        return PartitionSyncResult(counts[PartitionWrite.CREATED],
                                   counts[PartitionWrite.UPDATED],
                                   counts[PartitionWrite.REUSED])

    def restore_partition(self, store: SyntheticIncrementalStore, identity: CacheIdentity, *,
                          pinned_manifest_sha256: str,
                          minimum_generation: int = 1) -> int:
        """Reconstruct local SQLite from verified chunk; do not overwrite a partition.

        The independent full indicator replay here is intentional integrity
        validation, NOT yet an optimized direct L2 checkpoint import.
        """
        if not isinstance(store, SyntheticIncrementalStore):
            raise TypeError("Synthetic working store only")
        bars = self.load(identity, pinned_manifest_sha256=pinned_manifest_sha256,
                         minimum_generation=minimum_generation)
        if store.read_bars(identity):
            raise ValueError("Restore refuses overwrite of an existing local cache partition")
        manifest = self._manifest_chain(identity)[-1]
        now = manifest.created_at_utc
        update = store.apply_fixture_window(
            identity, bars, observed_at_utc=now, scope_start_utc=bars[0].start_utc,
            scope_end_utc=max(b.end_utc for b in bars),
            complete_scope=False, full_session_reconciled=False,
        )
        if update.inserted != len(bars) or store.read_checkpoints(identity) != full_recompute(bars):
            raise ValueError("Fixture local reconstruction failed validation")
        return update.inserted

    def simulate_corrupt_chunk(self, identity: CacheIdentity) -> None:
        """Explicit destructive test hook, never a production entrypoint."""
        m = self._manifest_chain(identity)[-1]
        self._chunks[m.chunk_name] += b"tampered"

    def simulate_missing_chunk(self, identity: CacheIdentity) -> None:
        m = self._manifest_chain(identity)[-1]
        del self._chunks[m.chunk_name]

    def simulate_forged_head(self, identity: CacheIdentity, sha: str) -> None:
        self._active[identity.fingerprint] = sha


def require_real_market_cache_transport(*_args: object, **_kwargs: object) -> None:
    raise PermissionError("No vendor retention rights, protected Drive writer, source trust or live cache authorization")
