"""GĐ4/P0.20 — verifier-only detached Ed25519 journal checkpoint contract.

Never generates or stores a signing key, enrolls an external custodian,
trusts an unpinned public key, or authorizes production. A signature proves
control of the corresponding private key, NOT that external approval occurred.
Optional 'custody' dependency uses vetted cryptography Ed25519 primitives.
"""
import base64
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
import re

from .reference_journal import ReferenceJournalCorrupt, _json, _utc
from .reference_journal_recovery import (
    JournalCheckpoint, verify_journal_backup_against_pinned,
    restore_journal_from_pinned, verify_journal_history_prefix,
)

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HEX = re.compile(r"^[0-9a-f]{64}$")
_DOMAIN = b"SwingTrading1.8/P0.20/MetadataJournalCheckpoint/Ed25519/v1\x00"


def _identifier(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("Explicit stable custody identity required")
    return value


def _signature_bytes(text):
    if not isinstance(text, str):
        raise ValueError("Signature must be canonical base64 text")
    try:
        raw = base64.b64decode(text, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise ValueError("Malformed Ed25519 signature base64") from exc
    if len(raw) != 64 or base64.b64encode(raw).decode("ascii") != text:
        raise ValueError("Ed25519 signature must be exactly 64 canonical bytes")
    return raw


@dataclass(frozen=True)
class DetachedJournalSignature:
    checkpoint_id: str
    store_id: str
    key_id: str
    signed_at_utc: datetime
    signature_base64: str
    schema_version: int = 1
    algorithm: str = "Ed25519"

    def __post_init__(self):
        for name in (self.checkpoint_id, self.store_id, self.key_id):
            _identifier(name)
        _utc(self.signed_at_utc)
        if self.algorithm != "Ed25519" or type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("Unknown detached-signature algorithm/schema")
        _signature_bytes(self.signature_base64)

    def canonical_json(self):
        return _json({
            "checkpoint_id": self.checkpoint_id, "store_id": self.store_id,
            "key_id": self.key_id, "signed_at_utc": _utc(self.signed_at_utc),
            "signature_base64": self.signature_base64,
            "schema_version": self.schema_version, "algorithm": self.algorithm,
        })

    @classmethod
    def parse_json(cls, text):
        if not isinstance(text, str):
            raise TypeError("Signature envelope must be JSON text")
        data = json.loads(text)
        expected = {"checkpoint_id", "store_id", "key_id", "signed_at_utc",
                    "signature_base64", "schema_version", "algorithm"}
        if not isinstance(data, dict) or set(data) != expected:
            raise ValueError("Exact signature envelope schema required")
        if not isinstance(data["signed_at_utc"], str):
            raise ValueError("UTC signing time must be text")
        data["signed_at_utc"] = datetime.fromisoformat(data["signed_at_utc"])
        return cls(**data)


def signature_payload(checkpoint: JournalCheckpoint, *, key_id: str, signed_at_utc: datetime):
    """Canonical bytes for an independently authorized Ed25519 signer.

    No signing, provisioning, key storage or automatic access here.
    """
    if not isinstance(checkpoint, JournalCheckpoint):
        raise TypeError("Typed JournalCheckpoint required")
    _identifier(key_id)
    _utc(signed_at_utc)
    if signed_at_utc < checkpoint.created_at_utc:
        raise ValueError("Signing time predates checkpoint")
    return _DOMAIN + _json({
        "checkpoint": json.loads(checkpoint.canonical_json()),
        "key_id": key_id, "signed_at_utc": _utc(signed_at_utc),
        "algorithm": "Ed25519", "schema_version": 1,
    }).encode("utf-8")


def verify_detached_journal_signature(
    checkpoint: JournalCheckpoint, seal: DetachedJournalSignature, *,
    public_key_raw: bytes, expected_key_id: str, expected_store_id: str,
    expected_public_key_sha256: str,
):
    """Requires public key AND fingerprint from an out-of-band trust anchor."""
    if not isinstance(checkpoint, JournalCheckpoint) or not isinstance(seal, DetachedJournalSignature):
        raise TypeError("Typed checkpoint and signature required")
    _identifier(expected_key_id)
    _identifier(expected_store_id)
    if (type(public_key_raw) is not bytes or len(public_key_raw) != 32
            or not isinstance(expected_public_key_sha256, str)
            or not _HEX.fullmatch(expected_public_key_sha256)):
        raise ValueError("Explicit 32-byte Ed25519 public key and pinned fingerprint required")
    if (seal.key_id != expected_key_id or seal.store_id != expected_store_id
            or checkpoint.store_id != expected_store_id
            or seal.checkpoint_id != checkpoint.checkpoint_id
            or seal.signed_at_utc < checkpoint.created_at_utc):
        raise ReferenceJournalCorrupt("Signature identity/clock mismatch")
    if sha256(public_key_raw).hexdigest() != expected_public_key_sha256:
        raise ReferenceJournalCorrupt("Trusted public-key fingerprint mismatch")
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:
        raise RuntimeError("Install the optional [custody] crypto extra before verifying Ed25519") from exc
    try:
        Ed25519PublicKey.from_public_bytes(public_key_raw).verify(
            _signature_bytes(seal.signature_base64),
            signature_payload(checkpoint, key_id=seal.key_id,
                              signed_at_utc=seal.signed_at_utc),
        )
    except (InvalidSignature, ValueError) as exc:
        raise ReferenceJournalCorrupt("Detached Ed25519 signature mismatch") from exc
    return checkpoint


def verify_signed_journal_backup(backup_path, checkpoint, seal, *,
                                 public_key_raw, expected_key_id,
                                 expected_store_id, expected_public_key_sha256):
    verify_detached_journal_signature(
        checkpoint, seal, public_key_raw=public_key_raw,
        expected_key_id=expected_key_id, expected_store_id=expected_store_id,
        expected_public_key_sha256=expected_public_key_sha256,
    )
    return verify_journal_backup_against_pinned(
        backup_path, checkpoint, expected_store_id=expected_store_id
    )


def restore_signed_journal_backup(backup_path, destination, checkpoint, seal, *,
                                  public_key_raw, expected_key_id,
                                  expected_store_id, expected_public_key_sha256):
    verify_signed_journal_backup(
        backup_path, checkpoint, seal, public_key_raw=public_key_raw,
        expected_key_id=expected_key_id, expected_store_id=expected_store_id,
        expected_public_key_sha256=expected_public_key_sha256,
    )
    return restore_journal_from_pinned(
        backup_path, destination, checkpoint, expected_store_id=expected_store_id
    )


def verify_signed_journal_prefix(store, checkpoint, seal, *,
                                 public_key_raw, expected_key_id,
                                 expected_store_id, expected_public_key_sha256):
    verify_detached_journal_signature(
        checkpoint, seal, public_key_raw=public_key_raw,
        expected_key_id=expected_key_id, expected_store_id=expected_store_id,
        expected_public_key_sha256=expected_public_key_sha256,
    )
    return verify_journal_history_prefix(
        store, checkpoint, expected_store_id=expected_store_id
    )
