"""P0.4: checked backup and restore for local SQLite evidence files.

Backup uses SQLite's online snapshot API, not a live .db file copy.
A new destination is atomically published on a POSIX filesystem; never
overwrite existing evidence. This is not geographic disaster recovery.
"""
from contextlib import closing
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile

from .durable_evidence import EvidenceCorrupt, EvidenceStore


def _temp(destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, filename = tempfile.mkstemp(
        prefix=".swing-audit-", suffix=".tmp", dir=destination.parent
    )
    os.close(fd)
    os.chmod(filename, 0o600)
    return Path(filename)


def _publish(temp: Path, destination: Path) -> None:
    # Hard link creates one visible, complete file or raises FileExistsError.
    # It does not silently overwrite another process's output.
    os.link(temp, destination)
    directory = os.open(str(destination.parent), os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def backup_verified(source: EvidenceStore, destination: str | Path):
    """Backup a consistent SQLite snapshot, then verify before publishing."""
    if not isinstance(source, EvidenceStore):
        raise TypeError("Expected evidence store")
    dest = Path(destination).expanduser().absolute()
    if dest.exists():
        raise FileExistsError(dest)
    before = source.verify()
    temporary = _temp(dest)
    try:
        with closing(source.connection()) as origin, closing(
            sqlite3.connect(temporary)
        ) as backup:
            origin.backup(backup)
        after = EvidenceStore(temporary).verify()
        if before != after:
            raise EvidenceCorrupt("Backup chain changed between verification and snapshot")
        with temporary.open("rb") as file:
            os.fsync(file.fileno())
        _publish(temporary, dest)
        return after
    finally:
        temporary.unlink(missing_ok=True)


def restore_verified(backup: str | Path, destination: str | Path) -> EvidenceStore:
    """Restore to a NEW location with round-trip checksum and chain checks."""
    src = EvidenceStore(backup)
    expected = src.verify()
    dest = Path(destination).expanduser().absolute()
    if dest.exists():
        raise FileExistsError(dest)
    temporary = _temp(dest)
    try:
        with src.path.open("rb") as origin, temporary.open("wb") as target:
            shutil.copyfileobj(origin, target)
            target.flush()
            os.fsync(target.fileno())
        if EvidenceStore(temporary).verify() != expected:
            raise EvidenceCorrupt("Restored evidence differs from verified backup")
        _publish(temporary, dest)
        return EvidenceStore(dest)
    finally:
        temporary.unlink(missing_ok=True)
