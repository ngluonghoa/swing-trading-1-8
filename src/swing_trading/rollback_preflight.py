"""REL-F1: pure engineering rollback planning; never switch a live version.

No file/DB/network access, state restore, cache purge, active pointer, migration,
provider permission, approval or claim that a production stable release exists.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from hashlib import sha256

from .release_manifest import (
    Component, ComponentPin, StateKind, ManifestRejected, canonical_json, require_sha256,
    utc_text, verify_engineering_bundle,
)


@dataclass(frozen=True)
class RetainedStatePin:
    state_kind: StateKind
    schema_sha256: str
    snapshot_sha256: str

    def __post_init__(self):
        if type(self.state_kind) is not StateKind:
            raise TypeError("Typed protected state kind required")
        require_sha256(self.schema_sha256)
        require_sha256(self.snapshot_sha256)


@dataclass(frozen=True)
class RetainedStateMetadata:
    observed_at_utc: datetime
    states: tuple[RetainedStatePin, ...]
    current_cache_namespace_sha256: str

    def __post_init__(self):
        utc_text(self.observed_at_utc)
        if (type(self.states) is not tuple
                or any(type(p) is not RetainedStatePin for p in self.states)
                or tuple(p.state_kind for p in self.states) != tuple(StateKind)):
            raise ManifestRejected("All four retained states in canonical order required")
        for pin in self.states:
            pin.__post_init__()
        require_sha256(self.current_cache_namespace_sha256)

    def metadata_sha256(self):
        return sha256(b"SwingTrading1.8/RetainedRollbackState/v1\x00" + canonical_json({
            "observed_at_utc": utc_text(self.observed_at_utc),
            "states": [{"state_kind": p.state_kind.value, "schema_sha256": p.schema_sha256,
                        "snapshot_sha256": p.snapshot_sha256} for p in self.states],
            "current_cache_namespace_sha256": self.current_cache_namespace_sha256,
        })).hexdigest()


class RollbackBlocker(str, Enum):
    TARGET_NOT_PINNED = "TARGET_NOT_PINNED"
    SAME_RELEASE_ID = "SAME_RELEASE_ID"
    INVALID_CHRONOLOGY = "INVALID_CHRONOLOGY"
    LOCKED_UI_MISMATCH = "LOCKED_UI_MISMATCH"
    CACHE_NAMESPACE_MISMATCH = "CACHE_NAMESPACE_MISMATCH"
    CURRENT_STATE_UNREADABLE = "CURRENT_STATE_UNREADABLE"
    TARGET_STATE_UNREADABLE = "TARGET_STATE_UNREADABLE"


@dataclass(frozen=True)
class RollbackFinding:
    blocker: RollbackBlocker
    state_kind: StateKind | None = None


@dataclass(frozen=True)
class EngineeringRollbackPlan:
    current_release_id: str
    target_release_id: str
    current_manifest_sha256: str
    target_manifest_sha256: str
    retained_metadata_sha256: str
    preserve_states: tuple[RetainedStatePin, ...]
    target_component_pins: tuple[ComponentPin, ...]
    target_cache_namespace_sha256: str
    cache_rebuild_required: bool
    checked_at_utc: datetime
    findings: tuple[RollbackFinding, ...]

    @property
    def disposition(self):
        return "BLOCKED" if self.findings else "METADATA_COMPATIBLE_REVIEW_REQUIRED"


def plan_engineering_rollback(
    current_bundle, target_bundle, retained_state, *, expected_retained_metadata_sha256,
    locked_ui_spec_sha256, checked_at_utc,
) -> EngineeringRollbackPlan:
    """Inspect supplied pinned bytes and schema declarations, never execute.

    Pinned metadata is not proof of real host freshness, rights or schema-reader
    behavior. All production approval, migration, position reconciliation and
    actual rollback/recovery acceptance remain outside this engineering plan.
    """
    if type(retained_state) is not RetainedStateMetadata:
        raise TypeError("Exact retained-state metadata required")
    retained_state.__post_init__()
    require_sha256(expected_retained_metadata_sha256)
    require_sha256(locked_ui_spec_sha256)
    utc_text(checked_at_utc)
    retained_digest = retained_state.metadata_sha256()
    if retained_digest != expected_retained_metadata_sha256:
        raise ManifestRejected("Retained state differs from separately supplied metadata pin")
    current = verify_engineering_bundle(current_bundle)
    target = verify_engineering_bundle(target_bundle)
    current_digest = current.manifest_sha256()
    target_digest = target.manifest_sha256()
    findings = []
    if current.rollback_target_manifest_sha256 != target_digest:
        findings.append(RollbackFinding(RollbackBlocker.TARGET_NOT_PINNED))
    if current.release_id == target.release_id:
        findings.append(RollbackFinding(RollbackBlocker.SAME_RELEASE_ID))
    if not (target.created_at_utc <= current.created_at_utc
            <= retained_state.observed_at_utc <= checked_at_utc):
        findings.append(RollbackFinding(RollbackBlocker.INVALID_CHRONOLOGY))
    if any(m.component(Component.UI_TEMPLATE).content_sha256 != locked_ui_spec_sha256
           for m in (current, target)):
        findings.append(RollbackFinding(RollbackBlocker.LOCKED_UI_MISMATCH))
    if retained_state.current_cache_namespace_sha256 != current.cache_namespace_sha256():
        findings.append(RollbackFinding(RollbackBlocker.CACHE_NAMESPACE_MISMATCH))
    for pin in retained_state.states:
        if pin.schema_sha256 not in current.reader(pin.state_kind):
            findings.append(RollbackFinding(RollbackBlocker.CURRENT_STATE_UNREADABLE, pin.state_kind))
        if pin.schema_sha256 not in target.reader(pin.state_kind):
            findings.append(RollbackFinding(RollbackBlocker.TARGET_STATE_UNREADABLE, pin.state_kind))
    return EngineeringRollbackPlan(
        current.release_id, target.release_id, current_digest, target_digest,
        retained_digest, retained_state.states, target.components,
        target.cache_namespace_sha256(),
        current.cache_namespace_sha256() != target.cache_namespace_sha256(),
        checked_at_utc, tuple(findings),
    )
