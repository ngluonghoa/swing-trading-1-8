# GĐ4/P0.4C — Independent evidence checkpoints and verified recovery

**Status:** Python engineering implementation with synthetic-only tests, 2026-11-06.
Source decisions: Google Drive Master Handoff §27.26; original P0.4/P0.4B contract.
**Nothing here constitutes a production deployment, external attestation or SSI validation.**

## What was built

- `src/swing_trading/evidence_checkpoint.py` provides typed `EvidenceCheckpoint` containing stable checkpoint/store IDs, UTC capture time, record count, audit chain tip, **whole backup file SHA-256**, and schema version.
- A candidate checkpoint is produced by creating a *NEW* consistent SQLite backup using the established P0.4 online-backup API, verifying the internal record chain, and hashing the resulting backup file. Its canonical JSON can be transferred to an **independent, access-controlled custodian** for review and pinning.
- A separately supplied pinned checkpoint can be used to validate an existing backup before restore. A mismatch of file checksum, chain, record count or expected store identifier fails closed. Restores target a new path and refuse overwrite.
- A pinned historical checkpoint can validate the **prefix** of a larger live store. The complete chain and prefix check execute in one consistent SQLite read transaction, making it possible to detect accidental tail truncation or rewriting relative to an independently held old tip.
- All byte hashing is streamed in 1 MiB chunks. The helpers do not serialize raw records, leak their bytes in report JSON or alter the `UNVERIFIED`/`QUARANTINED` source quality states.

## Threat model and limits

- This is **tamper-evident only if the approved checkpoint is held independently** from the data store and protected from modification. A checkpoint read from the same compromised DB, or simply regenerated after tampering, provides NO assurance. No signing, HSM, independent approval workflow or remote custody is provided.
- `store_id` is a caller-asserted namespace in checkpoint metadata, NOT a cryptographic ID embedded into the SQLite genesis record. External identity/ownership validation is required before trusting it.
- An approved old checkpoint authenticates its historical prefix, but **does not authenticate subsequently appended events**. New data need a later independently pinned checkpoint.
- This prototype makes no claim of data confidentiality or permissions: a real persistent filesystem, access controls, encryption at rest, independent off-site backup, monitoring, disaster-recovery exercises and operational acceptance remain OPEN.
- `file_sha256` confirms binary consistency, not correctness of SSI provider prices, calendars, timestamps, usage entitlement, corporate actions, auction semantics or detector profitability. A malicious authorized writer able to replace both database and checkpoint could forge a consistent pair.
- Local POSIX/SQLite behavior is covered by CI fixtures, not verified on the user's eventual production host. No MOCHI or other remote machine was accessed; no broker or live signal output was added.

## Engineering tests

`tests/test_evidence_checkpoint.py` covers synthetic empty/nonempty snapshots, binary bytes restored under externally supplied metadata, truncated/re-written chains, wrong store/digest/tip, corrupted SQLite backup, schema/UTC validation, historical chain extension, and refusal to overwrite backups.

Run `python -m unittest discover -s tests -v` on Python 3.11/3.12. Success is **ENGINE_FIXTURE_TESTED** only.

## Next deployment/SSI prerequisites

1. User approves a persistent runtime and storage volume outside the Git repository. Validate ACL, least-privilege access, encryption and retention without introducing broker credentials into source control.
2. Design independent custody/signature for periodically pinned checkpoints and a restore/rollback drill on that runtime.
3. Verify SSI source-specific entitlement, exact source bytes, endpoint timestamp meaning, available history and market calendar under blockers B01–B08.
4. Continue Backtest/Signal Engine shared-domain work. The first historical backtest may start with **one tested detector** only after licensed source and realistic fill/cost/settlement evidence; do not wait for all 16 detectors.

UI v1.0 remains DESIGN_LOCKED. CK2/FX2/Scanner are unchanged. MOCHI backup is deferred.
