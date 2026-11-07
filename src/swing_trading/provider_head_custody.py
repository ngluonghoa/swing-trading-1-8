"""P0.29: conditional, read-only signed custody-head and rotation preflight.

NO custodian identity is authenticated here. ALL keys, floors and signatures are
caller-supplied claims; freshness is measured against a caller-supplied clock.
No network, stateful monotonic store, raw quotes, key enrolment or rights grant.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256
import json
import re


HEX = re.compile(r"^[0-9a-f]{64}$")
KEY = re.compile(r"^KEY-[A-Z0-9]{8,32}$")
EVID = re.compile(r"^EVID-[A-Z0-9]{8,32}$")
HEAD = re.compile(r"^HEAD-[A-Z0-9]{8,32}$")
NONCE = re.compile(r"^[0-9a-f]{32}$")
HEAD_DOMAIN = b"SwingTrading1.8/P0.29/CustodianRightsHead/Ed25519/v1\x00"
ROTATION_DOMAIN = b"SwingTrading1.8/P0.29/DualCustodianKeyRotation/v1\x00"
MAX_HEAD_AGE = timedelta(minutes=5)


class CustodyRejected(ValueError):
    """Claims fail the conditional custody-head verification contract."""


class CustodyProduct(str, Enum):
    SSI_MCP_TICKS = "SSI_MCP.marketdata_list_intraday_stock_infor"
    SSI_FASTCONNECT_OHLC = "SSI_FASTCONNECT.Market/IntradayOhlc"
    DNSE_MCP_D1 = "DNSE_MCP.price_get_history"
    DNSE_OPENAPI_OHLC = "DNSE_OPENAPI./price/ohlc"
    VCBS_MCP_D1 = "VCBS_MCP.vcbs_get_history.D"


def _utc(value: datetime) -> str:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() != timedelta(0)):
        raise CustodyRejected("Timezone-aware UTC timestamp required")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _hex(value: str, label: str) -> None:
    if not isinstance(value, str) or not HEX.fullmatch(value):
        raise CustodyRejected(label + " must be lowercase SHA256")


def _id(value: str, pattern: re.Pattern, label: str) -> None:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise CustodyRejected("Malformed opaque " + label)


def _signature(text: str) -> bytes:
    if not isinstance(text, str):
        raise CustodyRejected("Canonical base64 Ed25519 signature required")
    try:
        raw = base64.b64decode(text, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise CustodyRejected("Malformed Ed25519 signature encoding") from exc
    if len(raw) != 64 or base64.b64encode(raw).decode("ascii") != text:
        raise CustodyRejected("Noncanonical or invalid-length signature")
    return raw


def _bytes(domain: bytes, payload: dict) -> bytes:
    return domain + json.dumps(payload, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=True, allow_nan=False).encode("ascii")


def _ed25519_verify(public_key: bytes, signature: str, message: bytes) -> None:
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:
        raise RuntimeError("Install cryptography for Ed25519 verification") from exc
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(_signature(signature), message)
    except (InvalidSignature, ValueError) as exc:
        raise CustodyRejected("Custodian Ed25519 signature did not verify") from exc


@dataclass(frozen=True)
class ClaimedCustodianKey:
    product: CustodyProduct
    key_id: str
    epoch: int
    public_key: bytes = field(repr=False)
    public_key_sha256: str
    enrollment_evidence_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.product, CustodyProduct):
            raise TypeError("Typed custody product required")
        _id(self.key_id, KEY, "key ID")
        _id(self.enrollment_evidence_id, EVID, "enrollment evidence ID")
        if type(self.epoch) is not int or not 1 <= self.epoch <= 1000000:
            raise CustodyRejected("Positive bounded custody key epoch required")
        if type(self.public_key) is not bytes or len(self.public_key) != 32:
            raise CustodyRejected("32-byte Ed25519 public key required")
        _hex(self.public_key_sha256, "Custodian key fingerprint")
        if sha256(self.public_key).hexdigest() != self.public_key_sha256:
            raise CustodyRejected("Custodian key fingerprint mismatch")

    @property
    def vendor_key_owner_verified(self) -> bool:
        return False

    @property
    def independently_enrolled(self) -> bool:
        return False


@dataclass(frozen=True)
class SignedCustodyHead:
    product: CustodyProduct
    head_id: str
    custody_key_id: str
    custody_epoch: int
    event_key_id: str
    event_public_key_sha256: str
    sequence: int
    tail_sha256: str
    account_binding_sha256_claim: str
    issued_at_utc: datetime
    expires_at_utc: datetime
    signature_base64: str = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.product, CustodyProduct):
            raise TypeError("Typed custody product required")
        for value, regex, label in ((self.head_id, HEAD, "head"),
                                    (self.custody_key_id, KEY, "custody key"),
                                    (self.event_key_id, KEY, "event key")):
            _id(value, regex, label)
        for label, value in (("event key SHA256", self.event_public_key_sha256),
                             ("event chain SHA256", self.tail_sha256),
                             ("account binding SHA256", self.account_binding_sha256_claim)):
            _hex(value, label)
        if type(self.custody_epoch) is not int or not 1 <= self.custody_epoch <= 1000000:
            raise CustodyRejected("Invalid head key epoch")
        if type(self.sequence) is not int or not 1 <= self.sequence <= 1000000000:
            raise CustodyRejected("Invalid head sequence")
        _utc(self.issued_at_utc)
        _utc(self.expires_at_utc)
        ttl = self.expires_at_utc - self.issued_at_utc
        if not timedelta(0) < ttl <= MAX_HEAD_AGE:
            raise CustodyRejected("Head expiry must follow issuance by at most five minutes")
        _signature(self.signature_base64)

    def signing_bytes(self) -> bytes:
        return _bytes(HEAD_DOMAIN, {
            "schema": 1,
            "product": self.product.value,
            "head_id": self.head_id,
            "custody_key_id": self.custody_key_id,
            "custody_epoch": self.custody_epoch,
            "event_key_id": self.event_key_id,
            "event_public_key_sha256": self.event_public_key_sha256,
            "sequence": self.sequence,
            "tail_sha256": self.tail_sha256,
            "account_binding_sha256_claim": self.account_binding_sha256_claim,
            "issued_at_utc": _utc(self.issued_at_utc),
            "expires_at_utc": _utc(self.expires_at_utc),
        })


@dataclass(frozen=True)
class ClaimedMonotonicFloor:
    """External high-watermark claim, NOT a durable trusted monotonic store."""
    product: CustodyProduct
    custody_key_id: str
    custody_key_sha256: str
    custody_epoch: int
    sequence: int
    tail_sha256: str
    account_binding_sha256_claim: str
    last_issued_at_utc: datetime
    observed_at_utc: datetime
    custody_evidence_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.product, CustodyProduct):
            raise TypeError("Typed custody product required")
        _id(self.custody_key_id, KEY, "floor custody key")
        _id(self.custody_evidence_id, EVID, "floor evidence")
        _hex(self.custody_key_sha256, "Floor key")
        _hex(self.tail_sha256, "Floor tail")
        _hex(self.account_binding_sha256_claim, "Floor account binding")
        if (type(self.custody_epoch) is not int or not 1 <= self.custody_epoch <= 1000000
                or type(self.sequence) is not int or not 1 <= self.sequence <= 1000000000):
            raise CustodyRejected("Positive bounded persisted floor required")
        _utc(self.last_issued_at_utc)
        _utc(self.observed_at_utc)
        if self.last_issued_at_utc > self.observed_at_utc:
            raise CustodyRejected("Floor observed before its own signed issuance")

    @property
    def externally_protected_storage_verified(self) -> bool:
        return False


@dataclass(frozen=True)
class DualSignedKeyRotation:
    product: CustodyProduct
    previous_key_id: str
    previous_key_sha256: str
    previous_epoch: int
    next_key_id: str
    next_key_sha256: str
    next_epoch: int
    floor_sequence: int
    floor_tail_sha256: str
    account_binding_sha256_claim: str
    rotated_at_utc: datetime
    nonce_hex: str
    previous_signature_base64: str = field(repr=False)
    next_signature_base64: str = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.product, CustodyProduct):
            raise TypeError("Typed rotation product required")
        for value in (self.previous_key_id, self.next_key_id):
            _id(value, KEY, "rotation key ID")
        for label, value in (("previous key SHA256", self.previous_key_sha256),
                             ("next key SHA256", self.next_key_sha256),
                             ("rotation floor SHA256", self.floor_tail_sha256)):
            _hex(value, label)
        _hex(self.account_binding_sha256_claim, "Rotation account binding")
        _id(self.nonce_hex, NONCE, "rotation nonce")
        if self.previous_key_id == self.next_key_id or self.previous_key_sha256 == self.next_key_sha256:
            raise CustodyRejected("Rotation must replace a distinct key")
        if (type(self.previous_epoch) is not int or type(self.next_epoch) is not int
                or self.previous_epoch < 1 or self.next_epoch != self.previous_epoch + 1):
            raise CustodyRejected("Rotation must advance one custody key epoch")
        if type(self.floor_sequence) is not int or self.floor_sequence < 1:
            raise CustodyRejected("Rotation must bind an existing positive floor")
        _utc(self.rotated_at_utc)
        _signature(self.previous_signature_base64)
        _signature(self.next_signature_base64)

    def signing_bytes(self) -> bytes:
        return _bytes(ROTATION_DOMAIN, {
            "schema": 1,
            "product": self.product.value,
            "previous_key_id": self.previous_key_id,
            "previous_key_sha256": self.previous_key_sha256,
            "previous_epoch": self.previous_epoch,
            "next_key_id": self.next_key_id,
            "next_key_sha256": self.next_key_sha256,
            "next_epoch": self.next_epoch,
            "floor_sequence": self.floor_sequence,
            "floor_tail_sha256": self.floor_tail_sha256,
            "account_binding_sha256_claim": self.account_binding_sha256_claim,
            "rotated_at_utc": _utc(self.rotated_at_utc),
            "nonce_hex": self.nonce_hex,
        })


@dataclass(frozen=True)
class ConditionalHeadAudit:
    product: CustodyProduct
    sequence: int
    tail_sha256: str
    custody_epoch: int
    relative_floor_held: bool
    custodian_signature_integrity: bool
    dual_rotation_signatures_verified: bool
    conditional_event_chain_integrity: bool
    age_within_local_budget: bool
    event_chain_state: str | None = None
    unresolved: tuple[str, ...] = (
        "UNVERIFIED_VENDOR_KEY_OWNER",
        "UNAUTHENTICATED_EXTERNAL_HEAD_CUSTODIAN",
        "UNTRUSTED_MONOTONIC_FLOOR_STORAGE",
        "UNVERIFIED_ACCOUNT_PRODUCT_RIGHTS_AND_RETENTION",
        "UNVERIFIED_COMPLETE_LIVE_REVOCATION_STREAM",
    )

    @property
    def vendor_key_origin_verified(self) -> bool:
        return False

    @property
    def fresh_revocation_stream_authenticated(self) -> bool:
        return False

    @property
    def anti_rollback_across_restarts_verified(self) -> bool:
        return False

    @property
    def rights_to_read_or_cache(self) -> bool:
        return False

    @property
    def market_indicators_allowed(self) -> bool:
        return False

    @property
    def historical_backtest_allowed(self) -> bool:
        return False

    @property
    def trading_actionable(self) -> bool:
        return False


def _rotation_matches_floor(
    rotation: DualSignedKeyRotation, floor: ClaimedMonotonicFloor,
    key: ClaimedCustodianKey, previous: ClaimedCustodianKey,
    head: SignedCustodyHead,
) -> None:
    if (previous.product is not floor.product or previous.key_id != floor.custody_key_id
            or previous.public_key_sha256 != floor.custody_key_sha256
            or previous.epoch != floor.custody_epoch):
        raise CustodyRejected("Previous rotation key not anchored to claimed floor")
    if (rotation.product is not head.product or rotation.product is not floor.product
            or rotation.previous_key_id != previous.key_id
            or rotation.previous_key_sha256 != previous.public_key_sha256
            or rotation.previous_epoch != previous.epoch
            or rotation.next_key_id != key.key_id
            or rotation.next_key_sha256 != key.public_key_sha256
            or rotation.next_epoch != key.epoch
            or rotation.floor_sequence != floor.sequence
            or rotation.floor_tail_sha256 != floor.tail_sha256
            or rotation.account_binding_sha256_claim != floor.account_binding_sha256_claim
            or head.account_binding_sha256_claim != floor.account_binding_sha256_claim):
        raise CustodyRejected("Rotation does not bind exact prior floor and keys")
    if not floor.last_issued_at_utc <= rotation.rotated_at_utc <= head.issued_at_utc:
        raise CustodyRejected("Rotation time does not follow floor and precede head")
    msg = rotation.signing_bytes()
    _ed25519_verify(previous.public_key, rotation.previous_signature_base64, msg)
    _ed25519_verify(key.public_key, rotation.next_signature_base64, msg)


def audit_conditional_custody_head(
    head: SignedCustodyHead, key: ClaimedCustodianKey,
    floor: ClaimedMonotonicFloor, *, checked_at_utc: datetime,
    rotation: DualSignedKeyRotation | None = None,
    previous_key: ClaimedCustodianKey | None = None,
    event_pin: object | None = None, events: tuple | None = None,
) -> ConditionalHeadAudit:
    """Only conditional crypto and a CALLER-SUPPLIED floor; NEVER provider approval.

    Optional P0.28 events and pin are independently verified and cross-bound to
    the custodian's signed head; VCBS cannot supply a P0.28 event product yet.
    No state mutation takes place and an adversary can supply self-made claims.
    """
    if not isinstance(head, SignedCustodyHead) or not isinstance(key, ClaimedCustodianKey):
        raise TypeError("Typed signed head and custody key required")
    if not isinstance(floor, ClaimedMonotonicFloor):
        raise TypeError("Explicit typed external floor required")
    _utc(checked_at_utc)
    if (head.product is not key.product or head.product is not floor.product
            or head.custody_key_id != key.key_id or head.custody_epoch != key.epoch):
        raise CustodyRejected("Custody product/key/epoch mismatch")
    if floor.observed_at_utc > checked_at_utc:
        raise CustodyRejected("Floor is from the future")
    if (head.issued_at_utc > checked_at_utc or
            checked_at_utc - head.issued_at_utc > MAX_HEAD_AGE or
            head.expires_at_utc <= checked_at_utc):
        raise CustodyRejected("Signed head stale, expired, or from future")
    if head.account_binding_sha256_claim != floor.account_binding_sha256_claim:
        raise CustodyRejected("Head account/product binding differs from claimed floor")
    if key.public_key_sha256 == head.event_public_key_sha256:
        raise CustodyRejected("Custodian and event signer must be distinct keys")
    if head.issued_at_utc < floor.last_issued_at_utc:
        raise CustodyRejected("Head issuance rolled back before claimed floor")
    if head.sequence < floor.sequence:
        raise CustodyRejected("Custody head sequence rolled back")
    if head.sequence == floor.sequence and head.tail_sha256 != floor.tail_sha256:
        raise CustodyRejected("Equal-sequence fork differs from claimed floor")
    if key.epoch < floor.custody_epoch or key.epoch > floor.custody_epoch + 1:
        raise CustodyRejected("Custody key epoch downgrade/skip")
    if key.epoch == floor.custody_epoch:
        if (rotation is not None or previous_key is not None or
                key.key_id != floor.custody_key_id or
                key.public_key_sha256 != floor.custody_key_sha256):
            raise CustodyRejected("Unapproved same-epoch key substitution")
        rotated = False
    else:
        if not isinstance(rotation, DualSignedKeyRotation) or not isinstance(previous_key, ClaimedCustodianKey):
            raise CustodyRejected("Dual-signature proof required for rotation")
        _rotation_matches_floor(rotation, floor, key, previous_key, head)
        rotated = True
    _ed25519_verify(key.public_key, head.signature_base64, head.signing_bytes())

    if (event_pin is None) != (events is None):
        raise CustodyRejected("Event pin and complete signed events must be paired")
    linked = False
    event_state = None
    if event_pin is not None:
        from .provider_signed_event_chain import (
            ClaimedExternalLedgerPin, SignedRightsEvent, verify_pinned_rights_event_chain,
        )
        if (not isinstance(event_pin, ClaimedExternalLedgerPin)
                or not isinstance(events, tuple)
                or any(not isinstance(x, SignedRightsEvent) for x in events)):
            raise CustodyRejected("Typed P0.28 pin and signed event tuple required")
        if (event_pin.product.value != head.product.value
                or event_pin.key_id != head.event_key_id
                or event_pin.expected_public_key_sha256 != head.event_public_key_sha256
                or event_pin.expected_sequence != head.sequence
                or event_pin.expected_tail_sha256 != head.tail_sha256
                or event_pin.pinned_at_utc != head.issued_at_utc):
            raise CustodyRejected("P0.28 event pin not exactly bound to signed custody head")
        chain = verify_pinned_rights_event_chain(events, event_pin, checked_at_utc=checked_at_utc)
        if floor.sequence > len(events) or events[floor.sequence - 1].chain_hash() != floor.tail_sha256:
            raise CustodyRejected("P0.28 signed prefix forked from claimed custody floor")
        event_state = chain.state.value
        linked = True

    return ConditionalHeadAudit(
        product=head.product, sequence=head.sequence, tail_sha256=head.tail_sha256,
        custody_epoch=key.epoch, relative_floor_held=True,
        custodian_signature_integrity=True, dual_rotation_signatures_verified=rotated,
        conditional_event_chain_integrity=linked, age_within_local_budget=True,
        event_chain_state=event_state,
    )


def require_authenticated_provider_rights(report: ConditionalHeadAudit) -> None:
    """No offline claim may be escalated into live provider/data permissions."""
    if not isinstance(report, ConditionalHeadAudit):
        raise TypeError("Typed conditional audit required")
    raise PermissionError(
        "P0.29 lacks externally authenticated vendor key owner, custody and live rights"
    )
