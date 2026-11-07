"""GĐ4/C3A: *synthetic fixture only* SQLite snapshot/restore preparation.

This module has NO Google Drive/API transport, no credentials, no licensed
SSI/DNSE/VCBS data, no production rights gate and no autonomous scheduling.
A checksum is NOT a signature; caller-controlled pins cannot defeat malicious
rollback when both the snapshot and the pin are replaced.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import shutil
import sqlite3
import tempfile

from .incremental_cache import (
    IndicatorCheckpoint, SyntheticIncrementalStore, _parse_utc, full_recompute,
)

_SCHEMA_VERSION = 1
_MAX_SQLITE_BYTES = 16 * 1024 * 1024
_MAX_FIXTURE_ROWS = 100_000
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_TABLES = ("config", "fixture_bars", "fixture_checkpoints",
           "fixture_cursor", "fixture_lineage")
_ALLOWED_TABLES = set(_TABLES) | {"sqlite_sequence"}
_REQUIRED_FIELDS = frozenset({
    "format_version", "project_id", "environment", "snapshot_id",
    "generation", "previous_manifest_sha256", "created_at_utc",
    "sqlite_sha256", "sqlite_bytes", "row_counts",
    "storage_class", "live_market_data_authorized", "drive_upload_performed",
})


def _utc(ts: datetime) -> datetime:
    if (not isinstance(ts, datetime) or ts.tzinfo is None
            or ts.utcoffset() != timedelta(0)):
        raise ValueError("Explicit UTC timestamp required")
    return ts


def _digest_file(path: Path) -> str:
    h = sha256()
    with path.open("rb") as stream:
        for piece in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(piece)
    return h.hexdigest()


def _digest_text(content: str) -> str:
    return sha256(content.encode("utf-8")).hexdigest()


def _hash(value: str) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise ValueError("Lowercase SHA-256 required")
    return value


def _candidate_path(value: str | Path, *, already_exists: bool) -> Path:
    p = Path(value)
    if not p.is_absolute() or ".." in p.parts or p.is_symlink():
        raise ValueError("Absolute, non-symlink, non-traversal file required")
    if not p.parent.is_dir() or p.parent.is_symlink():
        raise ValueError("Existing non-symlink parent required")
    for folder in p.parent.parents:
        if (folder / ".git").exists():
            raise ValueError("Do not place cache under a Git working tree")
    if (p.parent / ".git").exists():
        raise ValueError("Do not place cache under a Git working tree")
    if already_exists:
        if not p.is_file():
            raise FileNotFoundError("Expected existing regular file")
    elif p.exists() or p.is_symlink():
        raise FileExistsError("Refuse overwrite of snapshot, manifest or destination")
    return p


@dataclass(frozen=True)
class FixtureSnapshotManifest:
    """Portable *metadata only* receipt for a consistent synthetic SQLite copy."""
    snapshot_id: str
    generation: int
    previous_manifest_sha256: str | None
    created_at_utc: datetime
    sqlite_sha256: str
    sqlite_bytes: int
    row_counts: tuple[int, int, int, int, int]
    format_version: int = _SCHEMA_VERSION
    project_id: str = "SwingTrading1.8"
    environment: str = "SYNTHETIC_TEST_ONLY"
    storage_class: str = "DRIVE_STAGING_SYNTHETIC_ONLY"
    live_market_data_authorized: bool = False
    drive_upload_performed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot_id, str) or not _ID.fullmatch(self.snapshot_id):
            raise ValueError("Stable normalized snapshot id required")
        if type(self.generation) is not int or not 1 <= self.generation <= 2**63 - 1:
            raise ValueError("Positive bounded snapshot generation required")
        if ((self.generation == 1 and self.previous_manifest_sha256 is not None)
                or (self.generation > 1 and self.previous_manifest_sha256 is None)):
            raise ValueError("Only genesis generation has no prior manifest")
        if self.previous_manifest_sha256 is not None:
            _hash(self.previous_manifest_sha256)
        _utc(self.created_at_utc)
        _hash(self.sqlite_sha256)
        if type(self.sqlite_bytes) is not int or not 0 < self.sqlite_bytes <= _MAX_SQLITE_BYTES:
            raise ValueError("Bounded SQLite file length required")
        if (not isinstance(self.row_counts, tuple) or len(self.row_counts) != len(_TABLES)
                or any(type(n) is not int or n < 0 or n > _MAX_FIXTURE_ROWS for n in self.row_counts)):
            raise ValueError("Bounded exact per-table row counts required")
        if (type(self.format_version) is not int or self.format_version != _SCHEMA_VERSION
                or self.project_id != "SwingTrading1.8"
                or self.environment != "SYNTHETIC_TEST_ONLY"
                or self.storage_class != "DRIVE_STAGING_SYNTHETIC_ONLY"
                or self.live_market_data_authorized is not False
                or self.drive_upload_performed is not False):
            raise ValueError("Snapshot cannot claim production/cloud authority")

    def canonical_json(self) -> str:
        payload = {
            "format_version": self.format_version,
            "project_id": self.project_id,
            "environment": self.environment,
            "snapshot_id": self.snapshot_id,
            "generation": self.generation,
            "previous_manifest_sha256": self.previous_manifest_sha256,
            "created_at_utc": self.created_at_utc.isoformat(timespec="microseconds"),
            "sqlite_sha256": self.sqlite_sha256,
            "sqlite_bytes": self.sqlite_bytes,
            "row_counts": dict(zip(_TABLES, self.row_counts)),
            "storage_class": self.storage_class,
            "live_market_data_authorized": self.live_market_data_authorized,
            "drive_upload_performed": self.drive_upload_performed,
        }
        return json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=True)

    @property
    def digest(self) -> str:
        return _digest_text(self.canonical_json())

    @classmethod
    def parse_json(cls, content: str) -> "FixtureSnapshotManifest":
        if not isinstance(content, str) or len(content) > 4096:
            raise ValueError("Bounded manifest JSON text required")
        def reject_duplicate(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate manifest JSON key")
                result[key] = value
            return result
        d = json.loads(content, object_pairs_hook=reject_duplicate,
                       parse_constant=lambda x: (_ for _ in ()).throw(ValueError("Invalid JSON numeric constant")))
        if type(d) is not dict or set(d) != _REQUIRED_FIELDS:
            raise ValueError("Exact manifest fields required")
        counts = d["row_counts"]
        if type(counts) is not dict or set(counts) != set(_TABLES):
            raise ValueError("Exact table count keys required")
        if not isinstance(d["created_at_utc"], str):
            raise ValueError("Explicit timestamp text required")
        d["created_at_utc"] = datetime.fromisoformat(d["created_at_utc"])
        d["row_counts"] = tuple(counts[t] for t in _TABLES)
        obj = cls(**d)
        if content != obj.canonical_json():
            raise ValueError("Noncanonical manifest bytes not accepted")
        return obj


def _inspect_sqlite(path: Path) -> tuple[int, int, int, int, int]:
    """Verify backed-up synthetic schema/digests/causal EMA-ATR parity, read-only.

    Snapshot bytes are not market-licensed or certified synthetic by inspection;
    this is solely a data-integrity regression on the caller's fixture database.
    """
    if path.is_symlink() or not path.is_file():
        raise ValueError("SQLite snapshot must be an existing regular file")
    if not 0 < path.stat().st_size <= _MAX_SQLITE_BYTES:
        raise ValueError("Fixture snapshot exceeds configured size bound")
    uri = path.as_uri() + "?mode=ro&immutable=1"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA trusted_schema=OFF")
        connection.execute("PRAGMA query_only=ON")
        if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity check failed")
        types = {row["name"] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if types != _ALLOWED_TABLES and types != set(_TABLES):
            raise ValueError("Unknown or missing fixture tables")
        schema_row = connection.execute("SELECT val FROM config WHERE name='schema'").fetchall()
        if len(schema_row) != 1 or schema_row[0]["val"] != "1":
            raise ValueError("Unknown fixture cache schema")
        counts = tuple(connection.execute(
            "SELECT COUNT(*) FROM " + table).fetchone()[0] for table in _TABLES)
        if any(n > _MAX_FIXTURE_ROWS for n in counts):
            raise ValueError("Fixture row quota exceeded")
        keys = [row[0] for row in connection.execute(
            "SELECT DISTINCT cache_key FROM fixture_bars ORDER BY cache_key")]
        checkpoint_keys = {row[0] for row in connection.execute(
            "SELECT DISTINCT cache_key FROM fixture_checkpoints")}
        if checkpoint_keys != set(keys):
            raise ValueError("Orphan or missing checkpoint namespace")
        for key in keys:
            rows = connection.execute(
                "SELECT * FROM fixture_bars WHERE cache_key=? ORDER BY start_utc", (key,)).fetchall()
            bars = tuple(SyntheticIncrementalStore._bar(row) for row in rows)
            expected = full_recompute(bars)
            current = tuple(IndicatorCheckpoint(_parse_utc(row["start_utc"]),
                          Decimal(row["ema20"]), Decimal(row["atr14"]) if row["atr14"] is not None else None,
                          row["atr_seen"], Decimal(row["atr_seed_sum"]), Decimal(row["last_close"]))
                          for row in connection.execute(
                              "SELECT * FROM fixture_checkpoints WHERE cache_key=? ORDER BY start_utc", (key,)))
            if current != expected:
                raise ValueError("Fixture indicator checkpoints do not match cold replay")
        return counts


def create_fixture_snapshot(
    store: SyntheticIncrementalStore,
    snapshot_path: str | Path,
    manifest_path: str | Path,
    *,
    snapshot_id: str,
    generation: int,
    previous_manifest_sha256: str | None,
    created_at_utc: datetime,
) -> FixtureSnapshotManifest:
    """WAL-aware SQLite online backup, no-overwrite new files, no remote upload.

    Only the manifest is the *portable cache metadata*; the SQLite snapshot
    contains invented fixture bars and MUST NOT be committed to source control.
    """
    if not isinstance(store, SyntheticIncrementalStore):
        raise TypeError("C3A accepts only the synthetic fixture cache class")
    src = _candidate_path(store.path, already_exists=True)
    destination = _candidate_path(snapshot_path, already_exists=False)
    manifest_file = _candidate_path(manifest_path, already_exists=False)
    if src in (destination, manifest_file) or destination == manifest_file:
        raise ValueError("Distinct source, snapshot and manifest paths required")
    _utc(created_at_utc)
    # Validate the sequence before creating any output.
    _hash(previous_manifest_sha256) if previous_manifest_sha256 is not None else None
    if type(generation) is not int or (generation == 1) != (previous_manifest_sha256 is None):
        raise ValueError("Explicit genesis/continuation generation required")
    made_snapshot = made_manifest = False
    try:
        with tempfile.TemporaryDirectory(prefix="c3a-fixture-", dir=destination.parent) as tmpdir:
            pending = Path(tmpdir) / "snapshot.sqlite"
            with closing(sqlite3.connect(src, timeout=5)) as source, closing(sqlite3.connect(pending)) as target:
                source.backup(target)
            os.chmod(pending, 0o600)
            counts = _inspect_sqlite(pending)
            manifest = FixtureSnapshotManifest(
                snapshot_id, generation, previous_manifest_sha256, created_at_utc,
                _digest_file(pending), pending.stat().st_size, counts)
            # Opening with x never replaces an existing destination, including symlinks.
            with destination.open("xb") as f:
                made_snapshot = True
                os.chmod(destination, 0o600)
                with pending.open("rb") as inp:
                    shutil.copyfileobj(inp, f, 1024 * 1024)
                f.flush()
                os.fsync(f.fileno())
            if _digest_file(destination) != manifest.sqlite_sha256:
                raise ValueError("Snapshot copy failed integrity check")
            with manifest_file.open("x", encoding="utf-8") as f:
                made_manifest = True
                os.chmod(manifest_file, 0o600)
                f.write(manifest.canonical_json())
                f.flush()
                os.fsync(f.fileno())
        return manifest
    except Exception:
        if made_manifest:
            manifest_file.unlink(missing_ok=True)
        if made_snapshot:
            destination.unlink(missing_ok=True)
        raise


def verify_fixture_snapshot(
    snapshot_path: str | Path, manifest_text: str, *,
    pinned_manifest_sha256: str,
    minimum_generation: int = 1,
    expected_parent_sha256: str | None = None,
) -> FixtureSnapshotManifest:
    """Pin supplied out of band; *NOT* independent if caller controls both."""
    path = _candidate_path(snapshot_path, already_exists=True)
    _hash(pinned_manifest_sha256)
    if _digest_text(manifest_text) != pinned_manifest_sha256:
        raise ValueError("Manifest differs from separately supplied pinned digest")
    manifest = FixtureSnapshotManifest.parse_json(manifest_text)
    if type(minimum_generation) is not int or minimum_generation < 1:
        raise ValueError("Valid monotonic generation floor required")
    if manifest.generation < minimum_generation:
        raise ValueError("Snapshot generation rolls back below caller floor")
    if expected_parent_sha256 is not None and manifest.previous_manifest_sha256 != _hash(expected_parent_sha256):
        raise ValueError("Snapshot does not link expected previous manifest")
    if (path.stat().st_size != manifest.sqlite_bytes
            or _digest_file(path) != manifest.sqlite_sha256):
        raise ValueError("SQLite bytes differ from pinned manifest")
    if _inspect_sqlite(path) != manifest.row_counts:
        raise ValueError("SQLite table counts disagree with pinned manifest")
    return manifest


def restore_fixture_snapshot(
    snapshot_path: str | Path, destination_path: str | Path,
    manifest_text: str, *,
    pinned_manifest_sha256: str,
    minimum_generation: int = 1,
    expected_parent_sha256: str | None = None,
) -> SyntheticIncrementalStore:
    """Verify BEFORE exclusive copy; never overwrite, never auto-start live cache."""
    manifest = verify_fixture_snapshot(
        snapshot_path, manifest_text,
        pinned_manifest_sha256=pinned_manifest_sha256,
        minimum_generation=minimum_generation,
        expected_parent_sha256=expected_parent_sha256)
    source = _candidate_path(snapshot_path, already_exists=True)
    target = _candidate_path(destination_path, already_exists=False)
    if source == target:
        raise ValueError("Restore source and destination must differ")
    for suffix in ("-wal", "-shm", "-journal"):
        if Path(str(target) + suffix).exists():
            raise ValueError("Stale destination SQLite journal sidecar")
    made = False
    try:
        with target.open("xb") as out:
            made = True
            os.chmod(target, 0o600)
            with source.open("rb") as inp:
                shutil.copyfileobj(inp, out, 1024 * 1024)
            out.flush()
            os.fsync(out.fileno())
        verify_fixture_snapshot(target, manifest_text, pinned_manifest_sha256=pinned_manifest_sha256,
                                minimum_generation=minimum_generation,
                                expected_parent_sha256=expected_parent_sha256)
        return SyntheticIncrementalStore(target)
    except Exception:
        if made:
            target.unlink(missing_ok=True)
        raise


def require_approved_cache_transport(*_args: object, **_kwargs: object) -> None:
    raise PermissionError("No approved real-data rights, off-host pin or Google Drive runtime transport")
