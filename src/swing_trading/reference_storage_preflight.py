"""GĐ4/P0.19 — read-only POSIX preflight for one SSI/DNSE reference SQLite store.

Never changes ACLs or approves a runtime. A successful local permission check is
NOT licence approval, filesystem encryption, durable volume certification,
TOCTOU protection, remote mount proof, or production authorization.
"""
from dataclasses import dataclass
import os
from pathlib import Path
import stat


class UnsafeReferenceStorage(PermissionError):
    """The requested local path failed one or more fail-closed checks."""


def _absolute(path):
    p = Path(path).expanduser()
    if not p.is_absolute() or ".." in p.parts:
        raise ValueError("Explicit absolute path without '..' required")
    return p


@dataclass(frozen=True)
class StoragePreflight:
    root: Path
    database: Path
    expected_uid: int
    issues: tuple[str, ...]
    host_volume_approved: bool = False
    provider_retention_approved: bool = False
    production_authorized: bool = False

    @property
    def local_permissions_pass(self) -> bool:
        return not self.issues

    def require_local_permissions(self):
        if self.issues:
            raise UnsafeReferenceStorage("; ".join(self.issues))
        return self


def inspect_reference_storage(root, database, *, expected_uid=None):
    """Inspect existing path + SQLite sidecars without creating/fixing anything.

    POSIX-only engineering preflight. Caller supplies root and concrete DB path.
    Every path segment must be symlink-free; directory modes from root down
    must be 0700 and files 0600, owner-UID exact, link count 1.
    Protected volume/ACL/SELinux/Windows policy require external verification.
    """
    root = _absolute(root)
    database = _absolute(database)
    if root == Path("/"):
        raise ValueError("Filesystem root cannot be an approved private directory")
    try:
        rel = database.relative_to(root)
    except ValueError as exc:
        raise ValueError("Database must be inside declared private root") from exc
    if rel == Path(".") or len(rel.parts) < 1:
        raise ValueError("Expected a concrete SQLite file within the root")
    if expected_uid is None:
        if not hasattr(os, "getuid"):
            raise OSError("POSIX uid checks unavailable on this host")
        expected_uid = os.getuid()
    if type(expected_uid) is not int or expected_uid < 0:
        raise ValueError("Expected POSIX UID must be explicit nonnegative int")
    issues = []

    # Don't normalize symlinks with resolve(): symbolic path hops are a
    # security finding, even if they eventually resolve into the same root.
    chain = list(reversed(root.parents)) + [root]
    chain += [root / Path(*rel.parts[:i]) for i in range(1, len(rel.parts))]
    for i, directory in enumerate(chain):
        try:
            info = directory.lstat()
        except FileNotFoundError:
            issues.append("MISSING_DIRECTORY:" + str(directory))
            continue
        if stat.S_ISLNK(info.st_mode):
            issues.append("SYMLINK_DIRECTORY:" + str(directory))
            continue
        if not stat.S_ISDIR(info.st_mode):
            issues.append("NON_DIRECTORY:" + str(directory))
            continue
        # Parent directories above the declared private root need not have
        # 0700 (e.g. system /tmp), but must not redirect via symlinks.
        if i >= len(root.parents):
            if info.st_uid != expected_uid:
                issues.append("OWNER_DIRECTORY:" + str(directory))
            if stat.S_IMODE(info.st_mode) != 0o700:
                issues.append("MODE_DIRECTORY:" + str(directory))
            if (directory / ".git").exists() or (directory / ".git").is_symlink():
                issues.append("INSIDE_GIT_TREE:" + str(directory))
    # Check any repo marker above the private root too, without marking
    # ordinary system parents as invalid by their broad directory modes.
    for directory in root.parents:
        if (directory / ".git").exists() or (directory / ".git").is_symlink():
            issues.append("INSIDE_GIT_TREE:" + str(directory))

    def check_file(path, *, mandatory):
        try:
            info = path.lstat()
        except FileNotFoundError:
            if mandatory:
                issues.append("MISSING_FILE:" + str(path))
            return
        if stat.S_ISLNK(info.st_mode):
            issues.append("SYMLINK_FILE:" + str(path))
            return
        if not stat.S_ISREG(info.st_mode):
            issues.append("NON_REGULAR_FILE:" + str(path))
            return
        if info.st_uid != expected_uid:
            issues.append("OWNER_FILE:" + str(path))
        if stat.S_IMODE(info.st_mode) != 0o600:
            issues.append("MODE_FILE:" + str(path))
        if info.st_nlink != 1:
            issues.append("HARDLINK_FILE:" + str(path))

    check_file(database, mandatory=True)
    for suffix in ("-wal", "-shm", "-journal"):
        check_file(Path(str(database) + suffix), mandatory=False)
    # All tuple members are diagnostic paths/codes, not data content.
    return StoragePreflight(root, database, expected_uid, tuple(issues))


def require_reference_storage(root, database, *, expected_uid=None):
    """Fail closed on local permissions; never elevate to production."""
    return inspect_reference_storage(
        root, database, expected_uid=expected_uid
    ).require_local_permissions()
