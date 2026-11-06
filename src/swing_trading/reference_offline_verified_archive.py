"""GĐ4/P0.21 — signed, descriptor-pinned OFFLINE METADATA archive verification.

No sqlite3.connect(path) calls. A signed P0.18 metadata-only SQLite backup
is read from an O_NOFOLLOW-pinned inode and validated in SQLite :memory:
with its whole-file SHA256, immutable journal chain and an empty quote cache.

This is NOT a coherent live SQLite/WAL reader, backup scheduler, host approval,
production secure VFS, source entitlement, B5 backtest or trading permission.
"""
from contextlib import closing
from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
import sqlite3

from .reference_checkpoint_signature import (
    DetachedJournalSignature, verify_detached_journal_signature,
)
from .reference_journal import ReferenceJournal, ReferenceJournalCorrupt
from .reference_journal_recovery import JournalCheckpoint
from .reference_pinned_fd import pin_reference_sqlite_files
from .reference_storage_preflight import UnsafeReferenceStorage

_MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
_CHUNK = 1024 * 1024


@dataclass(frozen=True)
class OfflineMetadataReport:
    """Diagnostic result only, not a security attestation or market-data feed."""
    checkpoint_id: str
    store_id: str
    journal_records: int
    chain_tip_sha256: str
    archive_sha256: str
    archive_size_bytes: int

    @property
    def signed_manifest_checked(self) -> bool:
        return True

    @property
    def metadata_only(self) -> bool:
        return True

    @property
    def production_authorized(self) -> bool:
        return False

    @property
    def market_data_certified(self) -> bool:
        return False

    @property
    def historical_backtest_qualified(self) -> bool:
        return False

    @property
    def actionable(self) -> bool:
        return False


def verify_offline_signed_metadata_archive(
    root: str | Path,
    archive: str | Path,
    checkpoint: JournalCheckpoint,
    signature: DetachedJournalSignature,
    *,
    public_key_raw: bytes,
    expected_public_key_sha256: str,
    expected_key_id: str,
    expected_store_id: str,
    expected_uid: int | None = None,
    max_archive_bytes: int = _MAX_ARCHIVE_BYTES,
) -> OfflineMetadataReport:
    """Read a signed, standalone P0.18 backup with pinned POSIX file FDs.

    The public key AND expected fingerprint must come from a separately
    authenticated source, not from the archive or GitHub fixture. Checks
    are deliberately *before* file access. This is offline archive
    verification only; original live SQLite/WAL must NOT be used here.
    """
    verify_detached_journal_signature(
        checkpoint, signature,
        public_key_raw=public_key_raw,
        expected_public_key_sha256=expected_public_key_sha256,
        expected_key_id=expected_key_id, expected_store_id=expected_store_id,
    )
    if (type(max_archive_bytes) is not int
            or not 4096 <= max_archive_bytes <= _MAX_ARCHIVE_BYTES):
        raise ValueError("Archive size limit must be explicit and <=64MiB")
    with pin_reference_sqlite_files(root, archive, expected_uid=expected_uid) as pin:
        if pin.sidecar_fds:
            raise UnsafeReferenceStorage(
                "Offline metadata backup must be standalone: no SQLite sidecars"
            )
        # P0.18 publishes a standalone rollback-journal-mode SQLite file.
        # A WAL-mode main DB (header bytes 18/19 = 2) may lack committed
        # transactions without sidecars: rejecting absent-sidecar WAL is vital.
        if os.pread(pin.database_fd, 2, 18) != b"\x01\x01":
            raise UnsafeReferenceStorage(
                "Offline archive must use standalone rollback SQLite journal mode"
            )
        file_info = os.fstat(pin.database_fd)
        size = file_info.st_size
        if not 4096 <= size <= max_archive_bytes:
            raise UnsafeReferenceStorage("Metadata archive is empty or exceeds bound")
        digest = sha256()
        chunks = []
        offset = 0
        while offset < size:
            chunk = os.pread(pin.database_fd, min(_CHUNK, size-offset), offset)
            if not chunk:
                raise ReferenceJournalCorrupt("Pinned archive truncated during read")
            chunks.append(chunk)
            digest.update(chunk)
            offset += len(chunk)
        if (os.fstat(pin.database_fd).st_size != size
                or digest.hexdigest() != checkpoint.backup_sha256):
            raise ReferenceJournalCorrupt("Pinned archive SHA256/size mismatch")
        pin.verify_path_names()
        raw = b"".join(chunks)
        # Never connect by pathname. Only deserialize the fully signed bytes
        # into a disposable in-memory SQLite database.
        with closing(sqlite3.connect(":memory:", isolation_level=None)) as db:
            db.row_factory = sqlite3.Row
            if not hasattr(db, "deserialize"):
                raise RuntimeError("SQLite deserialize unavailable; fail closed")
            try:
                db.deserialize(raw)
                db.execute("PRAGMA query_only=ON")
                db.execute("BEGIN")
                try:
                    count, tip = ReferenceJournal._verify(db)
                    cache_count = db.execute(
                        "SELECT count(*) FROM cache"
                    ).fetchone()[0]
                    if cache_count != 0:
                        raise ReferenceJournalCorrupt(
                            "Offline archive carries prohibited SSI/DNSE quote cache"
                        )
                    if (count != checkpoint.record_count
                            or tip != checkpoint.chain_tip_sha256):
                        raise ReferenceJournalCorrupt(
                            "Signed journal record count or chain tip mismatch"
                        )
                finally:
                    db.execute("ROLLBACK")
            except sqlite3.Error as exc:
                raise ReferenceJournalCorrupt(
                    "Offline in-memory SQLite archive validation failed"
                ) from exc
        # Check names once more; any change during deserialization is refused.
        pin.verify_path_names()
        return OfflineMetadataReport(
            checkpoint.checkpoint_id, checkpoint.store_id,
            count, tip, digest.hexdigest(), size,
        )
