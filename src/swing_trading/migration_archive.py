"""P0.4B: explicit raw-source-byte bridge from legacy migration to P0.4 audit.

Engineering-only. No serialization of legacy Python objects, provider
authentication, SSI entitlement checks, or promotion to VERIFIED.
"""
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256

from .durable_evidence import EvidenceItem, EvidenceStore, State
from .legacy_migration import LegacyMigrationEnvelope, MigrationBatchResult, migrate_batch
from .market_data import CanonicalCandle as LegacyCandle
from .replay import require_utc


@dataclass(frozen=True)
class RawSourceBinding:
    """Caller attests which exact upstream bytes belong to one migration row."""
    row_reference: str
    source_record_id: str
    source_snapshot_id: str
    raw_bytes: bytes = field(repr=False)
    declared_sha256: str

    def __post_init__(self):
        if not all(isinstance(x, str) and x.strip() for x in (
            self.row_reference, self.source_record_id, self.source_snapshot_id
        )):
            raise ValueError("Raw evidence source and row identifiers are required")
        if type(self.raw_bytes) is not bytes:
            raise TypeError("Exact source bytes are required, never repr/pickle")
        if (not isinstance(self.declared_sha256, str)
                or len(self.declared_sha256) != 64
                or any(c not in "0123456789abcdef" for c in self.declared_sha256)):
            raise ValueError("Invalid lowercase SHA-256")
        if sha256(self.raw_bytes).hexdigest() != self.declared_sha256:
            raise ValueError("Raw source bytes disagree with declared SHA-256")


@dataclass(frozen=True)
class ArchivedRowReceipt:
    row_reference: str
    source_record_id: str
    raw_sha256: str
    state: State
    reason_code: str


@dataclass(frozen=True)
class ArchivedMigrationBatch:
    batch_id: str
    migration: MigrationBatchResult = field(repr=False)
    receipts: tuple[ArchivedRowReceipt, ...]
    record_count: int
    chain_tip_sha256: str


def archive_migration_batch(
    store: EvidenceStore,
    batch_id: str,
    envelopes: tuple[LegacyMigrationEnvelope, ...],
    raw_sources: tuple[RawSourceBinding, ...],
    as_of_utc: datetime,
    *,
    expected_tip_sha256: str | None = None,
) -> ArchivedMigrationBatch:
    """Preflight all input and migration outcomes, then commit one atomic batch.

    A missing, duplicate, mismatched or non-original byte source fails the
    ENTIRE batch before write. No fallback reconstruction from OHLC.
    """
    if not isinstance(store, EvidenceStore):
        raise TypeError("Expected EvidenceStore")
    require_utc(as_of_utc)
    if not isinstance(envelopes, tuple) or not isinstance(raw_sources, tuple):
        raise TypeError("Both input collections must be immutable tuples")
    if not envelopes or len(envelopes) != len(raw_sources) or len(envelopes) > 1000:
        raise ValueError("Require nonempty, equal-length bounded tuple inputs")
    if any(not isinstance(e, LegacyMigrationEnvelope) for e in envelopes):
        raise TypeError("Expected LegacyMigrationEnvelope")
    if any(not isinstance(s, RawSourceBinding) for s in raw_sources):
        raise TypeError("Expected RawSourceBinding")
    refs = [e.row_reference for e in envelopes]
    if len(refs) != len(set(refs)):
        raise ValueError("Duplicate row refs cannot be archived unambiguously")
    for envelope, source in zip(envelopes, raw_sources):
        if (envelope.row_reference != source.row_reference
                or envelope.source_snapshot_id != source.source_snapshot_id):
            raise ValueError("Raw-to-migration row/snapshot binding differs")
        legacy = envelope.legacy
        if isinstance(legacy, LegacyCandle):
            if legacy.observation_key.source_record_id != source.source_record_id:
                raise ValueError("Raw source ID is not the legacy observation ID")
            if legacy.revision.raw_digest_sha256 != source.declared_sha256:
                raise ValueError("Legacy raw digest is not the supplied original bytes")

    migration = migrate_batch(envelopes, as_of_utc)
    if migration.attempted_count != len(raw_sources):
        raise ValueError("Migration input/outcome counts are not equal")
    quarantined = {q.row_reference: q for q in migration.quarantined}
    if len(quarantined) != len(migration.quarantined):
        raise ValueError("Nonunique quarantine identity")
    migrated_refs = {e.row_reference for e in envelopes if e.row_reference not in quarantined}
    if len(migrated_refs) != len(migration.migrated):
        raise ValueError("Migration outcomes cannot be reconciled by row reference")
    entries = []
    receipts = []
    for source in raw_sources:
        q = quarantined.get(source.row_reference)
        state = State.QUARANTINED if q is not None else State.STAGED_UNVERIFIED
        reason = q.reason_code if q is not None else "LEGACY_EVIDENCE_UNVERIFIED"
        entries.append(EvidenceItem(
            source.row_reference, source.source_record_id, source.raw_bytes,
            source.declared_sha256, state, reason,
        ))
        receipts.append(ArchivedRowReceipt(
            source.row_reference, source.source_record_id,
            source.declared_sha256, state, reason,
        ))
    total, tip = store.append_batch(
        batch_id, tuple(entries), as_of_utc,
        expected_tip_sha256=expected_tip_sha256,
    )
    if total < len(entries):
        raise RuntimeError("Archive count cannot be less than committed batch")
    return ArchivedMigrationBatch(batch_id, migration, tuple(receipts), total, tip)
