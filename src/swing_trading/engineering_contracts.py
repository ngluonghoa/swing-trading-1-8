"""Engineering-only, versioned structural contracts for replaceable module ports.

This module checks an implementation's declared interface without invoking it.
Structural compatibility is NOT proof of source authorization, market-data
equivalence, operational safety, or permission to release a trading system.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

_CONTRACT = re.compile(r"^[a-z][a-z0-9_.-]{0,79}$")
_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SCOPE = re.compile(r"^[A-Z][A-Z0-9_]{0,31}$")
_VERSION = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def _semantic_version(version: str) -> tuple[int, int, int]:
    if not isinstance(version, str) or not _VERSION.fullmatch(version):
        raise ValueError("Explicit MAJOR.MINOR.PATCH contract version required")
    return tuple(int(piece) for piece in version.split("."))


@dataclass(frozen=True)
class PortDescriptor:
    """Public interface promise; scope identifies one isolated data authority."""

    contract_id: str
    version: str
    scope: str
    operations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.contract_id, str) or not _CONTRACT.fullmatch(self.contract_id):
            raise ValueError("Invalid contract ID")
        _semantic_version(self.version)
        if not isinstance(self.scope, str) or not _SCOPE.fullmatch(self.scope):
            raise ValueError("Invalid source or namespace scope")
        if not isinstance(self.operations, tuple) or not self.operations:
            raise TypeError("Nonempty immutable operations tuple required")
        if (any(not isinstance(item, str) or not _NAME.fullmatch(item)
                for item in self.operations)
                or len(set(self.operations)) != len(self.operations)):
            raise ValueError("Operations must be unique public method identifiers")


@dataclass(frozen=True)
class PortCompatibility:
    """Structural check only; never an authorization or deployed release receipt."""

    compatible: bool
    reasons: tuple[str, ...]
    structural_only: bool = True
    live_data_authorized: bool = False
    deploy_authorized: bool = False
    trading_authorized: bool = False

    def __post_init__(self) -> None:
        if (self.structural_only is not True or self.live_data_authorized is not False
                or self.deploy_authorized is not False or self.trading_authorized is not False):
            raise PermissionError("Port compatibility cannot grant production privileges")
        if type(self.compatible) is not bool or not isinstance(self.reasons, tuple):
            raise TypeError("Typed compatibility report required")
        if self.compatible == bool(self.reasons):
            raise ValueError("Compatible iff there are no incompatibility reasons")


def check_port(
    required: PortDescriptor, supplied: PortDescriptor, implementation: object
) -> PortCompatibility:
    """Check explicit contract identity/version/scope and callable operations.

    A higher minor version may satisfy an older minor within the SAME major;
    patch revisions do not remove operations. No cross-provider automatic
    substitution: caller must deliberately select matching source scope.
    Semantic behavior must also pass consumer-driven tests, independently.
    """
    if not isinstance(required, PortDescriptor) or not isinstance(supplied, PortDescriptor):
        raise TypeError("Typed PortDescriptor values required")
    reasons: list[str] = []
    if required.contract_id != supplied.contract_id:
        reasons.append("CONTRACT_ID_MISMATCH")
    rm, rminor, rpatch = _semantic_version(required.version)
    sm, sminor, spatch = _semantic_version(supplied.version)
    if rm != sm or (sminor, spatch) < (rminor, rpatch):
        reasons.append("INCOMPATIBLE_CONTRACT_VERSION")
    if required.scope != supplied.scope:
        reasons.append("SCOPE_MISMATCH_NO_IMPLICIT_PROVIDER_FALLBACK")
    for operation in required.operations:
        if operation not in supplied.operations:
            reasons.append("UNDECLARED_OPERATION:" + operation)
        elif not callable(getattr(implementation, operation, None)):
            reasons.append("MISSING_CALLABLE:" + operation)
    return PortCompatibility(not reasons, tuple(reasons))


def require_compatible_port(
    required: PortDescriptor, supplied: PortDescriptor, implementation: object
) -> None:
    """Fail closed before dependency injection. Does not execute the adapter."""
    result = check_port(required, supplied, implementation)
    if not result.compatible:
        raise ValueError("; ".join(result.reasons))
