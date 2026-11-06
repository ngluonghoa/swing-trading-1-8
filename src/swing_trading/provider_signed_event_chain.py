"""GĐ4/P0.28 — verifier-only pinned Ed25519 rights event-chain prototype.

A valid signature under a CALLER-SUPPLIED key and a matching CALLER-SUPPLIED
head only proves conditional cryptographic integrity. It DOES NOT establish
that the key belongs to SSI/DNSE, that the head came from a trusted custodian,
or that the head is the current complete revocation stream. No signer, HTTP
client, key enrolment, grants, cache access, broker or trading code is shipped.
"""
import base64
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from hashlib import sha256
import json
import re

from .native_minute_bar_source_plan import BarProduct, describe_bar_product
from .provider_rights_review import RightsScope
from .replay import require_utc

_HEX = re.compile(r"^[0-9a-f]{64}$")
_NONCE = re.compile(r"^[0-9a-f]{32}$")
_KEY = re.compile(r"^KEY-[A-Z0-9]{8,32}$")
_EVENT = re.compile(r"^EVNT-[A-Z0-9]{8,32}$")
_HEAD = re.compile(r"^HEAD-[A-Z0-9]{8,32}$")
_EVID = re.compile(r"^EVID-[A-Z0-9]{8,32}$")
_GENESIS = "0" * 64
_DOMAIN = b"SwingTrading1.8/P0.28/RightsEvent/Ed25519/v1\x00"
_CHAIN_DOMAIN = b"SwingTrading1.8/P0.28/EventChain/v1\x00"
_MAX_EVENTS = 128
_MAX_PIN_AGE = timedelta(minutes=5)


class RightsChainRejected(ValueError):
    """An event, signature, pinned checkpoint or chain violates the contract."""


class EventKind(str, Enum):
    GRANT_CANDIDATE = "GRANT_CANDIDATE"
    PROVIDER_REVOKE = "PROVIDER_REVOKE"
    SECURITY_SUSPEND = "SECURITY_SUSPEND"


class RightsChainState(str, Enum):
    SIGNED_CANDIDATE_UNAUTHORIZED = "SIGNED_CANDIDATE_UNAUTHORIZED"
    SIGNED_HOLD_UNAUTHORIZED = "SIGNED_HOLD_UNAUTHORIZED"
    SIGNED_CANDIDATE_EXPIRED = "SIGNED_CANDIDATE_EXPIRED"


def _canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _sig(text):
    if not isinstance(text, str):
        raise RightsChainRejected("Canonical base64 signature required")
    try:
        raw = base64.b64decode(text, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise RightsChainRejected("Malformed signature base64") from exc
    if len(raw) != 64 or base64.b64encode(raw).decode("ascii") != text:
        raise RightsChainRejected("Ed25519 signature must be 64 canonical bytes")
    return raw


def _iso(value):
    require_utc(value)
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class SignedRightsEvent:
    product: BarProduct
    sequence: int
    previous_sha256: str
    event_id: str
    evidence_id: str
    kind: EventKind
    key_id: str
    nonce_hex: str
    published_at_utc: datetime
    effective_at_utc: datetime
    expires_at_utc: datetime | None
    scope_claims: tuple[RightsScope, ...]
    signature_base64: str

    def __post_init__(self):
        describe_bar_product(self.product)
        if type(self.sequence) is not int or self.sequence < 1:
            raise RightsChainRejected("Positive integer sequence required")
        if not isinstance(self.previous_sha256, str) or not _HEX.fullmatch(self.previous_sha256):
            raise RightsChainRejected("Previous hash must be sha256 hex")
        for value, regex in (
            (self.event_id, _EVENT), (self.evidence_id, _EVID),
            (self.key_id, _KEY), (self.nonce_hex, _NONCE)
        ):
            if not isinstance(value, str) or not regex.fullmatch(value):
                raise RightsChainRejected("Nonsecret fixed-schema event identity required")
        if not isinstance(self.kind, EventKind):
            raise TypeError("Typed event kind required")
        _iso(self.published_at_utc)
        _iso(self.effective_at_utc)
        if self.effective_at_utc > self.published_at_utc:
            raise RightsChainRejected("Effective time cannot be later than published time")
        if not isinstance(self.scope_claims, tuple) or any(
            not isinstance(s, RightsScope) for s in self.scope_claims
        ) or len(set(self.scope_claims)) != len(self.scope_claims):
            raise RightsChainRejected("Unique typed claimed scopes required")
        if self.kind is EventKind.GRANT_CANDIDATE:
            if not self.scope_claims or self.expires_at_utc is None:
                raise RightsChainRejected("Candidate needs claimed scope and explicit expiry")
            _iso(self.expires_at_utc)
            if self.expires_at_utc <= self.effective_at_utc:
                raise RightsChainRejected("Candidate expiry must follow effective time")
        elif self.scope_claims or self.expires_at_utc is not None:
            raise RightsChainRejected("Revocation/suspension cannot carry renewal rights")
        _sig(self.signature_base64)

    def signing_bytes(self):
        return _DOMAIN + _canonical({
            "schema": 1,
            "product": self.product.value,
            "sequence": self.sequence,
            "previous_sha256": self.previous_sha256,
            "event_id": self.event_id,
            "evidence_id": self.evidence_id,
            "kind": self.kind.value,
            "key_id": self.key_id,
            "nonce_hex": self.nonce_hex,
            "published_at_utc": _iso(self.published_at_utc),
            "effective_at_utc": _iso(self.effective_at_utc),
            "expires_at_utc": _iso(self.expires_at_utc) if self.expires_at_utc else None,
            "scope_claims": [s.value for s in self.scope_claims],
        })

    def chain_hash(self):
        return sha256(_CHAIN_DOMAIN + self.signing_bytes()
                      + _sig(self.signature_base64)).hexdigest()


@dataclass(frozen=True)
class ClaimedExternalLedgerPin:
    product: BarProduct
    head_id: str
    key_id: str
    public_key_raw: bytes = field(repr=False)
    expected_public_key_sha256: str
    expected_sequence: int
    expected_tail_sha256: str
    pinned_at_utc: datetime

    def __post_init__(self):
        describe_bar_product(self.product)
        if not isinstance(self.head_id, str) or not _HEAD.fullmatch(self.head_id):
            raise RightsChainRejected("Opaque pinned head ID required")
        if not isinstance(self.key_id, str) or not _KEY.fullmatch(self.key_id):
            raise RightsChainRejected("Explicit pinned key identifier required")
        if type(self.public_key_raw) is not bytes or len(self.public_key_raw) != 32:
            raise RightsChainRejected("Pinned Ed25519 public key must be 32 bytes")
        if (not isinstance(self.expected_public_key_sha256, str)
                or not _HEX.fullmatch(self.expected_public_key_sha256)):
            raise RightsChainRejected("Explicit sha256 public key fingerprint required")
        if sha256(self.public_key_raw).hexdigest() != self.expected_public_key_sha256:
            raise RightsChainRejected("Pinned key fingerprint mismatch")
        if type(self.expected_sequence) is not int or self.expected_sequence < 1:
            raise RightsChainRejected("Nonzero pinned sequence required")
        if (not isinstance(self.expected_tail_sha256, str)
                or not _HEX.fullmatch(self.expected_tail_sha256)):
            raise RightsChainRejected("Explicit tail sha256 pin required")
        _iso(self.pinned_at_utc)

    @property
    def pinned_by_independent_provider(self):
        return False

    @property
    def live_revocation_freshness_verified(self):
        return False


@dataclass(frozen=True)
class RightsChainVerification:
    product: BarProduct
    key_id: str
    verified_events: int
    signed_tail_sha256: str
    event_ids: tuple[str, ...]
    state: RightsChainState
    signature_integrity_verified: bool = True

    @property
    def signer_authority_verified(self):
        return False

    @property
    def head_custody_independently_verified(self):
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
    def actionable(self):
        return False


def verify_pinned_rights_event_chain(
    events: tuple[SignedRightsEvent, ...],
    pin: ClaimedExternalLedgerPin,
    *,
    checked_at_utc: datetime,
) -> RightsChainVerification:
    """Verify *conditional* Ed25519 and completeness through a supplied pin.

    The caller MUST obtain the pin/key from a separate authenticated service.
    P0.28 does not establish its authenticity or freshness. It is impossible
    to infer absence of newly appended revocations from this finite prefix.
    """
    if not isinstance(pin, ClaimedExternalLedgerPin):
        raise TypeError("Typed ledger pin required")
    if not isinstance(events, tuple) or any(
        not isinstance(e, SignedRightsEvent) for e in events
    ):
        raise TypeError("Typed immutable event tuple required")
    _iso(checked_at_utc)
    if not 1 <= len(events) <= _MAX_EVENTS:
        raise RightsChainRejected("Nonempty bounded event history required")
    if (pin.pinned_at_utc > checked_at_utc
            or checked_at_utc - pin.pinned_at_utc > _MAX_PIN_AGE):
        raise RightsChainRejected("Claimed head is stale or from the future")
    if len(events) != pin.expected_sequence:
        raise RightsChainRejected("Pinned sequence differs from supplied history")

    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:
        raise RuntimeError("Install the [custody] extra for Ed25519 verification") from exc
    public_key = Ed25519PublicKey.from_public_bytes(pin.public_key_raw)
    previous = _GENESIS
    last_published = None
    ids = set()
    nonces = set()
    last_candidate_expiry = None
    is_held = False

    for index, event in enumerate(events, start=1):
        if event.product is not pin.product or event.key_id != pin.key_id:
            raise RightsChainRejected("Mixed product or unpinned signing key")
        if event.sequence != index or event.previous_sha256 != previous:
            raise RightsChainRejected("Gap, reordering or previous-link mismatch")
        if event.published_at_utc > checked_at_utc or (
            last_published is not None
            and event.published_at_utc < last_published
        ):
            raise RightsChainRejected("Future event or nonmonotone signed publication time")
        if event.event_id in ids or event.nonce_hex in nonces:
            raise RightsChainRejected("Duplicate signed event ID or nonce")
        ids.add(event.event_id)
        nonces.add(event.nonce_hex)
        try:
            public_key.verify(_sig(event.signature_base64), event.signing_bytes())
        except (InvalidSignature, ValueError) as exc:
            raise RightsChainRejected("Ed25519 signature verification failed") from exc
        if event.kind is EventKind.GRANT_CANDIDATE:
            # Even after a signed HOLD, later candidate messages must never
            # implicitly clear an earlier revocation.
            last_candidate_expiry = event.expires_at_utc
        else:
            is_held = True
        previous = event.chain_hash()
        last_published = event.published_at_utc

    if previous != pin.expected_tail_sha256:
        raise RightsChainRejected("Event-chain tip differs from separately supplied pin")
    if is_held:
        state = RightsChainState.SIGNED_HOLD_UNAUTHORIZED
    elif last_candidate_expiry is not None and last_candidate_expiry <= checked_at_utc:
        state = RightsChainState.SIGNED_CANDIDATE_EXPIRED
    else:
        state = RightsChainState.SIGNED_CANDIDATE_UNAUTHORIZED
    return RightsChainVerification(
        pin.product, pin.key_id, len(events), previous,
        tuple(event.event_id for event in events), state,
    )


def require_rights_chain_authorization(report: RightsChainVerification):
    """Verified cryptographic integrity is NEVER an executable licence."""
    if not isinstance(report, RightsChainVerification):
        raise TypeError("Typed rights-chain verification report required")
    raise PermissionError(
        "P0.28 has no authenticated provider key owner, complete fresh head, or legal grant"
    )
