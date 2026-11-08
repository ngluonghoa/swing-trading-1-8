"""H3-C1 POSIX pinned-FD exception and cleanup regression guards.

Synthetic local SQLite fixture ONLY. These tests do not authorize a
production filesystem, cloud cache, vendor source, or trading use.
"""
import errno
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from swing_trading.reference_journal import ReferenceJournal
from swing_trading.reference_pinned_fd import pin_reference_sqlite_files
from swing_trading.reference_storage_preflight import UnsafeReferenceStorage


@unittest.skipUnless(
    hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY"),
    "POSIX directory-FD + O_NOFOLLOW required",
)
class PinnedFdExceptionBoundaryTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "private"
        self.root.mkdir(mode=0o700)
        self.database = self.root / "fixture.sqlite"
        ReferenceJournal(self.database).initialize()
        os.chmod(self.database, 0o600)

    @staticmethod
    def _stat_failure(name, error):
        original_stat = os.stat

        def guarded_stat(path, *args, **kwargs):
            if path == name:
                raise error
            return original_stat(path, *args, **kwargs)

        return guarded_stat

    def test_only_genuinely_absent_sidecars_are_allowed(self):
        with pin_reference_sqlite_files(self.root, self.database) as pinned:
            self.assertEqual(pinned.sidecar_fds, ())
            self.assertTrue(pinned.verify_path_names())
            self.assertFalse(pinned.production_authorized)

    def test_each_new_sidecar_symlink_is_rejected(self):
        for suffix in ("-wal", "-shm", "-journal"):
            with self.subTest(suffix=suffix):
                sidecar = Path(str(self.database) + suffix)
                with pin_reference_sqlite_files(self.root, self.database) as pinned:
                    sidecar.symlink_to(self.database)
                    try:
                        with self.assertRaisesRegex(
                            UnsafeReferenceStorage, "sidecar appeared"
                        ):
                            pinned.verify_path_names()
                    finally:
                        sidecar.unlink()

    def test_new_git_marker_is_rejected(self):
        with pin_reference_sqlite_files(self.root, self.database) as pinned:
            marker = self.root / ".git"
            marker.mkdir()
            with self.assertRaisesRegex(
                UnsafeReferenceStorage, "Git repository marker appeared"
            ):
                pinned.verify_path_names()

    def test_missing_sidecar_permission_error_is_not_silenced(self):
        name = self.database.name + "-wal"
        denied = PermissionError(errno.EACCES, "synthetic permission denied", name)
        with pin_reference_sqlite_files(self.root, self.database) as pinned:
            with patch(
                "swing_trading.reference_pinned_fd.os.stat",
                side_effect=self._stat_failure(name, denied),
            ):
                with self.assertRaises(PermissionError) as caught:
                    pinned.verify_path_names()
        self.assertIs(caught.exception, denied)

    def test_missing_sidecar_io_error_is_not_silenced(self):
        name = self.database.name + "-shm"
        failed = OSError(errno.EIO, "synthetic I/O failure", name)
        with pin_reference_sqlite_files(self.root, self.database) as pinned:
            with patch(
                "swing_trading.reference_pinned_fd.os.stat",
                side_effect=self._stat_failure(name, failed),
            ):
                with self.assertRaises(OSError) as caught:
                    pinned.verify_path_names()
        self.assertIs(caught.exception, failed)

    def test_git_marker_permission_error_is_not_silenced(self):
        denied = PermissionError(errno.EACCES, "synthetic marker denied", ".git")
        with pin_reference_sqlite_files(self.root, self.database) as pinned:
            with patch(
                "swing_trading.reference_pinned_fd.os.stat",
                side_effect=self._stat_failure(".git", denied),
            ):
                with self.assertRaises(PermissionError) as caught:
                    pinned.verify_path_names()
        self.assertIs(caught.exception, denied)

    def test_pinned_database_stat_errors_are_wrapped_fail_closed(self):
        denied = PermissionError(errno.EACCES, "synthetic DB denied")
        with pin_reference_sqlite_files(self.root, self.database) as pinned:
            with patch(
                "swing_trading.reference_pinned_fd.os.stat",
                side_effect=self._stat_failure(self.database.name, denied),
            ):
                with self.assertRaisesRegex(
                    UnsafeReferenceStorage, "Pinned path became unavailable"
                ) as caught:
                    pinned.verify_path_names()
        self.assertIs(caught.exception.__cause__, denied)

    def test_sidecar_open_permission_error_is_wrapped_fail_closed(self):
        original_open = os.open
        name = self.database.name + "-journal"
        denied = PermissionError(errno.EACCES, "synthetic open denied", name)

        def guarded_open(path, *args, **kwargs):
            if path == name:
                raise denied
            return original_open(path, *args, **kwargs)

        with patch(
            "swing_trading.reference_pinned_fd.os.open",
            side_effect=guarded_open,
        ):
            with self.assertRaisesRegex(
                UnsafeReferenceStorage, "POSIX nofollow/openat inspection refused"
            ) as caught:
                with pin_reference_sqlite_files(self.root, self.database):
                    self.fail("Unsafe sidecar open must not yield an inspection")
        self.assertIs(caught.exception.__cause__, denied)

    def test_descriptor_lifetime_is_scoped_and_never_authorizes_production(self):
        with pin_reference_sqlite_files(self.root, self.database) as pinned:
            database_fd = pinned.database_fd
            self.assertEqual(
                os.pread(database_fd, 16, 0), b"SQLite format 3\x00"
            )
            self.assertFalse(pinned.production_authorized)
        with self.assertRaises(OSError) as closed:
            os.fstat(database_fd)
        self.assertEqual(closed.exception.errno, errno.EBADF)


if __name__ == "__main__":
    unittest.main()
