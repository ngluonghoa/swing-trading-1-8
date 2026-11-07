"""P0.29b: OFFLINE evidence onboarding and monotonic-floor journal *fixture*.

This module never authenticates a vendor, hosts an approved stateful custodian,
receives credentials, proves revocation freshness, writes licensed market data,
or grants access. An independent witness anchor MUST be acquired and protected
OUTSIDE this model; a caller-controlled anchor + journal can both be rolled back.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256
import json
import re

from .provider_head_custody import ClaimedMonotonicFloor, CustodyProduct

_HEX = re.compile(r"^[0-9a-f]{64}$")
_EVID = re.compile(r"^EVID-[A-Z0-9]{8,32}$")
_ACTOR = re.compile(r"^ACTR-[A-Z0-9]{8,32}$")
_GENESIS = "0" * 64
_RECORD_DOMAIN = b"SwingTrading1.8/P0.29b/FixtureFloorRecord/v1\x00"
_MAX_RECORDS = 256


class HostPreflightRejected(ValueError):
    """A fixture, external evidence claim or floor history is malformed."""


def _utc(value: datetime) -> str:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() != timedelta(0)):
        raise HostPreflightRejected("UTC-aware timestamp required")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _hex(value: str, label: str):
    if not isinstance(value, str) or not _HEX.fullmatch(value):
        raise HostPreflightRejected(label + " must be sha256 lowercase hex")


def _id(value: str, pattern: re.Pattern):
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise HostPreflightRejected("Use opaque nonsecret evidence/actor IDs")


class EvidenceRole(str, Enum):
    PROVIDER_KEY_ISSUER = "PROVIDER_KEY_ISSUER"
    INDEPENDENT_HEAD_CUSTODIAN = "INDEPENDENT_HEAD_CUSTODIAN"
    ACCOUNT_RIGHTS_REVIEWER = "ACCOUNT_RIGHTS_REVIEWER"
    INDEPENDENT_FLOOR_WITNESS = "INDEPENDENT_FLOOR_WITNESS"
    STORAGE_SECURITY_REVIEWER = "STORAGE_SECURITY_REVIEWER"
    INCIDENT_REVOCATION_OWNER = "INCIDENT_REVOCATION_OWNER"


class HostControl(str, Enum):
    INDEPENDENT_WITNESS_ANCHOR = "INDEPENDENT_WITNESS_ANCHOR"
    IMMUTABLE_MONOTONIC_COUNTER = "IMMUTABLE_MONOTONIC_COUNTER"
    AUTHENTICATED_VENDOR_KEY_ENROLLMENT = "AUTHENTICATED_VENDOR_KEY_ENROLLMENT"
    ATOMIC_FSYNC_AND_LOCKING = "ATOMIC_FSYNC_AND_LOCKING"
    NO_SYMLINK_OR_REPARSE = "NO_SYMLINK_OR_REPARSE"
    RESTRICTED_ACL_AND_ENCRYPTION = "RESTRICTED_ACL_AND_ENCRYPTION"
    BACKUP_RESTORE_ROLLBACK_CHECK = "BACKUP_RESTORE_ROLLBACK_CHECK"
    CLOCK_AND_REVOCATION_MONITORING = "CLOCK_AND_REVOCATION_MONITORING"
    EMERGENCY_DENY_AND_PURGE = "EMERGENCY_DENY_AND_PURGE"


@dataclass(frozen=True)
class ClaimedExternalEvidence:
    product: CustodyProduct
    role: EvidenceRole
    evidence_id: str
    opaque_actor_id: str
    recorded_at_utc: datetime
    expires_at_utc: datetime

    def __post_init__(self):
        if not isinstance(self.product, CustodyProduct) or not isinstance(self.role, EvidenceRole):
            raise TypeError("Typed source product and reviewer role required")
        _id(self.evidence_id, _EVID)
        _id(self.opaque_actor_id, _ACTOR)
        _utc(self.recorded_at_utc)
        _utc(self.expires_at_utc)
        if self.expires_at_utc <= self.recorded_at_utc:
            raise HostPreflightRejected("Evidence expiry must be after recording")

    @property
    def independently_authenticated(self) -> bool:
        return False


@dataclass(frozen=True)
class ClaimedHostControl:
    control: HostControl
    evidence_id: str
    opaque_actor_id: str
    claimed_present: bool

    def __post_init__(self):
        if not isinstance(self.control, HostControl):
            raise TypeError("Typed host control required")
        _id(self.evidence_id, _EVID)
        _id(self.opaque_actor_id, _ACTOR)
        if type(self.claimed_present) is not bool:
            raise TypeError("Boolean claim required")

    @property
    def verified_on_host(self) -> bool:
        return False


@dataclass(frozen=True)
class ExternalOnboardingReport:
    product: CustodyProduct
    listed_roles: tuple[EvidenceRole, ...]
    claimed_controls_present: tuple[HostControl, ...]
    missing_roles: tuple[EvidenceRole, ...]
    missing_controls: tuple[HostControl, ...]
    state: str = "INDEPENDENT_VERIFICATION_REQUIRED"

    @property
    def vendor_key_origin_verified(self) -> bool:
        return False

    @property
    def fresh_revocation_stream_authenticated(self) -> bool:
        return False

    @property
    def secure_host_approved(self) -> bool:
        return False

    @property
    def rights_to_read_or_cache(self) -> bool:
        return False

    @property
    def trading_actionable(self) -> bool:
        return False


def inspect_external_onboarding(
    product: CustodyProduct,
    evidence: tuple[ClaimedExternalEvidence, ...],
    host_controls: tuple[ClaimedHostControl, ...],
    *, checked_at_utc: datetime,
) -> ExternalOnboardingReport:
    """Checks completeness/separation of claims, NEVER verifies external identity."""
    if not isinstance(product, CustodyProduct) or not isinstance(evidence, tuple) or not isinstance(host_controls, tuple):
        raise TypeError("Explicit typed product and immutable evidence tuples required")
    _utc(checked_at_utc)
    if len(evidence) > len(EvidenceRole) or len(host_controls) > len(HostControl):
        raise HostPreflightRejected("Duplicate or unbounded evidence list")
    seen_roles: set[EvidenceRole] = set()
    used_actors: set[str] = set()
    ids: set[str] = set()
    for claim in evidence:
        if not isinstance(claim, ClaimedExternalEvidence) or claim.product is not product:
            raise HostPreflightRejected("Cross-product or untyped reviewer claim")
        if claim.role in seen_roles or claim.evidence_id in ids or claim.opaque_actor_id in used_actors:
            raise HostPreflightRejected("Independent role, evidence, and actor separation required")
        if claim.recorded_at_utc > checked_at_utc or claim.expires_at_utc <= checked_at_utc:
            raise HostPreflightRejected("Claimed role document not current")
        seen_roles.add(claim.role)
        ids.add(claim.evidence_id)
        used_actors.add(claim.opaque_actor_id)
    seen_controls: set[HostControl] = set()
    present: set[HostControl] = set()
    for claim in host_controls:
        if not isinstance(claim, ClaimedHostControl):
            raise HostPreflightRejected("Untyped host evidence")
        if claim.control in seen_controls or claim.evidence_id in ids:
            raise HostPreflightRejected("Duplicate host control or reused evidence ID")
        # Role actors can perform host controls, but cannot pose as another independent role.
        seen_controls.add(claim.control)
        ids.add(claim.evidence_id)
        if claim.claimed_present:
            present.add(claim.control)
    return ExternalOnboardingReport(
        product,
        tuple(role for role in EvidenceRole if role in seen_roles),
        tuple(c for c in HostControl if c in present),
        tuple(role for role in EvidenceRole if role not in seen_roles),
        tuple(c for c in HostControl if c not in present),
    )


@dataclass(frozen=True)
class FixtureFloorRecord:
    """Content-addressed metadata checkpoint, not a secure or approved state store."""
    product: CustodyProduct
    account_binding_sha256_claim: str
    sequence: int
    tail_sha256: str
    custody_key_sha256: str
    custody_key_id: str
    custody_epoch: int
    last_issued_at_utc: datetime
    observed_at_utc: datetime
    index: int
    previous_record_sha256: str
    record_sha256: str

    def __post_init__(self):
        if not isinstance(self.product, CustodyProduct):
            raise TypeError("Typed provider required")
        _id(self.custody_key_id, re.compile(r"^KEY-[A-Z0-9]{8,32}$"))
        for label, value in (
            ("account", self.account_binding_sha256_claim), ("tail", self.tail_sha256),
            ("custody key", self.custody_key_sha256),
            ("prior record", self.previous_record_sha256), ("record", self.record_sha256),
        ):
            _hex(value, label)
        if (type(self.sequence) is not int or self.sequence < 1
                or type(self.custody_epoch) is not int or self.custody_epoch < 1
                or type(self.index) is not int or self.index < 1):
            raise HostPreflightRejected("Positive, integer sequence/epoch/index required")
        _utc(self.last_issued_at_utc)
        _utc(self.observed_at_utc)
        if self.last_issued_at_utc > self.observed_at_utc:
            raise HostPreflightRejected("Head issued after floor was observed")
        if self.compute_sha256() != self.record_sha256:
            raise HostPreflightRejected("Fixture record digest corrupted")

    def compute_sha256(self) -> str:
        payload = {
            "schema": 1,
            "product": self.product.value,
            "account_binding_sha256_claim": self.account_binding_sha256_claim,
            "sequence": self.sequence,
            "tail_sha256": self.tail_sha256,
            "custody_key_sha256": self.custody_key_sha256,
            "custody_key_id": self.custody_key_id,
            "custody_epoch": self.custody_epoch,
            "last_issued_at_utc": _utc(self.last_issued_at_utc),
            "observed_at_utc": _utc(self.observed_at_utc),
            "index": self.index,
            "previous_record_sha256": self.previous_record_sha256,
        }
        return sha256(_RECORD_DOMAIN + json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        ).encode("ascii")).hexdigest()

    @property
    def host_protected(self) -> bool:
        return False


def append_fixture_floor(
    prior: FixtureFloorRecord | None, floor: ClaimedMonotonicFloor,
) -> FixtureFloorRecord:
    """Build next in-memory fixture record. No key rotation admitted here.

    A rotation requires P0.29a dual-signature verification AND independently
    authenticated custody; this simple journal deliberately cannot enroll one.
    """
    if prior is not None and not isinstance(prior, FixtureFloorRecord):
        raise TypeError("Prior fixture floor type required")
    if not isinstance(floor, ClaimedMonotonicFloor):
        raise TypeError("P0.29a claimed floor type required")
    if prior is not None:
        if floor.product is not prior.product or floor.account_binding_sha256_claim != prior.account_binding_sha256_claim:
            raise HostPreflightRejected("Provider/account substitution across floor history")
        if prior.compute_sha256() != prior.record_sha256:
            raise HostPreflightRejected("Prior record digest was changed")
        if (floor.custody_epoch != prior.custody_epoch
                or floor.custody_key_id != prior.custody_key_id
                or floor.custody_key_sha256 != prior.custody_key_sha256):
            raise HostPreflightRejected("Key rotation needs separate authenticated process")
        if floor.sequence < prior.sequence:
            raise HostPreflightRejected("Sequence rolled back")
        if floor.sequence == prior.sequence and floor.tail_sha256 != prior.tail_sha256:
            raise HostPreflightRejected("Same sequence forked into different tail")
        if floor.last_issued_at_utc < prior.last_issued_at_utc or floor.observed_at_utc <= prior.observed_at_utc:
            raise HostPreflightRejected("Issuance or observation clock rolled back")
        if floor.sequence == prior.sequence and floor.last_issued_at_utc == prior.last_issued_at_utc and floor.observed_at_utc == prior.observed_at_utc:
            raise HostPreflightRejected("No-op duplicate fixture checkpoint")
    kw = dict(
        product=floor.product,
        account_binding_sha256_claim=floor.account_binding_sha256_claim,
        sequence=floor.sequence,
        tail_sha256=floor.tail_sha256,
        custody_key_sha256=floor.custody_key_sha256,
        custody_key_id=floor.custody_key_id,
        custody_epoch=floor.custody_epoch,
        last_issued_at_utc=floor.last_issued_at_utc,
        observed_at_utc=floor.observed_at_utc,
        index=prior.index + 1 if prior else 1,
        previous_record_sha256=prior.record_sha256 if prior else _GENESIS,
    )
    placeholder = FixtureFloorRecord.__new__(FixtureFloorRecord)
    for k,v in kw.items():
        object.__setattr__(placeholder,k,v)
    digest = placeholder.compute_sha256()
    return FixtureFloorRecord(**kw,record_sha256=digest)


@dataclass(frozen=True)
class ClaimedIndependentAnchor:
    product: CustodyProduct
    account_binding_sha256_claim: str
    expected_index: int
    expected_record_sha256: str
    witness_evidence_id: str

    def __post_init__(self):
        if not isinstance(self.product, CustodyProduct):
            raise TypeError("Typed witness product required")
        _hex(self.account_binding_sha256_claim,"witness account")
        _hex(self.expected_record_sha256,"witness record")
        _id(self.witness_evidence_id,_EVID)
        if type(self.expected_index) is not int or self.expected_index < 1:
            raise HostPreflightRejected("Witness index required")

    @property
    def independently_authenticated(self) -> bool:
        return False


@dataclass(frozen=True)
class FixtureFloorInspection:
    product: CustodyProduct
    checkpoint_count: int
    observed_sequence: int
    observed_record_sha256: str
    anchor_digest_matches_claim: bool
    state: str = "CONDITIONAL_FIXTURE_ONLY"

    @property
    def trusted_monotonic_across_restarts(self) -> bool:
        return False

    @property
    def vendor_key_owner_verified(self) -> bool:
        return False

    @property
    def data_retention_allowed(self) -> bool:
        return False

    @property
    def trading_actionable(self) -> bool:
        return False


def inspect_fixture_floor_history(
    records: tuple[FixtureFloorRecord, ...],
    anchor: ClaimedIndependentAnchor,
) -> FixtureFloorInspection:
    """Check offline chain against supplied witness claim; no external I/O.

    A replaced/truncated file fails ONLY if `anchor` was truly held separately;
    a malicious caller who can replace BOTH file and anchor is undetectable.
    """
    if not isinstance(records, tuple) or not isinstance(anchor, ClaimedIndependentAnchor):
        raise TypeError("Typed immutable records and claimed anchor required")
    if not 1 <= len(records) <= _MAX_RECORDS:
        raise HostPreflightRejected("Nonempty bounded history required")
    prior = None
    for i, rec in enumerate(records,1):
        if not isinstance(rec, FixtureFloorRecord):
            raise HostPreflightRejected("Unknown floor record type")
        if rec.compute_sha256() != rec.record_sha256:
            raise HostPreflightRejected("Fixture record tampered after construction")
        if rec.index != i or rec.previous_record_sha256 != (prior.record_sha256 if prior else _GENESIS):
            raise HostPreflightRejected("Gap, reorder, or broken fixture hash link")
        if prior:
            if rec.product is not prior.product or rec.account_binding_sha256_claim != prior.account_binding_sha256_claim:
                raise HostPreflightRejected("Cross-account/product floor replaced")
            if (rec.custody_key_id != prior.custody_key_id or
                    rec.custody_key_sha256 != prior.custody_key_sha256 or
                    rec.custody_epoch != prior.custody_epoch):
                raise HostPreflightRejected("Unverified fixture key rotation")
            if rec.sequence < prior.sequence or (rec.sequence == prior.sequence and rec.tail_sha256 != prior.tail_sha256):
                raise HostPreflightRejected("Sequence rollback or same-sequence fork")
            if rec.last_issued_at_utc < prior.last_issued_at_utc or rec.observed_at_utc <= prior.observed_at_utc:
                raise HostPreflightRejected("Regressing or duplicate time")
        prior = rec
    final = records[-1]
    if (anchor.product is not final.product or
            anchor.account_binding_sha256_claim != final.account_binding_sha256_claim or
            anchor.expected_index != final.index or
            anchor.expected_record_sha256 != final.record_sha256):
        raise HostPreflightRejected("History does not match separately supplied witness anchor")
    return FixtureFloorInspection(final.product,len(records),final.sequence,final.record_sha256,True)


def require_external_trust(report: ExternalOnboardingReport | FixtureFloorInspection):
    """Local fixture or checklist NEVER unlocks provider data rights."""
    if not isinstance(report,(ExternalOnboardingReport,FixtureFloorInspection)):
        raise TypeError("Typed report required")
    raise PermissionError("P0.29b has no independently authenticated vendor/witness or protected host")
