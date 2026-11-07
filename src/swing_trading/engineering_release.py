"""Immutable engineering build identity; never an operational release authority.

A successful CI run or matching SHA proves neither data entitlements nor
performance/OOS, production LKG approval, or readiness to deploy/execute orders.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from hashlib import sha256
import json
import re

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_VERSION = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")


@dataclass(frozen=True)
class EngineeringSnapshot:
    """Exact input/version identity for audit and hypothetical rollback review."""

    code_git_sha: str
    package_version: str
    dependency_lock_sha256: str
    module_contracts_sha256: str
    documentation_sha256: str
    ci_run_ref: str
    captured_at_utc: datetime
    state: str = "ENGINEERING_ONLY"
    signed_release: bool = False
    independently_approved_lkg: bool = False
    licensed_market_data_authorized: bool = False
    deployment_authorized: bool = False
    trading_authorized: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.code_git_sha, str) or not _SHA40.fullmatch(self.code_git_sha):
            raise ValueError("Exact lowercase Git commit SHA required")
        if not isinstance(self.package_version, str) or not _VERSION.fullmatch(self.package_version):
            raise ValueError("Explicit MAJOR.MINOR.PATCH package version required")
        for field in ("dependency_lock_sha256", "module_contracts_sha256", "documentation_sha256"):
            value = getattr(self, field)
            if not isinstance(value, str) or not _SHA64.fullmatch(value):
                raise ValueError("Pinned SHA-256 required: " + field)
        if not isinstance(self.ci_run_ref, str) or not _REF.fullmatch(self.ci_run_ref):
            raise ValueError("Nonsecret CI run reference required")
        clock = self.captured_at_utc
        if not isinstance(clock, datetime) or clock.tzinfo is None or clock.utcoffset() != timedelta(0):
            raise ValueError("Captured time must be timezone-aware UTC")
        if (self.state != "ENGINEERING_ONLY" or self.signed_release is not False
                or self.independently_approved_lkg is not False
                or self.licensed_market_data_authorized is not False
                or self.deployment_authorized is not False
                or self.trading_authorized is not False):
            raise PermissionError("Engineering identity cannot certify release or market authority")

    def canonical_json(self) -> str:
        fields = asdict(self)
        fields["captured_at_utc"] = self.captured_at_utc.isoformat(timespec="microseconds")
        return json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    @property
    def fingerprint_sha256(self) -> str:
        return sha256(self.canonical_json().encode("ascii")).hexdigest()


@dataclass(frozen=True)
class EngineeringChangeReview:
    """A deterministic diff, not a claim that a migration or rollback is safe."""

    changed_fields: tuple[str, ...]
    schema_or_contract_requalification_required: bool
    documentation_sync_required: bool
    exact_identity: bool
    operational_rollback_approved: bool = False

    def __post_init__(self) -> None:
        if self.operational_rollback_approved is not False:
            raise PermissionError("Preview cannot approve a runtime rollback")


def compare_engineering_snapshots(
    current: EngineeringSnapshot, proposed: EngineeringSnapshot
) -> EngineeringChangeReview:
    if not isinstance(current, EngineeringSnapshot) or not isinstance(proposed, EngineeringSnapshot):
        raise TypeError("Typed build snapshots required")
    fields = (
        "code_git_sha", "package_version", "dependency_lock_sha256",
        "module_contracts_sha256", "documentation_sha256", "ci_run_ref",
        "captured_at_utc",
    )
    changed = tuple(field for field in fields if getattr(current, field) != getattr(proposed, field))
    return EngineeringChangeReview(
        changed_fields=changed,
        schema_or_contract_requalification_required=bool(
            {"package_version", "dependency_lock_sha256", "module_contracts_sha256"} & set(changed)
        ),
        documentation_sync_required="documentation_sha256" in changed,
        exact_identity=not changed,
    )
