# GĐ4/P0.4 — Local evidence store (engineering prototype)

**Not a deployed cloud service.** The canonical sources are Google Drive Master Handoff §27.24 and Data Contract 05 §§2–5.

Implemented:

- `durable_evidence.py`: explicit raw bytes, supplied SHA-256, source-record identity, reason, and state; only `STAGED_UNVERIFIED` or `QUARANTINED`. No data is marked VERIFIED.
- SQLite on a caller-selected local persistent directory, outside the repository. `WAL`, `synchronous=FULL`, single-transaction batch commits, immutable update/delete triggers, per-record SHA-256 and linked audit receipts. The verification routine checks byte hashes, chain, SQLite integrity and batch counts.
- `evidence_recovery.py`: consistent SQLite snapshot backup, validation, and new-file restore. Atomic publication requires ordinary POSIX filesystem semantics; existing destination is never overwritten.
- Synthetic tests: exact byte roundtrip, duplicate/invalid states, stale audit-head rejection, interrupted batch rollback, backup/restore and no-overwrite behavior.

**Limits:** This is local testable code, not remote storage, cloud sync or a production persistence deployment. A hash chain helps detect accidental corruption but cannot defeat privileged tampering without an independent signed checkpoint. SQLite volume permissions, encryption, monitoring, off-site backup and operational recovery remain unverified. Do not put raw SSI files or SQLite databases into GitHub.

The P0.3 legacy converter still holds original objects in memory. There is **no automatic adapter** from objects to original raw bytes: this module requires the caller to supply exact bytes, and never pickles, guesses data, validates SSI entitlements, or upgrades data quality. Integration and live data validation remain pending.

**Next:** P0.4B controlled migration-to-byte mapping, approved persistent storage destination/restore drill and endpoint-specific SSI B01–B08 evidence. Trading rules, original UI-1.0, CK2, FX2, Scanner and MOCHI remain unchanged; no real historical backtest/OOS is claimed.
