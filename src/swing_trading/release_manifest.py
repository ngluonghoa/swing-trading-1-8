"""REL-F1: bounded engineering artifact/version identity, not release approval.

Pure in-memory metadata and byte verification. No build, signing, file/DB I/O,
promotion, deployment, provider rights or last-known-good production registry.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from hashlib import sha256
import json
import re

from .replay import require_utc

MAX_MANIFEST_BYTES = 64 * 1024
MAX_ARTIFACT_BYTES = 8 * 1024 * 1024
LOCKED_UI_VERSION = "UI-1.0"
_FORMAT = "SwingTrading1.8/EngineeringReleaseManifest/v1"
_DOMAIN = b"SwingTrading1.8/EngineeringReleaseManifest/v1\x00"
_DIGEST = re.compile(r"[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+\-]{0,95}")
_SEMVER = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)


class ManifestRejected(ValueError):
    """Metadata, canonical encoding or pinned artifact identity is invalid."""


class Component(str, Enum):
    ENGINE = "ENGINE"
    RULE_SET = "RULE_SET"
    PARAMETER_SET = "PARAMETER_SET"
    DATA_SCHEMA = "DATA_SCHEMA"
    PROVIDER_ADAPTER = "PROVIDER_ADAPTER"
    MARKET_CALENDAR = "MARKET_CALENDAR"
    CACHE_FORMAT = "CACHE_FORMAT"
    UI_TEMPLATE = "UI_TEMPLATE"


class MaterialKind(str, Enum):
    SOURCE = "SOURCE"
    DESIGN_SPEC = "DESIGN_SPEC"
    SYNTHETIC_FIXTURE = "SYNTHETIC_FIXTURE"


class StateKind(str, Enum):
    MARKET_DATA = "MARKET_DATA"
    AUDIT_HISTORY = "AUDIT_HISTORY"
    CUSTODY_FLOOR = "CUSTODY_FLOOR"
    POSITION_CONTEXT = "POSITION_CONTEXT"


def require_sha256(value):
    if type(value) is not str or not _DIGEST.fullmatch(value) or value == "0" * 64:
        raise ManifestRejected("Canonical non-placeholder sha256 hex required")


def utc_text(value):
    if type(value) is not datetime:
        raise TypeError("Exact UTC datetime required")
    require_utc(value)
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def canonical_json(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _identity(value, prefix):
    if type(value) is not str or not re.fullmatch(prefix + r"-[A-Z0-9]{8,32}", value):
        raise ManifestRejected("Opaque engineering artifact/release identity required")


def _keys(value, required):
    if type(value) is not dict or set(value) != set(required):
        raise ManifestRejected("Exact versioned manifest fields required")


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ManifestRejected("Duplicate JSON field")
        result[key] = value
    return result


def _no_constant(_):
    raise ManifestRejected("Non-finite JSON number")


@dataclass(frozen=True)
class ComponentPin:
    component: Component
    version: str
    content_sha256: str
    material_kind: MaterialKind

    def __post_init__(self):
        if type(self.component) is not Component or type(self.material_kind) is not MaterialKind:
            raise TypeError("Typed component and material kind required")
        if type(self.version) is not str or not _VERSION.fullmatch(self.version):
            raise ManifestRejected("Bounded ASCII component version required")
        require_sha256(self.content_sha256)
        if self.component is Component.UI_TEMPLATE and (
            self.version != LOCKED_UI_VERSION or self.material_kind is not MaterialKind.DESIGN_SPEC
        ):
            raise ManifestRejected("UI-1.0 locked design snapshot required; renderer is not accepted")


@dataclass(frozen=True)
class ArtifactPin:
    artifact_id: str
    content_sha256: str
    byte_length: int

    def __post_init__(self):
        _identity(self.artifact_id, "ARTF")
        require_sha256(self.content_sha256)
        if type(self.byte_length) is not int or not 1 <= self.byte_length <= MAX_ARTIFACT_BYTES:
            raise ManifestRejected("Positive bounded engineering artifact size required")


@dataclass(frozen=True)
class StateReader:
    state_kind: StateKind
    schema_sha256s: tuple[str, ...]

    def __post_init__(self):
        if type(self.state_kind) is not StateKind:
            raise TypeError("Typed retained state kind required")
        if type(self.schema_sha256s) is not tuple or not 1 <= len(self.schema_sha256s) <= 16:
            raise ManifestRejected("Bounded immutable exact-schema reader list required")
        for value in self.schema_sha256s:
            require_sha256(value)
        if tuple(sorted(set(self.schema_sha256s))) != self.schema_sha256s:
            raise ManifestRejected("Unique canonical reader fingerprints required")


@dataclass(frozen=True)
class EngineeringReleaseManifest:
    release_id: str
    release_version: str
    source_revision: str
    created_at_utc: datetime
    artifact: ArtifactPin
    components: tuple[ComponentPin, ...]
    state_readers: tuple[StateReader, ...]
    build_recipe_sha256: str
    dependency_spec_sha256: str
    test_suite_sha256: str
    rollback_target_manifest_sha256: str | None = None

    def __post_init__(self):
        _identity(self.release_id, "REL")
        if type(self.release_version) is not str or len(self.release_version) > 96:
            raise ManifestRejected("Bounded SemVer identity required")
        match = _SEMVER.fullmatch(self.release_version)
        if match is None or any(
            s.isdigit() and len(s) > 1 and s[0] == "0"
            for s in (match.group(4) or "").split(".") if s
        ):
            raise ManifestRejected("Canonical SemVer identity required")
        if type(self.source_revision) is not str or not _COMMIT.fullmatch(self.source_revision):
            raise ManifestRejected("Pinned 40-hex source commit required, not a moving branch")
        utc_text(self.created_at_utc)
        if type(self.artifact) is not ArtifactPin:
            raise TypeError("Exact artifact pin required")
        if (type(self.components) is not tuple
                or any(type(p) is not ComponentPin for p in self.components)
                or tuple(p.component for p in self.components) != tuple(Component)):
            raise ManifestRejected("All eight unique component pins in canonical order required")
        if (type(self.state_readers) is not tuple
                or any(type(p) is not StateReader for p in self.state_readers)
                or tuple(p.state_kind for p in self.state_readers) != tuple(StateKind)):
            raise ManifestRejected("Explicit readers for all four protected state kinds required")
        if self.component(Component.DATA_SCHEMA).content_sha256 not in self.reader(StateKind.MARKET_DATA):
            raise ManifestRejected("Manifest must declare its own market data schema readable")
        for value in (self.build_recipe_sha256, self.dependency_spec_sha256, self.test_suite_sha256):
            require_sha256(value)
        if self.rollback_target_manifest_sha256 is not None:
            require_sha256(self.rollback_target_manifest_sha256)

    def component(self, kind):
        return next(p for p in self.components if p.component is kind)

    def reader(self, kind):
        return next(p.schema_sha256s for p in self.state_readers if p.state_kind is kind)

    def canonical_bytes(self):
        return canonical_json({
            "format": _FORMAT, "scope": "ENGINEERING_CANDIDATE",
            "release_id": self.release_id, "release_version": self.release_version,
            "source_revision": self.source_revision,
            "created_at_utc": utc_text(self.created_at_utc),
            "artifact": {"artifact_id": self.artifact.artifact_id,
                         "content_sha256": self.artifact.content_sha256,
                         "byte_length": self.artifact.byte_length},
            "components": [{"component": p.component.value, "version": p.version,
                            "content_sha256": p.content_sha256,
                            "material_kind": p.material_kind.value} for p in self.components],
            "state_readers": [{"state_kind": r.state_kind.value,
                               "schema_sha256s": list(r.schema_sha256s)} for r in self.state_readers],
            "build_recipe_sha256": self.build_recipe_sha256,
            "dependency_spec_sha256": self.dependency_spec_sha256,
            "test_suite_sha256": self.test_suite_sha256,
            "rollback_target_manifest_sha256": self.rollback_target_manifest_sha256,
        })

    def manifest_sha256(self):
        return sha256(_DOMAIN + self.canonical_bytes()).hexdigest()

    def cache_namespace_sha256(self):
        # Release/build + every semantic component is pinned. Old cache contents
        # never become current merely because a previous release is selected.
        return sha256(b"SwingTrading1.8/ReleaseCacheNamespace/v1\x00"
                      + self.canonical_bytes()).hexdigest()

    @classmethod
    def from_canonical_bytes(cls, raw):
        if type(raw) is not bytes or not 1 <= len(raw) <= MAX_MANIFEST_BYTES:
            raise ManifestRejected("Bounded immutable canonical manifest bytes required")
        try:
            data = json.loads(raw.decode("ascii"), object_pairs_hook=_no_duplicates,
                              parse_constant=_no_constant)
            _keys(data, ("format", "scope", "release_id", "release_version", "source_revision",
                         "created_at_utc", "artifact", "components", "state_readers",
                         "build_recipe_sha256", "dependency_spec_sha256", "test_suite_sha256",
                         "rollback_target_manifest_sha256"))
            if data["format"] != _FORMAT or data["scope"] != "ENGINEERING_CANDIDATE":
                raise ManifestRejected("Unsupported format or attempted scope promotion")
            artifact = data["artifact"]
            _keys(artifact, ("artifact_id", "content_sha256", "byte_length"))
            if type(data["components"]) is not list or len(data["components"]) != len(Component):
                raise ManifestRejected("Exact component array required")
            pins = []
            for p in data["components"]:
                _keys(p, ("component", "version", "content_sha256", "material_kind"))
                pins.append(ComponentPin(Component(p["component"]), p["version"],
                                         p["content_sha256"], MaterialKind(p["material_kind"])))
            if type(data["state_readers"]) is not list or len(data["state_readers"]) != len(StateKind):
                raise ManifestRejected("Exact state-reader array required")
            readers = []
            for r in data["state_readers"]:
                _keys(r, ("state_kind", "schema_sha256s"))
                if type(r["schema_sha256s"]) is not list:
                    raise ManifestRejected("Exact schema list required")
                readers.append(StateReader(StateKind(r["state_kind"]), tuple(r["schema_sha256s"])))
            timestamp = data["created_at_utc"]
            if type(timestamp) is not str or len(timestamp) != 27 or not timestamp.endswith("Z"):
                raise ManifestRejected("Canonical microsecond UTC timestamp required")
            result = cls(data["release_id"], data["release_version"], data["source_revision"],
                         datetime.fromisoformat(timestamp.replace("Z", "+00:00")),
                         ArtifactPin(**artifact), tuple(pins), tuple(readers),
                         data["build_recipe_sha256"], data["dependency_spec_sha256"],
                         data["test_suite_sha256"], data["rollback_target_manifest_sha256"])
            if result.canonical_bytes() != raw:
                raise ManifestRejected("Manifest encoding is not canonical")
            return result
        except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
            # Never echo arbitrary manifest fields, credentials or payload bytes.
            raise ManifestRejected("Malformed, noncanonical or unsupported engineering manifest") from None


@dataclass(frozen=True)
class PinnedEngineeringBundle:
    manifest_bytes: bytes = field(repr=False)
    artifact_bytes: bytes = field(repr=False)
    expected_manifest_sha256: str

    def __post_init__(self):
        require_sha256(self.expected_manifest_sha256)
        if type(self.manifest_bytes) is not bytes or not 1 <= len(self.manifest_bytes) <= MAX_MANIFEST_BYTES:
            raise ManifestRejected("Bounded immutable manifest bytes required")
        if type(self.artifact_bytes) is not bytes or not 1 <= len(self.artifact_bytes) <= MAX_ARTIFACT_BYTES:
            raise ManifestRejected("Bounded immutable engineering artifact bytes required")


def verify_engineering_bundle(bundle):
    """Bind bytes to an explicit supplied pin; no ownership or release approval."""
    if type(bundle) is not PinnedEngineeringBundle:
        raise TypeError("Exact pinned engineering bundle required")
    bundle.__post_init__()
    manifest = EngineeringReleaseManifest.from_canonical_bytes(bundle.manifest_bytes)
    if manifest.manifest_sha256() != bundle.expected_manifest_sha256:
        raise ManifestRejected("Engineering manifest differs from separately supplied pin")
    if (len(bundle.artifact_bytes) != manifest.artifact.byte_length
            or sha256(bundle.artifact_bytes).hexdigest() != manifest.artifact.content_sha256):
        raise ManifestRejected("Engineering artifact bytes differ from manifest")
    return manifest
