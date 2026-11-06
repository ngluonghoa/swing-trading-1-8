"""P0.4C independently pinned evidence checkpoints (engineering-only).

A checkpoint is trustworthy only when its digest and chain tip are stored
OUTSIDE the SQLite database and controlled by a separately approved custodian.
These helpers do not sign checkpoints, grant SSI permissions, or authorize
historical backtests/trading.
"""
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re

from .durable_evidence import EvidenceCorrupt, EvidenceStore, ZERO
from .evidence_recovery import backup_verified, restore_verified
from .replay import require_utc

_SHA = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _validate_sha(s: str):
    if not isinstance(s, str) or not _SHA.fullmatch(s):
        raise ValueError("Expected lowercase SHA-256 digest")


def file_sha256(path: str | Path) -> str:
    """Bounded streaming hash; does not retain sensitive bytes in memory."""
    hasher = sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


@dataclass(frozen=True)
class EvidenceCheckpoint:
    checkpoint_id: str
    store_id: str
    created_at_utc: datetime
    record_count: int
    chain_tip_sha256: str
    backup_sha256: str
    schema_version: int = 1

    def __post_init__(self):
        for name in ("checkpoint_id", "store_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not _ID.fullmatch(value):
                raise ValueError(name + " must have a stable explicit identifier")
        require_utc(self.created_at_utc)
        if type(self.record_count) is not int or self.record_count < 0:
            raise ValueError("Record count must be nonnegative integer")
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("Unknown checkpoint schema")
        _validate_sha(self.chain_tip_sha256)
        _validate_sha(self.backup_sha256)
        if self.record_count == 0 and self.chain_tip_sha256 != ZERO:
            raise ValueError("Empty store must have genesis chain tip")
        if self.record_count > 0 and self.chain_tip_sha256 == ZERO:
            raise ValueError("Nonempty store cannot have genesis tip")

    def canonical_json(self) -> str:
        """Stable serialization for copying to independent custody."""
        return json.dumps({
            "checkpoint_id": self.checkpoint_id,
            "store_id": self.store_id,
            "created_at_utc": self.created_at_utc.isoformat(timespec="microseconds"),
            "record_count": self.record_count,
            "chain_tip_sha256": self.chain_tip_sha256,
            "backup_sha256": self.backup_sha256,
            "schema_version": self.schema_version,
        }, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def parse_json(cls, text: str) -> "EvidenceCheckpoint":
        if not isinstance(text, str):
            raise TypeError("Checkpoint must be JSON text")
        data = json.loads(text)
        required = {"checkpoint_id", "store_id", "created_at_utc", "record_count",
                    "chain_tip_sha256", "backup_sha256", "schema_version"}
        if not isinstance(data, dict) or set(data) != required:
            raise ValueError("Checkpoint requires exact schema, no silent defaults")
        timestamp = data["created_at_utc"]
        if not isinstance(timestamp, str):
            raise ValueError("Checkpoint UTC time must be text")
        data["created_at_utc"] = datetime.fromisoformat(timestamp)
        return cls(**data)


def create_candidate_checkpoint(
    store: EvidenceStore, backup_destination: str | Path,
    checkpoint_id: str, store_id: str, created_at_utc: datetime,
) -> EvidenceCheckpoint:
    """Produce a candidate for *independent* approval/custody, never auto-approve.

    The backup must be published to a NEW file. Checkpoints are not embedded
    back into the same database because that would allow silent tail rewrites.
    """
    if not isinstance(store, EvidenceStore):
        raise TypeError("Expected evidence store")
    require_utc(created_at_utc)
    if (not isinstance(checkpoint_id, str) or not isinstance(store_id, str)
            or not _ID.fullmatch(checkpoint_id) or not _ID.fullmatch(store_id)):
        raise ValueError("Explicit checkpoint and store identifiers required")
    path = Path(backup_destination)
    total, tip = backup_verified(store, path)
    return EvidenceCheckpoint(checkpoint_id, store_id, created_at_utc,
                              total, tip, file_sha256(path))


def verify_backup_against_pinned(
    backup_path: str | Path, approved_checkpoint: EvidenceCheckpoint,
    *, expected_store_id: str,
) -> tuple[int, str]:
    """Only accepts an independently supplied/pinned checkpoint (not self read)."""
    if not isinstance(approved_checkpoint, EvidenceCheckpoint):
        raise TypeError("Independently pinned EvidenceCheckpoint required")
    if not isinstance(expected_store_id, str) or expected_store_id != approved_checkpoint.store_id:
        raise EvidenceCorrupt("Pinned checkpoint references a different store")
    if file_sha256(backup_path) != approved_checkpoint.backup_sha256:
        raise EvidenceCorrupt("Backup differs from independently pinned file checksum")
    result = EvidenceStore(backup_path).verify()
    if result != (approved_checkpoint.record_count, approved_checkpoint.chain_tip_sha256):
        raise EvidenceCorrupt("Backup chain differs from independent checkpoint")
    return result


def restore_from_pinned(
    backup_path: str | Path, destination: str | Path,
    approved_checkpoint: EvidenceCheckpoint, *, expected_store_id: str,
) -> EvidenceStore:
    """Restore only a verified pinned backup; never overwrite an existing file."""
    verify_backup_against_pinned(
        backup_path, approved_checkpoint, expected_store_id=expected_store_id
    )
    restored = restore_verified(backup_path, destination)
    if restored.verify() != (
        approved_checkpoint.record_count, approved_checkpoint.chain_tip_sha256
    ):
        raise EvidenceCorrupt("Restored chain differs from the pinned checkpoint")
    if file_sha256(restored.path) != approved_checkpoint.backup_sha256:
        raise EvidenceCorrupt("Restored file checksum differs from independently pinned copy")
    return restored


def verify_history_prefix(
    store: EvidenceStore, approved_checkpoint: EvidenceCheckpoint,
    *, expected_store_id: str,
) -> tuple[int, str]:
    """Ensure current valid chain still includes a separately pinned old tip.

    New records may extend the chain. This does not certify the unpinned
    suffix, whose own independent checkpoint is still required.
    """
    if not isinstance(approved_checkpoint, EvidenceCheckpoint):
        raise TypeError("Expected independently pinned checkpoint")
    if approved_checkpoint.store_id != expected_store_id:
        raise EvidenceCorrupt("Store identity mismatch")
    # Check the full chain and pinned prefix IN ONE read snapshot. Separate
    # connections would create a read/write TOCTOU gap.
    with closing(store.connection()) as conn:
        conn.execute("BEGIN")
        try:
            size, tip = store._verify_conn(conn)
            if size < approved_checkpoint.record_count:
                raise EvidenceCorrupt("Current chain truncated below pinned record count")
            if approved_checkpoint.record_count == 0:
                old_tip = ZERO
            else:
                row = conn.execute(
                    "SELECT chained FROM rows ORDER BY seq LIMIT 1 OFFSET ?",
                    (approved_checkpoint.record_count - 1,)
                ).fetchone()
                if row is None:
                    raise EvidenceCorrupt("Pinned row not found")
                old_tip = row["chained"]
            if old_tip != approved_checkpoint.chain_tip_sha256:
                raise EvidenceCorrupt("Pinned historical chain prefix was rewritten")
            return size, tip
        finally:
            conn.execute("ROLLBACK")
