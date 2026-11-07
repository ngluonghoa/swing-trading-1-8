"""Engineering manifest and non-operational release/rollback safeguards."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import tomllib
import unittest

import swing_trading
from swing_trading.engineering_release import (
    EngineeringChangeReview, EngineeringSnapshot, compare_engineering_snapshots,
)

T0 = datetime(2026, 11, 8, 0, 0, tzinfo=timezone.utc)


def snapshot(**overrides) -> EngineeringSnapshot:
    values = dict(
        code_git_sha="a" * 40,
        package_version="0.0.1",
        dependency_lock_sha256="b" * 64,
        module_contracts_sha256="c" * 64,
        documentation_sha256="d" * 64,
        ci_run_ref="github_actions:TEST_ONLY",
        captured_at_utc=T0,
    )
    values.update(overrides)
    return EngineeringSnapshot(**values)


class VersionAndReleaseContractTests(unittest.TestCase):
    def test_package_version_matches_build_metadata(self):
        pyproject = tomllib.loads(
            (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
        )
        self.assertEqual(pyproject["project"]["version"], swing_trading.__version__)

    def test_identity_is_stable_and_canonical(self):
        self.assertEqual(snapshot().canonical_json(), snapshot().canonical_json())
        self.assertEqual(snapshot().fingerprint_sha256, snapshot().fingerprint_sha256)
        self.assertRegex(snapshot().fingerprint_sha256, r"^[0-9a-f]{64}$")
        self.assertNotIn(" ", snapshot().canonical_json())

    def test_contract_revision_changes_identity(self):
        self.assertNotEqual(snapshot().fingerprint_sha256,
                            snapshot(module_contracts_sha256="e" * 64).fingerprint_sha256)

    def test_code_sha_changes_identity(self):
        self.assertNotEqual(snapshot().fingerprint_sha256,
                            snapshot(code_git_sha="f" * 40).fingerprint_sha256)

    def test_document_revision_changes_identity(self):
        self.assertNotEqual(snapshot().fingerprint_sha256,
                            snapshot(documentation_sha256="f" * 64).fingerprint_sha256)

    def test_dependency_revision_changes_identity(self):
        self.assertNotEqual(snapshot().fingerprint_sha256,
                            snapshot(dependency_lock_sha256="f" * 64).fingerprint_sha256)

    def test_manifest_rejects_unpinned_commit(self):
        for value in ("main", "", "x" * 40, "a" * 39, "A" * 40):
            with self.subTest(value=value), self.assertRaises(ValueError):
                snapshot(code_git_sha=value)

    def test_manifest_rejects_unpinned_dependencies(self):
        with self.assertRaises(ValueError):
            snapshot(dependency_lock_sha256="not-a-hash")

    def test_manifest_rejects_invalid_semver(self):
        for value in ("v0.0.1", "0.1", "01.0.0", "0.0.1+custom"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                snapshot(package_version=value)

    def test_manifest_rejects_naive_and_non_utc_clocks(self):
        with self.assertRaises(ValueError):
            snapshot(captured_at_utc=datetime(2026, 11, 8))
        with self.assertRaises(ValueError):
            snapshot(captured_at_utc=T0.astimezone(timezone(timedelta(hours=7))))

    def test_no_false_release_or_lkg_claim(self):
        for field in ("signed_release", "independently_approved_lkg",
                      "licensed_market_data_authorized", "deployment_authorized",
                      "trading_authorized"):
            with self.subTest(field=field), self.assertRaises(PermissionError):
                snapshot(**{field: True})
        with self.assertRaises(PermissionError):
            snapshot(state="RELEASED")

    def test_replacement_release_field_cannot_upgrade_authority(self):
        with self.assertRaises(PermissionError):
            replace(snapshot(), trading_authorized=True)

    def test_bad_ci_reference_rejected(self):
        for value in ("", "https://secret.example/?token=xyz", "bad ref"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                snapshot(ci_run_ref=value)

    def test_identical_build_has_empty_diff(self):
        diff = compare_engineering_snapshots(snapshot(), snapshot())
        self.assertTrue(diff.exact_identity)
        self.assertEqual(diff.changed_fields, ())
        self.assertFalse(diff.operational_rollback_approved)

    def test_changed_contract_requires_requalification(self):
        diff = compare_engineering_snapshots(
            snapshot(), snapshot(module_contracts_sha256="e" * 64)
        )
        self.assertFalse(diff.exact_identity)
        self.assertTrue(diff.schema_or_contract_requalification_required)
        self.assertEqual(diff.changed_fields, ("module_contracts_sha256",))

    def test_changed_dependency_lock_requires_requalification(self):
        diff = compare_engineering_snapshots(
            snapshot(), snapshot(dependency_lock_sha256="e" * 64)
        )
        self.assertTrue(diff.schema_or_contract_requalification_required)

    def test_changed_document_requires_resync(self):
        diff = compare_engineering_snapshots(
            snapshot(), snapshot(documentation_sha256="e" * 64)
        )
        self.assertTrue(diff.documentation_sync_required)
        self.assertFalse(diff.schema_or_contract_requalification_required)

    def test_review_cannot_approve_rollback(self):
        with self.assertRaises(PermissionError):
            EngineeringChangeReview((), False, False, True, operational_rollback_approved=True)

    def test_untyped_review_inputs_rejected(self):
        with self.assertRaises(TypeError):
            compare_engineering_snapshots(snapshot(), {})


if __name__ == "__main__":
    unittest.main()
