"""GĐ4/P0.27 — nonsecret independent-review packet and revocation HOLD replay.

This is a checklist/triage contract, NOT an independent identity check,
provider signature verifier, immutable event ledger, licensing grant, or a live
access-control service. Claimed attestation roles NEVER authorize data access.
Revocation/expiry can only block; no event/API to clear a hold or grant rights.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re

from .native_minute_bar_source_plan import BarProduct, describe_bar_product
from .provider_rights_review import (
    UnverifiedRightsClaim, EvidenceKind, RightsScope,
    review_unverified_source_claims,
)
from .replay import require_utc

_EVID = re.compile(r"^EVID-[A-Z0-9]{8,32}$")
_ACTOR = re.compile(r"^ACTR-[A-Z0-9]{8,32}$")
_ATTESTATION = re.compile(r"^ATST-[A-Z0-9]{8,32}$")
_EVENT = re.compile(r"^HOLD-[A-Z0-9]{8,32}$")


class ReviewRole(str, Enum):
    PROVIDER_ENTITLEMENT = "PROVIDER_ENTITLEMENT"
    INDEPENDENT_COMPLIANCE = "INDEPENDENT_COMPLIANCE"
    STORAGE_SECURITY = "STORAGE_SECURITY"


class HoldKind(str, Enum):
    PROVIDER_REVOCATION_CLAIM = "PROVIDER_REVOCATION_CLAIM"
    EXPIRED_TERMS_NOTICE = "EXPIRED_TERMS_NOTICE"
    SECURITY_SUSPENSION = "SECURITY_SUSPENSION"


class PacketState(str, Enum):
    EVIDENCE_INCOMPLETE = "EVIDENCE_INCOMPLETE"
    READY_FOR_EXTERNAL_REVIEW_ONLY = "READY_FOR_EXTERNAL_REVIEW_ONLY"
    BLOCKED_EXPIRED = "BLOCKED_EXPIRED"
    BLOCKED_HOLD = "BLOCKED_HOLD"


@dataclass(frozen=True)
class ClaimedReviewAttestation:
    """A non-sensitive claimed role marker, NOT authentic proof of signer."""
    product: BarProduct
    evidence_id: str
    attestation_id: str
    role: ReviewRole
    opaque_actor_ref: str
    recorded_at_utc: datetime

    def __post_init__(self):
        describe_bar_product(self.product)
        if not isinstance(self.evidence_id, str) or not _EVID.fullmatch(self.evidence_id):
            raise ValueError("Only an opaque referenced EVID docket is allowed")
        if not isinstance(self.attestation_id, str) or not _ATTESTATION.fullmatch(
            self.attestation_id
        ):
            raise ValueError("Only opaque ATST token is allowed")
        if not isinstance(self.role, ReviewRole):
            raise TypeError("A typed review role is required")
        if not isinstance(self.opaque_actor_ref, str) or not _ACTOR.fullmatch(
            self.opaque_actor_ref
        ):
            raise ValueError("No names, account IDs, email addresses or credentials")
        require_utc(self.recorded_at_utc)

    @property
    def identity_independently_verified(self):
        return False

    @property
    def signature_verified(self):
        return False


@dataclass(frozen=True)
class UnverifiedHoldNotice:
    """Recorded restriction notice, not proof of vendor source authenticity."""
    product: BarProduct
    evidence_id: str
    event_id: str
    kind: HoldKind
    effective_at_utc: datetime
    observed_at_utc: datetime

    def __post_init__(self):
        describe_bar_product(self.product)
        if not isinstance(self.evidence_id, str) or not _EVID.fullmatch(self.evidence_id):
            raise ValueError("Hold target requires an opaque evidence ID")
        if not isinstance(self.event_id, str) or not _EVENT.fullmatch(self.event_id):
            raise ValueError("Hold notice requires opaque HOLD event ID")
        if not isinstance(self.kind, HoldKind):
            raise TypeError("Typed hold kind required")
        require_utc(self.effective_at_utc)
        require_utc(self.observed_at_utc)
        if self.effective_at_utc > self.observed_at_utc:
            raise ValueError("Cannot know about a future-effective notice before observation")


@dataclass(frozen=True)
class IndependentReviewPacket:
    product: BarProduct
    reviewed_at_utc: datetime
    state: PacketState
    evidence_ids: tuple[str, ...]
    claimed_roles_present: tuple[ReviewRole, ...]
    missing_review_roles: tuple[ReviewRole, ...]
    unverified_scope_claims: tuple[RightsScope, ...]
    missing_scope_claims: tuple[RightsScope, ...]
    missing_expiry_ids: tuple[str, ...]
    expired_evidence_ids: tuple[str, ...]
    held_evidence_ids: tuple[str, ...]
    outstanding: tuple[str, ...]

    @property
    def prepared_for_external_review(self):
        return self.state is PacketState.READY_FOR_EXTERNAL_REVIEW_ONLY

    @property
    def external_identity_or_signature_verified(self):
        return False

    @property
    def provider_entitlement_verified(self):
        return False

    @property
    def permission_to_read(self):
        return False

    @property
    def permission_to_store_raw_or_derived(self):
        return False

    @property
    def real_backtest_allowed(self):
        return False

    @property
    def production_authorized(self):
        return False

    @property
    def actionable(self):
        return False


def assemble_independent_review_packet(
    product: BarProduct,
    claims: tuple[UnverifiedRightsClaim, ...],
    attestation_claims: tuple[ClaimedReviewAttestation, ...],
    holds: tuple[UnverifiedHoldNotice, ...],
    *,
    reviewed_at_utc: datetime,
) -> IndependentReviewPacket:
    """Deterministic as-of triage, keeping every entitlement gate CLOSED.

    Caller supplies the *complete* event history. No source is authenticated;
    omitted/corrupted events could alter the displayed checklist, so this is
    not a revocation enforcement engine or a tamper-evident revocation ledger.
    """
    describe_bar_product(product)
    require_utc(reviewed_at_utc)
    if not isinstance(claims, tuple) or not isinstance(attestation_claims, tuple) or not isinstance(holds, tuple):
        raise TypeError("Claims, attestations and hold events require tuples")
    if len(attestation_claims) > 32 or len(holds) > 128:
        raise ValueError("Review history exceeds bounded in-memory limits")
    if any(not isinstance(a, ClaimedReviewAttestation) for a in attestation_claims):
        raise TypeError("Only typed claimed attestations allowed")
    if any(not isinstance(h, UnverifiedHoldNotice) for h in holds):
        raise TypeError("Only typed hold events allowed")

    base = review_unverified_source_claims(
        product, claims, reviewed_at_utc=reviewed_at_utc
    )
    by_evidence = {c.evidence_id: c for c in claims}
    if len({a.attestation_id for a in attestation_claims}) != len(attestation_claims):
        raise ValueError("Duplicate attestation ID")
    if len({h.event_id for h in holds}) != len(holds):
        raise ValueError("Duplicate hold event ID")

    # Pseudonym uniqueness is a *claimed* separation-of-duties check;
    # it is NOT independently checked against a real identity registry.
    actor_roles = {}
    for a in attestation_claims:
        if a.product is not product or a.evidence_id not in by_evidence:
            raise ValueError("Cross-product or unknown attestation evidence")
        source_claim = by_evidence[a.evidence_id]
        if source_claim.kind is EvidenceKind.PUBLIC_PRODUCT_DOCUMENTATION:
            raise ValueError("A public product page cannot attest account permissions")
        if not source_claim.recorded_at_utc <= a.recorded_at_utc <= reviewed_at_utc:
            raise ValueError("Attestation time is before source claim or after cutoff")
        if a.opaque_actor_ref in actor_roles and actor_roles[a.opaque_actor_ref] is not a.role:
            raise ValueError("Claimed dual-role actor violates role separation")
        actor_roles[a.opaque_actor_ref] = a.role

    for h in holds:
        if h.product is not product or h.evidence_id not in by_evidence:
            raise ValueError("Cross-product or unknown hold notice")
        if (h.observed_at_utc > reviewed_at_utc
                or h.observed_at_utc < by_evidence[h.evidence_id].recorded_at_utc):
            raise ValueError("Hold notice cannot be future-known or predate evidence")

    # Any hold is a global fail-closed stop for this product packet, including
    # notices on an expired/partial evidence reference. No release event exists.
    held = tuple(sorted({h.evidence_id for h in holds}))
    missing_expiry = tuple(sorted(c.evidence_id for c in claims
        if c.kind is not EvidenceKind.PUBLIC_PRODUCT_DOCUMENTATION
        and c.claimed_expiry_utc is None))
    role_set = {a.role for a in attestation_claims}
    present_roles = tuple(r for r in ReviewRole if r in role_set)
    missing_roles = tuple(r for r in ReviewRole if r not in role_set)
    expired = base.expired_claims

    if held:
        state = PacketState.BLOCKED_HOLD
    elif expired:
        state = PacketState.BLOCKED_EXPIRED
    elif (not claims or base.missing_scope_claims
          or missing_roles or missing_expiry):
        state = PacketState.EVIDENCE_INCOMPLETE
    else:
        state = PacketState.READY_FOR_EXTERNAL_REVIEW_ONLY

    blockers = [
        "VENDOR_ACCOUNT_AND_AGREEMENT_AUTHENTICITY_NOT_VERIFIED",
        "REVIEWER_IDENTITY_ROLE_AND_SIGNATURE_NOT_VERIFIED",
        "SIGNED_APPROVAL_OR_TAMPER_EVIDENT_LEDGER_NOT_DEPLOYED",
        "SOURCE_ACCESS_AND_OHLCV_RETENTION_NOT_AUTHORIZED",
        "LIVE_M1_M5_M15_AND_HISTORICAL_BT_OOS_NOT_READY",
    ]
    if held:
        blockers += [
            "REVIEW_PACKET_HELD_NO_REINSTATEMENT",
            "OUTSTANDING_CACHE_ACCESS_BLOCK_AND_RETENTION_PURGE_AUDIT",
        ]
    if expired:
        blockers.append("EXPIRED_EVIDENCE_REQUIRES_NEW_PROVIDER_REVIEW")
    if missing_expiry:
        blockers.append("EVIDENCE_EXPIRY_WINDOW_MISSING")
    if missing_roles:
        blockers.append("CLAIMED_REVIEW_ROLES_INCOMPLETE")
    if base.missing_scope_claims:
        blockers.append("RIGHTS_CLAIMS_INCOMPLETE")

    return IndependentReviewPacket(
        product, reviewed_at_utc, state,
        base.evidence_ids_seen, present_roles, missing_roles,
        base.claimed_scopes_unverified, base.missing_scope_claims,
        missing_expiry, expired, held, tuple(blockers),
    )


def require_independently_authorized_packet(packet: IndependentReviewPacket):
    """No production trust root exists in P0.27, including READY packets."""
    if not isinstance(packet, IndependentReviewPacket):
        raise TypeError("Typed independent review packet required")
    raise PermissionError(
        "P0.27 cannot independently validate vendor rights or reviewer identity"
    )
