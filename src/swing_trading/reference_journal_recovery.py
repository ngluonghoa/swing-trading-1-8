"""GĐ4/P0.18 — metadata-only, independently pinnable reference journal recovery.

This is a logical SQLite snapshot, NOT a byte copy of the live database.
It deliberately NEVER writes the optional SSI/DNSE quote cache to backup,
including SQLite free pages, WAL or rollback journals. The live source may
still contain licensed data: source storage/erasure is OUT OF SCOPE.
No code here can independently approve a checkpoint or production host.
"""
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile

from .evidence_checkpoint import file_sha256
from .reference_journal import (
    ReferenceJournal, ReferenceJournalCorrupt, ZERO, _json, _utc,
)

_SHA = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SNAPSHOT_KIND = "METADATA_ONLY"


def _id(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("Explicit stable checkpoint/store identifier required")


def _sha(value):
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise ValueError("Lowercase SHA256 required")


@dataclass(frozen=True)
class JournalCheckpoint:
    """A candidate only: trust requires separate, access-controlled pinning."""
    checkpoint_id: str
    store_id: str
    created_at_utc: datetime
    record_count: int
    chain_tip_sha256: str
    backup_sha256: str
    omitted_cache_rows: int
    schema_version: int = 1
    snapshot_kind: str = _SNAPSHOT_KIND

    def __post_init__(self):
        _id(self.checkpoint_id)
        _id(self.store_id)
        _utc(self.created_at_utc)
        if type(self.record_count) is not int or self.record_count < 0:
            raise ValueError("Invalid journal record count")
        if type(self.omitted_cache_rows) is not int or self.omitted_cache_rows < 0:
            raise ValueError("Invalid cache omission count")
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("Unsupported checkpoint schema")
        if self.snapshot_kind != _SNAPSHOT_KIND:
            raise ValueError("Only metadata-only checkpoint format is supported")
        _sha(self.chain_tip_sha256)
        _sha(self.backup_sha256)
        if ((self.record_count == 0 and self.chain_tip_sha256 != ZERO)
                or (self.record_count > 0 and self.chain_tip_sha256 == ZERO)):
            raise ValueError("Journal count and chain tip disagree")

    def canonical_json(self) -> str:
        return _json({
            "checkpoint_id": self.checkpoint_id,
            "store_id": self.store_id,
            "created_at_utc": _utc(self.created_at_utc),
            "record_count": self.record_count,
            "chain_tip_sha256": self.chain_tip_sha256,
            "backup_sha256": self.backup_sha256,
            "omitted_cache_rows": self.omitted_cache_rows,
            "schema_version": self.schema_version,
            "snapshot_kind": self.snapshot_kind,
        })

    @classmethod
    def parse_json(cls, value: str) -> "JournalCheckpoint":
        if not isinstance(value, str):
            raise TypeError("Checkpoint must be JSON text")
        data = json.loads(value)
        fields = {
            "checkpoint_id", "store_id", "created_at_utc", "record_count",
            "chain_tip_sha256", "backup_sha256", "omitted_cache_rows",
            "schema_version", "snapshot_kind",
        }
        if not isinstance(data, dict) or set(data) != fields:
            raise ValueError("Exact journal checkpoint schema required")
        if not isinstance(data["created_at_utc"], str):
            raise ValueError("UTC timestamp must be text")
        data["created_at_utc"] = datetime.fromisoformat(data["created_at_utc"])
        return cls(**data)


def _paths(destination: str | Path) -> tuple[Path, Path, Path]:
    """Prepare a private staging DIRECTORY: temp DB never holds quote bytes."""
    dest = Path(destination).expanduser().absolute()
    if dest.exists() or dest.is_symlink():
        raise FileExistsError(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    temporary_directory = Path(tempfile.mkdtemp(
        prefix=".swing-reference-snapshot-", dir=dest.parent
    ))
    return dest, temporary_directory, temporary_directory / "journal.sqlite"


def _publish(source: Path, dest: Path):
    """No-overwrite publish + directory durability on supported POSIX hosts."""
    os.link(source, dest)
    dir_fd = os.open(str(dest.parent), os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def _verify_snapshot(path: str | Path, expected: tuple[int, str]):
    store = ReferenceJournal(path)
    with closing(store._connection()) as c:
        c.execute("BEGIN")
        try:
            observed = store._verify(c)
            cached = c.execute("SELECT count(*) FROM cache").fetchone()[0]
            if cached != 0:
                raise ReferenceJournalCorrupt(
                    "Protected snapshot must never contain SSI/DNSE quote cache"
                )
            if observed != expected:
                raise ReferenceJournalCorrupt("Journal snapshot chain/count mismatch")
            return observed
        finally:
            c.execute("ROLLBACK")


def create_candidate_journal_checkpoint(
    store: ReferenceJournal,
    backup_destination: str | Path,
    checkpoint_id: str,
    store_id: str,
    created_at_utc: datetime,
) -> JournalCheckpoint:
    """Take a consistent logical snapshot of journal METADATA ONLY.

    Quote bytes are not copied then deleted: only selected journal columns are
    inserted into a FRESH, private SQLite database. This avoids recoverable
    quote bytes in SQLite freelist and sidecar WAL/rollback files.
    """
    if not isinstance(store, ReferenceJournal):
        raise TypeError("ReferenceJournal required")
    _id(checkpoint_id)
    _id(store_id)
    _utc(created_at_utc)
    dest, temporary_directory, staging = _paths(backup_destination)
    try:
        with closing(store._connection()) as source:
            source.execute("BEGIN")
            try:
                count, tip = store._verify(source)
                omitted = source.execute("SELECT count(*) FROM cache").fetchone()[0]
                output = ReferenceJournal(staging)
                output.initialize()
                os.chmod(staging, 0o600)
                with closing(output._connection(writable=True)) as target:
                    target.execute("BEGIN IMMEDIATE")
                    try:
                        for row in source.execute(
                            "SELECT seq,run_id,body,prev,chained FROM journal ORDER BY seq"
                        ):
                            target.execute(
                                """INSERT INTO journal(seq,run_id,body,prev,chained)
                                   VALUES(?,?,?,?,?)""",
                                (row["seq"], row["run_id"], row["body"],
                                 row["prev"], row["chained"]),
                            )
                        target.execute("COMMIT")
                    except Exception:
                        target.execute("ROLLBACK")
                        raise
                    # No WAL or SQLite sidecar needs to accompany the
                    # published, single-file, read-only backup artifact.
                    target.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    mode = target.execute("PRAGMA journal_mode=DELETE").fetchone()[0]
                    if mode.lower() != "delete":
                        raise ReferenceJournalCorrupt("Failed to close snapshot WAL mode")
                _verify_snapshot(staging, (count, tip))
            finally:
                source.execute("ROLLBACK")
        for suffix in ("-wal", "-shm", "-journal"):
            if staging.with_name(staging.name + suffix).exists():
                raise ReferenceJournalCorrupt("Incomplete snapshot sidecar cleanup")
        with staging.open("rb") as f:
            os.fsync(f.fileno())
        checkpoint = JournalCheckpoint(
            checkpoint_id, store_id, created_at_utc, count, tip,
            file_sha256(staging), omitted,
        )
        _publish(staging, dest)
        return checkpoint
    finally:
        shutil.rmtree(temporary_directory)


def verify_journal_backup_against_pinned(
    backup_path: str | Path,
    approved_checkpoint: JournalCheckpoint,
    *,
    expected_store_id: str,
) -> tuple[int, str]:
    """Trust requires separately supplied, already pinned checkpoint metadata."""
    if not isinstance(approved_checkpoint, JournalCheckpoint):
        raise TypeError("Independently supplied JournalCheckpoint required")
    if approved_checkpoint.store_id != expected_store_id:
        raise ReferenceJournalCorrupt("Store namespace mismatch")
    if file_sha256(backup_path) != approved_checkpoint.backup_sha256:
        raise ReferenceJournalCorrupt("Backup bytes differ from pinned SHA256")
    return _verify_snapshot(
        backup_path,
        (approved_checkpoint.record_count, approved_checkpoint.chain_tip_sha256),
    )


def restore_journal_from_pinned(
    backup_path: str | Path,
    destination: str | Path,
    approved_checkpoint: JournalCheckpoint,
    *,
    expected_store_id: str,
) -> ReferenceJournal:
    """Restore metadata-only journal to NEW path; quotes are never resurrected."""
    verify_journal_backup_against_pinned(
        backup_path, approved_checkpoint, expected_store_id=expected_store_id
    )
    dest, temporary_directory, staging = _paths(destination)
    try:
        with Path(backup_path).open("rb") as source, staging.open("xb") as target:
            # The staging DIRECTORY is private, but the final hard-linked
            # destination must itself have owner-only permissions.
            os.chmod(staging, 0o600)
            shutil.copyfileobj(source, target, length=1024 * 1024)
            target.flush()
            os.fsync(target.fileno())
        if file_sha256(staging) != approved_checkpoint.backup_sha256:
            raise ReferenceJournalCorrupt("Copied restore differs from pinned bytes")
        _verify_snapshot(
            staging,
            (approved_checkpoint.record_count, approved_checkpoint.chain_tip_sha256),
        )
        _publish(staging, dest)
        return ReferenceJournal(dest)
    finally:
        shutil.rmtree(temporary_directory)


def verify_journal_history_prefix(
    store: ReferenceJournal,
    approved_checkpoint: JournalCheckpoint,
    *,
    expected_store_id: str,
) -> tuple[int, str]:
    """Compare live immutable history prefix with independently held checkpoint.

    Does not authenticate unpinned tail writes or ever check source licence.
    The *live* store may contain opt-in cache; checkpoint backup never does.
    """
    if not isinstance(store, ReferenceJournal):
        raise TypeError("ReferenceJournal required")
    if not isinstance(approved_checkpoint, JournalCheckpoint):
        raise TypeError("Independently pinned JournalCheckpoint required")
    if approved_checkpoint.store_id != expected_store_id:
        raise ReferenceJournalCorrupt("Pinned store namespace mismatch")
    with closing(store._connection()) as c:
        c.execute("BEGIN")
        try:
            count, tip = store._verify(c)
            if count < approved_checkpoint.record_count:
                raise ReferenceJournalCorrupt("Journal truncated below pinned prefix")
            if approved_checkpoint.record_count == 0:
                prefix_tip = ZERO
            else:
                row = c.execute(
                    "SELECT chained FROM journal ORDER BY seq LIMIT 1 OFFSET ?",
                    (approved_checkpoint.record_count - 1,),
                ).fetchone()
                if row is None:
                    raise ReferenceJournalCorrupt("Pinned historical journal row missing")
                prefix_tip = row["chained"]
            if prefix_tip != approved_checkpoint.chain_tip_sha256:
                raise ReferenceJournalCorrupt("Pinned historical journal prefix changed")
            return count, tip
        finally:
            c.execute("ROLLBACK")
