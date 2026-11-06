"""REL-F1 synthetic artifact integrity/strict wire-format security regressions."""
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta, timezone
from hashlib import sha256
import json
import unittest

from release_fixtures import T0, UI, SCHEMAS, bundle, digest, manifest
from swing_trading.release_manifest import (
    ArtifactPin, Component, ComponentPin, EngineeringReleaseManifest, ManifestRejected,
    MaterialKind, MAX_ARTIFACT_BYTES, MAX_MANIFEST_BYTES, PinnedEngineeringBundle,
    StateKind, StateReader, canonical_json, verify_engineering_bundle,
)


class ReleaseManifestTests(unittest.TestCase):
    def setUp(self):
        self.manifest, self.blob = manifest()

    def parse(self, value):
        return EngineeringReleaseManifest.from_canonical_bytes(value)

    def test_canonical_roundtrip_is_exact_and_deterministic(self):
        raw = self.manifest.canonical_bytes()
        self.assertEqual(self.parse(raw), self.manifest)
        self.assertEqual(self.parse(raw).canonical_bytes(), raw)
        self.assertEqual(self.parse(raw).manifest_sha256(), self.manifest.manifest_sha256())
        self.assertEqual(json.loads(raw)["scope"], "ENGINEERING_CANDIDATE")

    def test_verified_bundle_binds_exact_manifest_and_artifact(self):
        self.assertEqual(verify_engineering_bundle(bundle(self.manifest, self.blob)), self.manifest)

    def test_artifact_bit_tamper_rejected_at_same_size(self):
        tampered = bytes([self.blob[0] ^ 1]) + self.blob[1:]
        with self.assertRaises(ManifestRejected):
            verify_engineering_bundle(bundle(self.manifest, tampered))

    def test_artifact_length_mismatch_rejected_even_with_matching_content_hash(self):
        m = replace(self.manifest, artifact=replace(self.manifest.artifact,
                                                   byte_length=len(self.blob) + 1))
        with self.assertRaises(ManifestRejected):
            verify_engineering_bundle(bundle(m, self.blob))

    def test_manifest_changed_with_original_external_pin_rejected(self):
        changed = replace(self.manifest, source_revision="a" * 40)
        b = PinnedEngineeringBundle(changed.canonical_bytes(), self.blob,
                                    self.manifest.manifest_sha256())
        with self.assertRaises(ManifestRejected):
            verify_engineering_bundle(b)

    def test_entire_manifest_and_artifact_substitution_still_needs_original_pin(self):
        other, blob = manifest(2)
        b = PinnedEngineeringBundle(other.canonical_bytes(), blob, self.manifest.manifest_sha256())
        with self.assertRaises(ManifestRejected):
            verify_engineering_bundle(b)

    def test_each_component_fingerprint_invalidates_namespace_even_with_same_version(self):
        original = self.manifest.cache_namespace_sha256()
        for kind in Component:
            with self.subTest(kind=kind):
                pins = tuple(replace(p, content_sha256=digest("changed-" + kind.value))
                             if p.component is kind else p for p in self.manifest.components)
                readers = self.manifest.state_readers
                if kind is Component.DATA_SCHEMA:
                    readers = tuple(replace(r, schema_sha256s=(digest("changed-" + kind.value),))
                                    if r.state_kind is StateKind.MARKET_DATA else r for r in readers)
                changed = replace(self.manifest, components=pins, state_readers=readers)
                self.assertNotEqual(changed.cache_namespace_sha256(), original)

    def test_release_recipe_dependencies_and_test_identity_are_bound(self):
        for field in ("build_recipe_sha256", "dependency_spec_sha256", "test_suite_sha256"):
            with self.subTest(field=field):
                changed = replace(self.manifest, **{field: digest("changed")})
                self.assertNotEqual(changed.manifest_sha256(), self.manifest.manifest_sha256())
                self.assertNotEqual(changed.cache_namespace_sha256(), self.manifest.cache_namespace_sha256())

    def test_missing_duplicate_or_reordered_component_registry_rejected(self):
        pins = self.manifest.components
        for bad in (pins[:-1], pins + (pins[0],), (pins[0],) * 8, tuple(reversed(pins))):
            with self.subTest(bad=bad), self.assertRaises(ManifestRejected):
                replace(self.manifest, components=bad)

    def test_untyped_or_mutable_component_registry_rejected(self):
        for bad in (list(self.manifest.components), tuple({} for _ in Component)):
            with self.assertRaises(ManifestRejected):
                replace(self.manifest, components=bad)

    def test_moving_source_ref_and_noncanonical_hashes_rejected(self):
        for ref in ("main", "feature/branch", "A" * 40, "0" * 39, "https://example.invalid/commit"):
            with self.subTest(ref=ref), self.assertRaises(ManifestRejected):
                replace(self.manifest, source_revision=ref)
        for bad in ("a" * 63, "A" * 64, "0" * 64, "sha256:" + "a" * 64):
            with self.assertRaises(ManifestRejected):
                replace(self.manifest.artifact, content_sha256=bad)

    def test_semver_identity_accepts_valid_prerelease_and_build(self):
        for version in ("0.0.1", "1.8.0-dev.12", "1.8.0-rc.1+build.01", "1.8.0-alpha-x"):
            with self.subTest(version=version):
                self.assertEqual(replace(self.manifest, release_version=version).release_version, version)

    def test_semver_rejects_ambiguous_versions(self):
        for bad in ("01.8.0", "1.08.0", "1.8", "v1.8.0", "1.8.0-01", "1.8.0-rc..1",
                    "1.8.0+", "1.8.0 dev", "1.8.0/../../", "1.8.0-" + "a" * 100):
            with self.subTest(bad=bad), self.assertRaises(ManifestRejected):
                replace(self.manifest, release_version=bad)

    def test_locked_ui_cannot_change_version_or_claim_implemented_renderer(self):
        pin = self.manifest.component(Component.UI_TEMPLATE)
        for changes in ({"version": "UI-1.1"}, {"material_kind": MaterialKind.SOURCE}):
            with self.assertRaises(ManifestRejected):
                replace(pin, **changes)

    def test_all_four_state_readers_required_without_silent_default(self):
        r = self.manifest.state_readers
        for bad in (r[:-1], tuple(reversed(r)), (r[0],) * 4, list(r)):
            with self.assertRaises(ManifestRejected):
                replace(self.manifest, state_readers=bad)

    def test_own_market_schema_must_be_explicitly_readable(self):
        readers = tuple(replace(r, schema_sha256s=(digest("unknown"),))
                        if r.state_kind is StateKind.MARKET_DATA else r for r in self.manifest.state_readers)
        with self.assertRaises(ManifestRejected):
            replace(self.manifest, state_readers=readers)

    def test_schema_reader_rejects_wildcard_duplicate_and_unbounded_lists(self):
        for bad in ((), ("*",), ("a" * 64, "a" * 64), tuple(digest(str(i)) for i in range(17)),
                    ["a" * 64], ("b" * 64, "a" * 64)):
            with self.assertRaises(ManifestRejected):
                StateReader(StateKind.CUSTODY_FLOOR, bad)

    def test_artifact_size_rejects_bool_empty_and_oversized(self):
        for size in (True, 0, -1, 1.0, MAX_ARTIFACT_BYTES + 1):
            with self.assertRaises(ManifestRejected):
                replace(self.manifest.artifact, byte_length=size)

    def test_ids_versions_reject_path_url_and_free_text(self):
        for bad in ("../release", "https://example.invalid/token", "account=123", "REL-abcdefgh"):
            with self.assertRaises(ManifestRejected):
                replace(self.manifest, release_id=bad)
        with self.assertRaises(ManifestRejected):
            replace(self.manifest.component(Component.ENGINE), version="token=secret")

    def test_wire_rejects_whitespace_bom_and_reordered_keys(self):
        raw = self.manifest.canonical_bytes()
        data = json.loads(raw)
        for bad in (raw + b"\n", b" " + raw, b"\xef\xbb\xbf" + raw,
                    json.dumps(data, indent=2).encode(),
                    json.dumps(dict(reversed(list(data.items()))), separators=(",", ":")).encode()):
            with self.assertRaises(ManifestRejected):
                self.parse(bad)

    def test_duplicate_nested_or_root_json_keys_rejected(self):
        raw = self.manifest.canonical_bytes()
        for bad in (b'{"scope":"ACTIVE",' + raw[1:],
                    raw.replace(b'"byte_length":', b'"byte_length":1,"byte_length":', 1)):
            with self.assertRaises(ManifestRejected):
                self.parse(bad)

    def test_scope_promotion_and_unknown_approval_fields_rejected(self):
        for key, value in (("scope", "PRODUCTION"), ("scope", "ACTIVE"), ("approved", True),
                           ("approved_at_utc", "2026-11-07T00:00:00Z"), ("format", "v2")):
            data = json.loads(self.manifest.canonical_bytes())
            data[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ManifestRejected):
                self.parse(canonical_json(data))

    def test_unknown_nested_fields_are_not_ignored(self):
        data = json.loads(self.manifest.canonical_bytes())
        data["artifact"]["uri"] = "https://example.invalid/token"
        with self.assertRaises(ManifestRejected):
            self.parse(canonical_json(data))

    def test_invalid_numbers_types_and_missing_keys_rejected(self):
        for bad in (True, "123", 1.5, None):
            data = json.loads(self.manifest.canonical_bytes())
            data["artifact"]["byte_length"] = bad
            with self.assertRaises(ManifestRejected):
                self.parse(canonical_json(data))
        data.pop("state_readers")
        with self.assertRaises(ManifestRejected):
            self.parse(canonical_json(data))
        with self.assertRaises(ManifestRejected):
            self.parse(self.manifest.canonical_bytes().replace(b'"byte_length":', b'"byte_length":NaN,"x":', 1))

    def test_manifest_input_is_bounded_immutable_and_ascii(self):
        for bad in (b"", b"x" * (MAX_MANIFEST_BYTES + 1), b"\xff", bytearray(self.manifest.canonical_bytes()),
                    b"[]", b"null", b'{"x":' + b"[" * 1100 + b"0" + b"]" * 1100 + b"}"):
            with self.assertRaises(ManifestRejected):
                self.parse(bad)

    def test_utc_and_wire_time_must_be_canonical(self):
        for bad in (T0.replace(tzinfo=None), T0.astimezone(timezone(timedelta(hours=7)))):
            with self.assertRaises(ValueError):
                replace(self.manifest, created_at_utc=bad)
        data = json.loads(self.manifest.canonical_bytes())
        data["created_at_utc"] = "2026-11-07T00:01:00Z"
        with self.assertRaises(ManifestRejected):
            self.parse(canonical_json(data))

    def test_bundle_requires_immutable_bounded_payloads(self):
        for blob in (b"", bytearray(self.blob), b"x" * (MAX_ARTIFACT_BYTES + 1)):
            with self.assertRaises(ManifestRejected):
                bundle(self.manifest, blob)
        with self.assertRaises(TypeError):
            verify_engineering_bundle({"manifest_bytes": self.manifest.canonical_bytes()})

    def test_schema_and_hash_rejections_do_not_echo_payload(self):
        sentinel = "SYNTHETIC_PRIVATE_SENTINEL"
        data = json.loads(self.manifest.canonical_bytes())
        data["approval_secret"] = sentinel
        with self.assertRaises(ManifestRejected) as cm:
            self.parse(canonical_json(data))
        self.assertNotIn(sentinel, str(cm.exception))
        self.assertNotIn(self.blob.decode(), repr(bundle(self.manifest, self.blob)))

    def test_metadata_is_frozen_without_approval_promotion_fields(self):
        with self.assertRaises(FrozenInstanceError):
            self.manifest.release_version = "1.8.0"
        with self.assertRaises(TypeError):
            replace(self.manifest, approved=True)


if __name__ == "__main__":
    unittest.main()
