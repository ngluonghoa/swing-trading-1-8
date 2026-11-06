"""P0.29: offline, CONDITIONAL custody-head/rotation/rollback contract.

All inputs, including the root and high-water floor, remain externally CLAIMED.
No provider identity, independent custody, durable CAS, current vendor head or
licence is established here. There is no signer, enrolment, I/O or permission
promotion. A self-consistent attacker-owned root still passes only integrity.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from hashlib import sha256
import re
from typing import Protocol

from .native_minute_bar_source_plan import BarProduct, describe_bar_product
from .provider_signed_event_chain import (
    RightsChainRejected, RightsChainState, SignedRightsEvent,
    _canonical, _iso, _sig, _verify_rights_prefix,
)

_ZERO = "0" * 64
_HEX = re.compile(r"[0-9a-f]{64}")
_NONCE = re.compile(r"[0-9a-f]{32}")
_MAX_EVENTS = 128
_MAX_EPOCHS = 16
_FRESHNESS_WINDOW = timedelta(seconds=60)
_DOMAIN = b"SwingTrading1.8/P0.29/"


class HeadCustodyRejected(RightsChainRejected):
    """The claimed root, rotation, challenge, head or floor is inconsistent."""


def _identifier(value, prefix):
    if type(value) is not str or not re.fullmatch(prefix + r"-[A-Z0-9]{8,32}", value):
        raise HeadCustodyRejected("Opaque nonsecret identity required")


def _digest(value):
    if type(value) is not str or not _HEX.fullmatch(value):
        raise HeadCustodyRejected("Canonical sha256 hex required")


def _nonce(value):
    if type(value) is not str or not _NONCE.fullmatch(value):
        raise HeadCustodyRejected("Canonical 128-bit challenge nonce required")


def _integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise HeadCustodyRejected("Bounded integer required")


def _utc(value):
    if type(value) is not datetime:
        raise TypeError("UTC datetime required")
    return _iso(value)


def _public_key(raw):
    if type(raw) is not bytes or len(raw) != 32:
        raise HeadCustodyRejected("Ed25519 public key must be 32 bytes")
    return sha256(raw).hexdigest()


def _bytes(kind, values):
    return _DOMAIN + kind + b"/v1\x00" + _canonical({"schema": 1, **values})


def _verify(raw_key, signature, message):
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:
        raise RuntimeError("Install the [custody] extra for Ed25519 verification") from exc
    try:
        Ed25519PublicKey.from_public_bytes(raw_key).verify(_sig(signature), message)
    except (InvalidSignature, ValueError) as exc:
        raise HeadCustodyRejected("Custody signature verification failed") from exc


@dataclass(frozen=True)
class ClaimedCustodyAnchor:
    product: BarProduct
    custodian_id: str
    root_key_id: str
    root_public_key_raw: bytes = field(repr=False)
    expected_root_sha256: str
    provenance_evidence_id: str
    operator_actor_id: str
    independent_reviewer_actor_id: str

    def __post_init__(self):
        describe_bar_product(self.product)
        for value, prefix in (
            (self.custodian_id, "CUST"), (self.root_key_id, "KEY"),
            (self.provenance_evidence_id, "EVID"),
            (self.operator_actor_id, "ACTR"),
            (self.independent_reviewer_actor_id, "ACTR"),
        ):
            _identifier(value, prefix)
        _digest(self.expected_root_sha256)
        if _public_key(self.root_public_key_raw) != self.expected_root_sha256:
            raise HeadCustodyRejected("Root fingerprint mismatch")
        if self.operator_actor_id == self.independent_reviewer_actor_id:
            raise HeadCustodyRejected("Distinct claimed operator/reviewer required")

    def anchor_sha256(self):
        return sha256(_bytes(b"ClaimedAnchor", {
            "product": self.product.value, "custodian_id": self.custodian_id,
            "root_key_id": self.root_key_id, "root_sha256": self.expected_root_sha256,
            "provenance_evidence_id": self.provenance_evidence_id,
            "operator_actor_id": self.operator_actor_id,
            "independent_reviewer_actor_id": self.independent_reviewer_actor_id,
        })).hexdigest()

    @property
    def provider_key_owner_verified(self):
        return False


@dataclass(frozen=True)
class SignedLedgerKeyEpoch:
    product: BarProduct
    anchor_sha256: str
    epoch: int
    key_id: str
    public_key_raw: bytes = field(repr=False)
    activates_at_sequence: int
    recorded_at_utc: datetime
    expires_at_utc: datetime
    previous_epoch_sha256: str
    provenance_evidence_id: str
    root_signature_base64: str
    new_key_signature_base64: str
    previous_key_signature_base64: str | None

    def __post_init__(self):
        describe_bar_product(self.product)
        _digest(self.anchor_sha256)
        _integer(self.epoch, 1, _MAX_EPOCHS)
        _identifier(self.key_id, "KEY")
        _public_key(self.public_key_raw)
        _integer(self.activates_at_sequence, 1, _MAX_EVENTS)
        _utc(self.recorded_at_utc)
        _utc(self.expires_at_utc)
        if self.expires_at_utc <= self.recorded_at_utc:
            raise HeadCustodyRejected("Key epoch expiry must follow publication")
        _digest(self.previous_epoch_sha256)
        _identifier(self.provenance_evidence_id, "EVID")
        _sig(self.root_signature_base64)
        _sig(self.new_key_signature_base64)
        if self.epoch == 1:
            if (self.previous_epoch_sha256 != _ZERO
                    or self.activates_at_sequence != 1
                    or self.previous_key_signature_base64 is not None):
                raise HeadCustodyRejected("Explicit genesis key epoch required")
        elif self.previous_key_signature_base64 is None:
            raise HeadCustodyRejected("Rotation needs previous-key continuity signature")
        else:
            _sig(self.previous_key_signature_base64)

    def signing_bytes(self, role):
        if role not in ("ROOT", "NEW_KEY", "PREVIOUS_KEY"):
            raise HeadCustodyRejected("Known rotation signature role required")
        return _bytes(b"KeyEpoch/" + role.encode("ascii"), {
            "product": self.product.value, "anchor_sha256": self.anchor_sha256,
            "epoch": self.epoch, "key_id": self.key_id,
            "public_key_sha256": _public_key(self.public_key_raw),
            "activates_at_sequence": self.activates_at_sequence,
            "recorded_at_utc": _utc(self.recorded_at_utc),
            "expires_at_utc": _utc(self.expires_at_utc),
            "previous_epoch_sha256": self.previous_epoch_sha256,
            "provenance_evidence_id": self.provenance_evidence_id,
        })

    def registry_sha256(self):
        return sha256(_DOMAIN + b"KeyRegistry/v1\x00"
                      + self.signing_bytes("ROOT") + _sig(self.root_signature_base64)
                      + _sig(self.new_key_signature_base64)
                      + (_sig(self.previous_key_signature_base64)
                         if self.previous_key_signature_base64 is not None else b"")).hexdigest()


@dataclass(frozen=True)
class ClaimedCustodyFloor:
    anchor_sha256: str
    generation: int
    head_serial: int
    sequence: int
    tail_sha256: str
    key_epoch: int
    key_registry_sha256: str
    checked_at_utc: datetime
    head_issued_at_utc: datetime | None
    challenge_id: str | None
    challenge_nonce_hex: str | None
    hold_observed: bool

    def __post_init__(self):
        _digest(self.anchor_sha256)
        _integer(self.generation, 0, 2**63 - 1)
        _integer(self.head_serial, 0, 2**63 - 1)
        _integer(self.sequence, 0, _MAX_EVENTS)
        _integer(self.key_epoch, 0, _MAX_EPOCHS)
        _digest(self.tail_sha256)
        _digest(self.key_registry_sha256)
        _utc(self.checked_at_utc)
        if type(self.hold_observed) is not bool:
            raise TypeError("Typed sticky hold flag required")
        if self.generation == 0:
            if (any((self.head_serial, self.sequence, self.key_epoch, self.hold_observed))
                    or self.tail_sha256 != _ZERO or self.key_registry_sha256 != _ZERO
                    or self.head_issued_at_utc is not None or self.challenge_id is not None
                    or self.challenge_nonce_hex is not None):
                raise HeadCustodyRejected("Bootstrap floor must be explicitly empty")
        else:
            if not all((self.head_serial, self.sequence, self.key_epoch)):
                raise HeadCustodyRejected("Observed floor cannot reset counters")
            if self.tail_sha256 == _ZERO or self.key_registry_sha256 == _ZERO:
                raise HeadCustodyRejected("Observed floor requires non-genesis digests")
            _utc(self.head_issued_at_utc)
            if self.head_issued_at_utc > self.checked_at_utc:
                raise HeadCustodyRejected("Floor cannot predate its observed head")
            _identifier(self.challenge_id, "CHAL")
            _nonce(self.challenge_nonce_hex)

    def floor_sha256(self):
        return sha256(_bytes(b"ClaimedFloor", {
            "anchor_sha256": self.anchor_sha256, "generation": self.generation,
            "head_serial": self.head_serial, "sequence": self.sequence,
            "tail_sha256": self.tail_sha256, "key_epoch": self.key_epoch,
            "key_registry_sha256": self.key_registry_sha256,
            "checked_at_utc": _utc(self.checked_at_utc),
            "head_issued_at_utc": (_utc(self.head_issued_at_utc)
                                   if self.head_issued_at_utc is not None else None),
            "challenge_id": self.challenge_id,
            "challenge_nonce_hex": self.challenge_nonce_hex,
            "hold_observed": self.hold_observed,
        })).hexdigest()


def bootstrap_claimed_custody_floor(anchor: ClaimedCustodyAnchor, *, checked_at_utc):
    """Explicit engineering bootstrap ONLY; never recover a lost production floor.

    A real custodian must independently enrol/pin the root and retain its floor.
    Supplying a fresh bootstrap after deletion/rollback is outside this proof.
    """
    if type(anchor) is not ClaimedCustodyAnchor:
        raise TypeError("Exact claimed anchor required")
    return ClaimedCustodyFloor(anchor.anchor_sha256(), 0, 0, 0, _ZERO, 0, _ZERO,
                              checked_at_utc, None, None, None, False)


@dataclass(frozen=True)
class HeadFreshnessChallenge:
    product: BarProduct
    anchor_sha256: str
    floor_sha256: str
    challenge_id: str
    nonce_hex: str
    issued_at_utc: datetime
    expires_at_utc: datetime

    def __post_init__(self):
        describe_bar_product(self.product)
        _digest(self.anchor_sha256)
        _digest(self.floor_sha256)
        _identifier(self.challenge_id, "CHAL")
        _nonce(self.nonce_hex)
        _utc(self.issued_at_utc)
        _utc(self.expires_at_utc)
        if not timedelta(0) < self.expires_at_utc - self.issued_at_utc <= _FRESHNESS_WINDOW:
            raise HeadCustodyRejected("Challenge lifetime must be positive and at most 60s")


@dataclass(frozen=True)
class SignedCustodianHead:
    product: BarProduct
    anchor_sha256: str
    head_id: str
    head_serial: int
    challenge_id: str
    challenge_nonce_hex: str
    floor_sha256: str
    key_epoch: int
    key_registry_sha256: str
    ledger_key_id: str
    ledger_key_sha256: str
    sequence: int
    tail_sha256: str
    issued_at_utc: datetime
    expires_at_utc: datetime
    service_suspended: bool
    signature_base64: str

    def __post_init__(self):
        describe_bar_product(self.product)
        for digest in (self.anchor_sha256, self.floor_sha256, self.key_registry_sha256,
                       self.ledger_key_sha256, self.tail_sha256):
            _digest(digest)
        _identifier(self.head_id, "HEAD")
        _identifier(self.challenge_id, "CHAL")
        _identifier(self.ledger_key_id, "KEY")
        _nonce(self.challenge_nonce_hex)
        _integer(self.head_serial, 1, 2**63 - 1)
        _integer(self.key_epoch, 1, _MAX_EPOCHS)
        _integer(self.sequence, 1, _MAX_EVENTS)
        _utc(self.issued_at_utc)
        _utc(self.expires_at_utc)
        if not timedelta(0) < self.expires_at_utc - self.issued_at_utc <= _FRESHNESS_WINDOW:
            raise HeadCustodyRejected("Head lifetime must be positive and at most 60s")
        if type(self.service_suspended) is not bool:
            raise TypeError("Typed custodian suspension flag required")
        _sig(self.signature_base64)

    def signing_bytes(self):
        return _bytes(b"CustodianHead", {
            "product": self.product.value, "anchor_sha256": self.anchor_sha256,
            "head_id": self.head_id, "head_serial": self.head_serial,
            "challenge_id": self.challenge_id, "challenge_nonce_hex": self.challenge_nonce_hex,
            "floor_sha256": self.floor_sha256, "key_epoch": self.key_epoch,
            "key_registry_sha256": self.key_registry_sha256,
            "ledger_key_id": self.ledger_key_id, "ledger_key_sha256": self.ledger_key_sha256,
            "sequence": self.sequence, "tail_sha256": self.tail_sha256,
            "issued_at_utc": _utc(self.issued_at_utc), "expires_at_utc": _utc(self.expires_at_utc),
            "service_suspended": self.service_suspended,
        })


class CustodyFloorStorePort(Protocol):
    """External, separately approved store; NO implementation or I/O supplied.

    Missing/corrupt state must raise, never silently bootstrap. CAS must durably
    commit the whole floor and consumed challenge before any future authority
    decision. Root/floor restoration requires separate out-of-band recovery.
    """

    def read_floor(self, anchor_sha256: str) -> ClaimedCustodyFloor: ...

    def compare_and_swap(self, expected_floor_sha256: str,
                         next_floor: ClaimedCustodyFloor) -> bool: ...


@dataclass(frozen=True)
class CustodiedRightsVerification:
    product: BarProduct
    state: RightsChainState
    verified_events: int
    expected_floor_sha256: str
    proposed_floor: ClaimedCustodyFloor

    @property
    def conditional_signature_integrity_verified(self):
        return True

    @property
    def external_atomic_commit_required(self):
        return True

    @property
    def provider_key_owner_verified(self):
        return False

    @property
    def custodian_independence_verified(self):
        return False

    @property
    def durable_rollback_protection_verified(self):
        return False

    @property
    def current_revocation_freshness_verified(self):
        return False

    @property
    def permission_to_read_or_cache(self):
        return False

    @property
    def backtest_allowed(self):
        return False

    @property
    def production_authorized(self):
        return False

    @property
    def actionable(self):
        return False


def verify_custodied_rights_chain(
    events: tuple[SignedRightsEvent, ...],
    key_epochs: tuple[SignedLedgerKeyEpoch, ...],
    anchor: ClaimedCustodyAnchor,
    floor: ClaimedCustodyFloor,
    challenge: HeadFreshnessChallenge,
    head: SignedCustodianHead,
    *, checked_at_utc: datetime,
) -> CustodiedRightsVerification:
    """Validate conditional integrity; return a CAS proposal, NEVER access rights.

    Authentic root enrolment, account-product grant, independent custody, trusted
    UTC/nonce issuance and durable anti-rollback floor remain external gates.
    """
    for value, cls in ((anchor, ClaimedCustodyAnchor), (floor, ClaimedCustodyFloor),
                       (challenge, HeadFreshnessChallenge), (head, SignedCustodianHead)):
        if type(value) is not cls:
            raise TypeError("Exact immutable custody contracts required")
        value.__post_init__()
    _utc(checked_at_utc)
    if type(key_epochs) is not tuple or not 1 <= len(key_epochs) <= _MAX_EPOCHS:
        raise HeadCustodyRejected("Bounded immutable key-epoch history required")
    if any(type(e) is not SignedLedgerKeyEpoch for e in key_epochs):
        raise TypeError("Exact signed key epochs required")
    anchor_hash = anchor.anchor_sha256()
    floor_hash = floor.floor_sha256()
    if any(h != anchor_hash for h in (floor.anchor_sha256, challenge.anchor_sha256,
                                     head.anchor_sha256)):
        raise HeadCustodyRejected("Root/provenance substitution or wrong custody floor")
    if challenge.product is not anchor.product or head.product is not anchor.product:
        raise HeadCustodyRejected("Cross-product freshness response")
    if challenge.floor_sha256 != floor_hash or head.floor_sha256 != floor_hash:
        raise HeadCustodyRejected("Freshness response does not bind current floor")
    if (head.challenge_id != challenge.challenge_id
            or head.challenge_nonce_hex != challenge.nonce_hex
            or challenge.challenge_id == floor.challenge_id
            or challenge.nonce_hex == floor.challenge_nonce_hex):
        raise HeadCustodyRejected("Wrong or already consumed challenge")
    if not (floor.checked_at_utc <= challenge.issued_at_utc <= head.issued_at_utc
            <= checked_at_utc < head.expires_at_utc <= challenge.expires_at_utc):
        raise HeadCustodyRejected("Stale/future response, expired challenge or clock rollback")
    if (head.head_serial <= floor.head_serial or head.sequence < floor.sequence
            or head.key_epoch < floor.key_epoch):
        raise HeadCustodyRejected("Custodian head/sequence/key epoch rollback or replay")
    if floor.head_issued_at_utc is not None and head.issued_at_utc < floor.head_issued_at_utc:
        raise HeadCustodyRejected("Custodian head clock regressed")
    _verify(anchor.root_public_key_raw, head.signature_base64, head.signing_bytes())

    prior_hash = _ZERO
    previous = None
    key_ids = {anchor.root_key_id}
    key_fingerprints = {anchor.expected_root_sha256}
    for index, epoch in enumerate(key_epochs, 1):
        epoch.__post_init__()
        if (epoch.product is not anchor.product or epoch.anchor_sha256 != anchor_hash
                or epoch.epoch != index or epoch.previous_epoch_sha256 != prior_hash):
            raise HeadCustodyRejected("Gap, substitution or broken key registry prefix")
        fingerprint = _public_key(epoch.public_key_raw)
        if epoch.key_id in key_ids or fingerprint in key_fingerprints:
            raise HeadCustodyRejected("Repeated ledger key or root/ledger key reuse")
        if epoch.recorded_at_utc > head.issued_at_utc:
            raise HeadCustodyRejected("Future key provenance")
        if previous is not None:
            if (epoch.activates_at_sequence <= previous.activates_at_sequence
                    or epoch.recorded_at_utc < previous.recorded_at_utc
                    or epoch.recorded_at_utc >= previous.expires_at_utc):
                raise HeadCustodyRejected("Retroactive rotation or expired continuity key")
            _verify(previous.public_key_raw, epoch.previous_key_signature_base64,
                    epoch.signing_bytes("PREVIOUS_KEY"))
        _verify(anchor.root_public_key_raw, epoch.root_signature_base64,
                epoch.signing_bytes("ROOT"))
        _verify(epoch.public_key_raw, epoch.new_key_signature_base64,
                epoch.signing_bytes("NEW_KEY"))
        key_ids.add(epoch.key_id)
        key_fingerprints.add(fingerprint)
        prior_hash = epoch.registry_sha256()
        previous = epoch
    active = key_epochs[-1]
    if (head.key_epoch != len(key_epochs) or head.key_registry_sha256 != prior_hash
            or head.ledger_key_id != active.key_id
            or head.ledger_key_sha256 != _public_key(active.public_key_raw)
            or active.activates_at_sequence > head.sequence
            or head.issued_at_utc >= active.expires_at_utc):
        raise HeadCustodyRejected("Head does not pin the complete active key registry")
    if floor.key_epoch and key_epochs[floor.key_epoch - 1].registry_sha256() != floor.key_registry_sha256:
        raise HeadCustodyRejected("Previously observed key registry was rewritten")

    def event_key(event):
        selected = key_epochs[0]
        for candidate in key_epochs[1:]:
            if candidate.activates_at_sequence > event.sequence:
                break
            selected = candidate
        if (event.key_id != selected.key_id
                or not selected.recorded_at_utc <= event.published_at_utc < selected.expires_at_utc):
            raise HeadCustodyRejected("Event uses inactive, unpublished or expired ledger key")
        return selected.public_key_raw

    chain = _verify_rights_prefix(
        events, product=anchor.product, reporting_key_id=active.key_id,
        expected_sequence=head.sequence, expected_tail_sha256=head.tail_sha256,
        pinned_at_utc=head.issued_at_utc, checked_at_utc=checked_at_utc,
        public_key_for_event=event_key,
    )
    if floor.sequence and events[floor.sequence - 1].chain_hash() != floor.tail_sha256:
        raise HeadCustodyRejected("Previously observed event prefix was rewritten")
    is_held = (floor.hold_observed or head.service_suspended
               or chain.state is RightsChainState.SIGNED_HOLD_UNAUTHORIZED)
    state = RightsChainState.SIGNED_HOLD_UNAUTHORIZED if is_held else chain.state
    proposed = ClaimedCustodyFloor(
        anchor_hash, floor.generation + 1, head.head_serial, head.sequence,
        head.tail_sha256, head.key_epoch, head.key_registry_sha256,
        checked_at_utc, head.issued_at_utc, challenge.challenge_id,
        challenge.nonce_hex, is_held,
    )
    return CustodiedRightsVerification(anchor.product, state, chain.verified_events,
                                       floor_hash, proposed)


def require_custodied_rights_authorization(report: CustodiedRightsVerification):
    if type(report) is not CustodiedRightsVerification:
        raise TypeError("Exact custody verification report required")
    raise PermissionError(
        "P0.29 has no independently enrolled provider/custodian root, durable floor, or legal grant"
    )
