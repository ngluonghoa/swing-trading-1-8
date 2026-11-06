"""Synthetic engineering artifacts/state identities; no source quotes or releases."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256

from swing_trading.release_manifest import (
    ArtifactPin, Component, ComponentPin, EngineeringReleaseManifest, MaterialKind,
    PinnedEngineeringBundle, StateKind, StateReader,
)
from swing_trading.rollback_preflight import RetainedStateMetadata, RetainedStatePin

T0 = datetime(2026, 11, 7, tzinfo=timezone.utc)


def digest(text):
    return sha256(text.encode()).hexdigest()


UI = digest("SYNTHETIC_LOCKED_UI_SPEC")
SCHEMAS = {kind: digest("synthetic-schema-" + kind.value) for kind in StateKind}


def manifest(number=1, *, rollback=None, component_overrides=None, reader_overrides=None):
    components = []
    for kind in Component:
        content = SCHEMAS[StateKind.MARKET_DATA] if kind is Component.DATA_SCHEMA else (
            UI if kind is Component.UI_TEMPLATE else digest("synthetic-component-" + kind.value))
        pin = ComponentPin(kind, "UI-1.0" if kind is Component.UI_TEMPLATE else "0.0.1",
                           content, MaterialKind.DESIGN_SPEC if kind in (
                               Component.RULE_SET, Component.PARAMETER_SET, Component.UI_TEMPLATE,
                               Component.DATA_SCHEMA, Component.MARKET_CALENDAR, Component.CACHE_FORMAT
                           ) else MaterialKind.SOURCE)
        components.append((component_overrides or {}).get(kind, pin))
    readers = tuple(StateReader(k, (reader_overrides or {}).get(k, (SCHEMAS[k],))) for k in StateKind)
    blob = f"SYNTHETIC_ENGINEERING_ARTIFACT_{number}".encode()
    result = EngineeringReleaseManifest(
        f"REL-ENGCAND{number:04d}", f"1.8.0-dev.{number}", f"{number:040x}",
        T0 + timedelta(minutes=number),
        ArtifactPin(f"ARTF-ENGCAND{number:04d}", sha256(blob).hexdigest(), len(blob)),
        tuple(components), readers, digest("recipe"), digest("dependency-spec"),
        digest("synthetic-test-suite"), rollback,
    )
    return result, blob


def bundle(m, blob):
    return PinnedEngineeringBundle(m.canonical_bytes(), blob, m.manifest_sha256())


def retained(current, *, schema_overrides=None):
    return RetainedStateMetadata(
        T0 + timedelta(minutes=3),
        tuple(RetainedStatePin(kind, (schema_overrides or {}).get(kind, SCHEMAS[kind]),
                               digest("LATEST_RETAINED_" + kind.value)) for kind in StateKind),
        current.cache_namespace_sha256(),
    )
