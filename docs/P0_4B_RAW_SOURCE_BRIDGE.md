# GĐ4/P0.4B — Explicit raw-byte lineage into the local evidence store

**Status: engineering fixtures only, NOT a deployed production bridge.** Based on Google Drive Master Handoff §27.25, Data Contract 05, and the versioned P0.3/P0.4 code.

## Implemented

- `migration_archive.py` introduces immutable `RawSourceBinding`: exact caller-supplied upstream `bytes`, supplied lowercase SHA-256, row reference, source-record ID and source-snapshot ID. Raw bytes are excluded from the object's default text representation. No object serialization, pickle, OHLC reconstruction or remote API is performed.
- `archive_migration_batch()` accepts equal-length tuples of P0.3 `LegacyMigrationEnvelope` and raw-byte bindings in the same explicit order. Before any write it checks row ID and snapshot mapping, raw SHA-256, and (for typed legacy candles) exact source-record ID and the original revision's raw digest. Duplicate row refs, missing rows, reordered/mismatched input or altered raw digest fail closed for the whole batch.
- The bridge runs the existing `migrate_batch()` *without changing its data-quality decisions*. A migrated row remains `STAGED_UNVERIFIED` with reason `LEGACY_EVIDENCE_UNVERIFIED`; a rejected row becomes `QUARANTINED` with the original P0.3 reason. Future-known revisions and unknown lifecycle remain quarantined. No state named VERIFIED is possible.
- Only after every row is mapped to exactly one outcome does the bridge call P0.4 `EvidenceStore.append_batch()` once. SQLite commits the complete set atomically, checks the chain and SHA-256, refuses duplicate batch IDs, and optionally requires a supplied expected chain tip.
- Returns counts, audit row IDs, reasons, raw hashes, states and the chain tip; never returns reconstructed raw bytes in its receipt. The store's verified-read path returns the exact original bytes upon request.

## Synthetic acceptance tests

`tests/test_migration_archive.py` tests staging, quarantine, future-revision as-of behavior, mixed outcomes, exact binary byte backup/restore, invalid digest, bad source snapshot/record/row mapping, absent/swapped entries, duplicate identifiers, stale writer and duplicate batch ID, malformed legacy objects and UTC input requirements.

## What this **does not** establish

- A caller may falsely assert which original bytes correspond to a legacy object. A matching digest is necessary but not proof of the economic content or original provider authenticity. A separately reviewed, versioned source parser and entitlement verification are required before accepting the mapping for actual data.
- For a malformed legacy object, the source ID and snapshot ID come **only** from the caller; the outcome remains quarantined. There is no implicit claim of source identity verification.
- No real SSI bytes were ingested, no persistent production filesystem/cloud was provisioned, and no independent, signed chain checkpoints, off-site backup or disaster-recovery drill have been completed. SQLite tests run against disposable fixture directories in CI.
- In-memory P0.3 original objects still exist; the bridge only persists explicitly supplied bytes, not arbitrary Python objects or their exact serialization.
- Full B01–B08 source parity, calendar/auction policy, corporate-action adjustments, live engine, 16 executable detectors, BT-01..16, OOS and real performance validation remain **OPEN/NOT_RUN**.

## Next

P0.4C / P0.5: select and approve a real persistent store and permissions, add independent provenance and recoverability checks, then verify SSI endpoint/entitlement/timestamps with strict quarantine. Do not modify UI-1.0, MOCHI, CK2/FX2/Scanner without separate authorization.
