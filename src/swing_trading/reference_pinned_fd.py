"""GĐ4/P0.20 — pinned read-only POSIX file descriptor boundary.

Uses dirfd + O_NOFOLLOW for path traversal and opens the actual file inode.
Reduces path-swap races for *this inspection*, NOT for sqlite3.connect(path):
SQLite itself may reopen path/sidecars, so this DOES NOT approve live use.
No file content is ingested, no database is written or repaired.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import stat

from .reference_storage_preflight import UnsafeReferenceStorage, _absolute

_SIDECARS = ("-wal", "-shm", "-journal")
_HEADER = b"SQLite format 3\x00"


@dataclass(frozen=True)
class _Bound:
    parent_fd: int
    name: str
    fd: int
    device: int
    inode: int


@dataclass(frozen=True)
class PinnedReferenceInspection:
    """Only valid while the owning context manager keeps all FDs open."""
    database_fd: int
    sidecar_fds: tuple[tuple[str, int], ...]
    _directories: tuple[_Bound, ...]
    _files: tuple[_Bound, ...]
    _missing_sidecars: tuple[str, ...]
    _last_directory_fd: int
    local_permissions_pass: bool = True

    @property
    def production_authorized(self) -> bool:
        return False

    def verify_path_names(self):
        """Detect swaps since the FDs were pinned; not atomic with later opens."""
        for item in (*self._directories, *self._files):
            try:
                named = os.stat(item.name, dir_fd=item.parent_fd,
                                follow_symlinks=False)
                opened = os.fstat(item.fd)
            except OSError as exc:
                raise UnsafeReferenceStorage("Pinned path became unavailable") from exc
            if ((named.st_dev, named.st_ino) != (item.device, item.inode)
                    or (opened.st_dev, opened.st_ino) != (item.device, item.inode)):
                raise UnsafeReferenceStorage("Pinned pathname/inode has changed")
        for name in self._missing_sidecars:
            try:
                os.stat(name, dir_fd=self._last_directory_fd,
                        follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise UnsafeReferenceStorage("SQLite sidecar appeared after inspection")
        for item in self._directories:
            try:
                os.stat(".git", dir_fd=item.fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise UnsafeReferenceStorage("Git repository marker appeared")
        return True


def _owner_mode(fd, *, uid, kind, mode):
    info = os.fstat(fd)
    if (info.st_uid != uid or stat.S_IMODE(info.st_mode) != mode
            or (not stat.S_ISDIR(info.st_mode) if kind == "dir"
                else not stat.S_ISREG(info.st_mode))):
        raise UnsafeReferenceStorage("Incorrect POSIX type/UID/mode: " + kind)
    if kind == "file" and info.st_nlink != 1:
        raise UnsafeReferenceStorage("Multiple hard links to SQLite file")
    return info


@contextmanager
def pin_reference_sqlite_files(root, database, *, expected_uid=None):
    """Inspect a journal without trusting later pathname lookups.

    Caller MUST NOT use these FDs to assert that arbitrary sqlite3.connect()
    calls are race-free. The pinned DB/WAL may be concurrently modified by a
    writer, so raw-byte reads also are NOT consistent SQLite snapshots.
    """
    root, database = _absolute(root), _absolute(database)
    if root == Path("/"):
        raise ValueError("Private root cannot be filesystem root")
    try:
        relative = database.relative_to(root)
    except ValueError as exc:
        raise ValueError("SQLite path must be under private root") from exc
    if not relative.parts or relative.name in ("", ".", ".."):
        raise ValueError("Concrete SQLite filename required")
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise OSError("POSIX nofollow directory FD semantics required")
    uid = os.getuid() if expected_uid is None else expected_uid
    if type(uid) is not int or uid < 0:
        raise ValueError("Explicit expected POSIX UID required")
    flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    held = []
    directories = []
    files = []
    missing = []
    try:
        base = os.open("/", flags | os.O_DIRECTORY)
        held.append(base)
        parent = base
        segments = database.parts[1:-1]
        private_depth = len(root.parts) - 1
        for i, segment in enumerate(segments):
            opened = os.open(segment, flags | os.O_DIRECTORY, dir_fd=parent)
            held.append(opened)
            if i >= private_depth - 1:
                _owner_mode(opened, uid=uid, kind="dir", mode=0o700)
            info = os.fstat(opened)
            directories.append(_Bound(parent, segment, opened,
                                      info.st_dev, info.st_ino))
            parent = opened
            try:
                os.stat(".git", dir_fd=opened, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise UnsafeReferenceStorage("SQLite cannot live under Git tree")

        names = [database.name] + [database.name + suffix for suffix in _SIDECARS]
        for idx, name in enumerate(names):
            try:
                opened = os.open(name, flags, dir_fd=parent)
            except FileNotFoundError:
                if idx == 0:
                    raise UnsafeReferenceStorage("SQLite database missing")
                missing.append(name)
                continue
            held.append(opened)
            info = _owner_mode(opened, uid=uid, kind="file", mode=0o600)
            files.append(_Bound(parent, name, opened, info.st_dev, info.st_ino))
            if idx == 0 and os.pread(opened, 16, 0) != _HEADER:
                raise UnsafeReferenceStorage("SQLite database header invalid")
        if not files or files[0].name != database.name:
            raise UnsafeReferenceStorage("SQLite database not safely pinned")
        snapshot = PinnedReferenceInspection(
            files[0].fd,
            tuple((item.name.removeprefix(database.name), item.fd) for item in files[1:]),
            tuple(directories), tuple(files), tuple(missing), parent
        )
        snapshot.verify_path_names()
        yield snapshot
    except OSError as exc:
        if isinstance(exc, UnsafeReferenceStorage):
            raise
        raise UnsafeReferenceStorage("POSIX nofollow/openat inspection refused") from exc
    finally:
        for fd in reversed(held):
            os.close(fd)
