"""GĐ4/P0.19 — detached keyed-MAC checkpoint custody INTERFACE (engineering-only).

A detached HMAC verifies possession of a shared key at sealing time. It does
NOT prove that a key lives with an independent custodian, that a seal was
approved, or that the clock/time/source bytes are authentic. A holder of the
verification key can also forge seals. No keys, tokens or MACs are persisted.
"""
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import hmac
import json
import re

from .reference_journal import ReferenceJournalCorrupt, _json, _utc
from .reference_journal_recovery import (
    JournalCheckpoint, restore_journal_from_pinned,
    verify_journal_backup_against_pinned, verify_journal_history_prefix,
)

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_DOMAIN = b"SwingTrading1.8/P0.19/MetadataJournalCheckpoint/HMAC-SHA256/v1\x00"


def _require_key(key):
    if type(key) is not bytes or len(key) < 32:
        raise ValueError("Explicit >=32-byte out-of-band MAC key required")
    return key


@dataclass(frozen=True)
class DetachedJournalMac:
    """Portable manifest seal; must be transferred through a separate channel."""
    checkpoint_id: str
    store_id: str
    key_id: str
    sealed_at_utc: datetime
    mac_sha256: str
    schema_version: int = 1

    def __post_init__(self):
        for value in (self.checkpoint_id, self.store_id, self.key_id):
            if not isinstance(value, str) or not _ID.fullmatch(value):
                raise ValueError("Invalid detached seal identity")
        _utc(self.sealed_at_utc)
        if not isinstance(self.mac_sha256, str) or not _SHA.fullmatch(self.mac_sha256):
            raise ValueError("Invalid detached HMAC digest")
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("Unsupported detached seal schema")

    def canonical_json(self):
        return _json({
            "checkpoint_id": self.checkpoint_id, "store_id": self.store_id,
            "key_id": self.key_id, "sealed_at_utc": _utc(self.sealed_at_utc),
            "mac_sha256": self.mac_sha256, "schema_version": self.schema_version,
        })

    @classmethod
    def parse_json(cls, value):
        if not isinstance(value, str):
            raise TypeError("Detached seal must be JSON text")
        data = json.loads(value)
        if not isinstance(data, dict) or set(data) != {
            "checkpoint_id", "store_id", "key_id", "sealed_at_utc",
            "mac_sha256", "schema_version",
        }:
            raise ValueError("Exact detached seal JSON schema required")
        if not isinstance(data["sealed_at_utc"], str):
            raise ValueError("Seal clock must be text")
        data["sealed_at_utc"] = datetime.fromisoformat(data["sealed_at_utc"])
        return cls(**data)


def _message(checkpoint, *, key_id, sealed_at_utc):
    return _DOMAIN + _json({
        "checkpoint": json.loads(checkpoint.canonical_json()),
        "key_id": key_id,
        "sealed_at_utc": _utc(sealed_at_utc),
    }).encode("utf-8")


def create_candidate_detached_mac(
    checkpoint: JournalCheckpoint, *,
    signing_key: bytes, key_id: str, sealed_at_utc: datetime,
) -> DetachedJournalMac:
    """Pure helper for an approved OFF-HOST custodian, never auto-called by journal."""
    if not isinstance(checkpoint, JournalCheckpoint):
        raise TypeError("Typed journal checkpoint required")
    _require_key(signing_key)
    if not isinstance(key_id, str) or not _ID.fullmatch(key_id):
        raise ValueError("Explicit custody key identifier required")
    _utc(sealed_at_utc)
    if sealed_at_utc < checkpoint.created_at_utc:
        raise ValueError("Seal cannot predate checkpoint creation")
    mac = hmac.new(signing_key, _message(
        checkpoint, key_id=key_id, sealed_at_utc=sealed_at_utc
    ), sha256).hexdigest()
    return DetachedJournalMac(
        checkpoint.checkpoint_id, checkpoint.store_id,
        key_id, sealed_at_utc, mac,
    )


def verify_detached_journal_mac(
    checkpoint: JournalCheckpoint, seal: DetachedJournalMac, *,
    verification_key: bytes, expected_key_id: str, expected_store_id: str,
):
    """Fail-closed cryptographic check; independent custody remains UNPROVEN."""
    if not isinstance(checkpoint, JournalCheckpoint) or not isinstance(seal, DetachedJournalMac):
        raise TypeError("Typed checkpoint and seal are both required")
    _require_key(verification_key)
    if (not isinstance(expected_key_id, str)
            or not _ID.fullmatch(expected_key_id)
            or seal.key_id != expected_key_id
            or checkpoint.store_id != expected_store_id
            or seal.store_id != checkpoint.store_id
            or seal.checkpoint_id != checkpoint.checkpoint_id
            or seal.sealed_at_utc < checkpoint.created_at_utc):
        raise ReferenceJournalCorrupt("Detached seal identity/time mismatch")
    correct = hmac.new(verification_key, _message(
        checkpoint, key_id=seal.key_id, sealed_at_utc=seal.sealed_at_utc
    ), sha256).hexdigest()
    if not hmac.compare_digest(correct, seal.mac_sha256):
        raise ReferenceJournalCorrupt("Detached checkpoint MAC mismatch")
    return checkpoint


def verify_authenticated_journal_backup(
    backup_path, checkpoint, seal, *,
    verification_key: bytes, expected_key_id: str, expected_store_id: str,
):
    """Opt-in wrapper: verify detached MAC BEFORE reading pinned backup."""
    verify_detached_journal_mac(
        checkpoint, seal, verification_key=verification_key,
        expected_key_id=expected_key_id, expected_store_id=expected_store_id,
    )
    return verify_journal_backup_against_pinned(
        backup_path, checkpoint, expected_store_id=expected_store_id
    )


def restore_authenticated_journal_backup(
    backup_path, destination, checkpoint, seal, *,
    verification_key: bytes, expected_key_id: str, expected_store_id: str,
):
    """Restore only after checking detached key custody seal + exact backup."""
    verify_authenticated_journal_backup(
        backup_path, checkpoint, seal,
        verification_key=verification_key, expected_key_id=expected_key_id,
        expected_store_id=expected_store_id,
    )
    return restore_journal_from_pinned(
        backup_path, destination, checkpoint, expected_store_id=expected_store_id
    )


def verify_authenticated_journal_prefix(
    store, checkpoint, seal, *,
    verification_key: bytes, expected_key_id: str, expected_store_id: str,
):
    verify_detached_journal_mac(
        checkpoint, seal, verification_key=verification_key,
        expected_key_id=expected_key_id, expected_store_id=expected_store_id,
    )
    return verify_journal_history_prefix(
        store, checkpoint, expected_store_id=expected_store_id
    )
