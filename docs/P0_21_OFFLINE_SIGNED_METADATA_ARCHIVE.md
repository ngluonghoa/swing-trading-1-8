# GĐ4/P0.21 — Signed offline metadata-only archive reader (pinned-FD + in-memory SQLite)

Date: 2026-11-06. **Engineering-only, no production host / licensed market-data runtime.**

## Concrete problem solved

P0.20 can inspect a SQLite inode through POSIX `O_NOFOLLOW` FDs, but the P0.17/P0.18 path-based `sqlite3.connect(path)` still reopens filenames and sidecars. It is incorrect to claim that the pin protects the **later** SQLite open. P0.21 therefore implements a narrower, actually descriptor-bound verifier for **standalone, offline, signed P0.18 metadata-only backup archives**, rather than falsely declaring the live journal safe.

Code: `src/swing_trading/reference_offline_verified_archive.py`.

`verify_offline_signed_metadata_archive(root, archive, checkpoint, signature, *, public_key_raw, expected_public_key_sha256, expected_key_id, expected_store_id, expected_uid=None, max_archive_bytes=64MiB)`:

1. First require P0.20 **valid Ed25519 signature** for all immutable P0.18 `JournalCheckpoint` fields using an independently obtained/pinned 32-byte public key, SHA256 fingerprint, explicit key ID and store ID. No private key/signing service is shipped. Validity of those trust inputs is NOT independently proven by this code.
2. Open the offline backup using P0.20 `pin_reference_sqlite_files`: POSIX dirfd + `O_NOFOLLOW`, private 0700 directories and 0600 regular single-link file, matching UID, no Git tree or symlinks. **Refuse any `-wal/-shm/-journal` sidecar**, because this is a standalone P0.18 logical metadata archive, not a live WAL database.
3. Enforce a bounded file size (4096 bytes to 64MiB), read exact bytes using **`os.pread` from the pinned file descriptor**, check whole-file SHA256 against the signed manifest, check that it has not been truncated, and recheck pinned names/inodes.
4. `sqlite3.connect(":memory:")` only, deserialize the already verified bytes, set read-only `PRAGMA query_only=ON`, run P0.17 SQLite integrity, chain, schema, foreign-key and append-only-trigger checks. Assert **zero cache quote rows**, match signed journal count and chain tip. Refuse any malformed/corrupt database; recheck file identity before return.
5. Return only an immutable `OfflineMetadataReport` containing check result and counts/digests; always `production_authorized=False`, `market_data_certified=False`, `historical_backtest_qualified=False`, `actionable=False`. No SQLite connection, raw provider bytes or price is exposed.

This is a fail-closed archive-verification **read path**, not a writer, not a production SQLite database opening method, not a cache feed and not an import of live MCP. No code in the module connects to brokerage endpoints, stores source credentials or schedules activities. The old P0.17 path-based **live journal** implementation remains engineering-only, not production-safe. In-memory SQLite verification does not establish lawful source retention, nor does a valid signature prove external trustee approval.

## Synthetic test matrix

`tests/test_reference_offline_verified_archive.py` verifies signed snapshot acceptance, integrity without caching OHLCV, one SQLite archive with SSI+DNSE metadata, wrong/missing trust key or fingerprint, modified signed manifest/backup bytes, malformed/prohibited live journal carrying quote cache even if signed, WAL/SHM/journal sidecar rejection, file mode/link/symlink and missing path checks, explicit size bound, and no production/actionable elevation. Python 3.11 and 3.12 CI must pass before merge.

## What remains OPEN and next GĐ4/P0.22

- No approved production runtime/volume/independent Ed25519 signer and out-of-band pinned fingerprint; no approved source-data rights, no hosted MCP runtime. A signed offline archive is NOT a full live backup or a path-safe SQLite writer.
- P0.17 live `ReferenceJournal._connection()` and P0.18 restore still rely on path-based SQLite; in-place SQLite/WAL on untrusted/mutable directories needs a reviewed native SQLite VFS/locked host storage strategy. **Do not patch this with a preflight-then-connect claim.**
- P0.21 imposes a 64MiB per-archive bound. Larger verified archives need an explicitly reviewed streaming-validation design; this is not a blanket size limit for live market-data caches.
- Native SSI/DNSE M1/M5/M15 historic entitlement/coverage and source timestamp/adjustment provenance, SSI B01–B08, B5 SHORT/SWING calibration, full simulator costs/settlement, historical BT/OOS remain blocked.
- Locked UI-1.0, CK 2.0, FX 2.0, Scanner and MOCHI unchanged, no brokerage orders.
