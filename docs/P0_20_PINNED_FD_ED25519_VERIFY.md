# GĐ4/P0.20 — Pinned read-only SQLite FDs and Ed25519 checkpoint verification

Date: 2026-11-06. **Engineering-only synthetic tests, not a deployed data or trading service.**

## Pinned FD inspection — what is protected and what is not

`src/swing_trading/reference_pinned_fd.py` provides `pin_reference_sqlite_files(root, database, expected_uid)`: a POSIX-only, read-only context manager. It opens path segments through directory file descriptors using `O_NOFOLLOW|O_DIRECTORY`, pins the actual DB inode and any existing `-wal/-shm/-journal` sidecars, checks owner UID/0700 private directories/0600 regular single-link files, rejects Git ancestry and validates the 16-byte SQLite header. `verify_path_names()` rechecks named entries against the opened dev/inode and detects later directory/file swaps, new sidecars or Git markers. The context closes all opened FDs on exit. It does not repair filesystem permissions or open SSI/DNSE feeds.

**Security boundary:** This protects the pinned *inspection* and detects some path swaps. It DOES NOT guarantee `sqlite3.connect(path)` reuses the same inode or prevent races between a separate check and subsequent SQLite path-based access; it does NOT implement production-safe SQLite read/write handles or coherent WAL snapshotting through raw file bytes. A malicious local process able to mutate parent directories, ACLs or mount points remains a deployment blocker. POSIX/NFS semantics, encryption, ACLs, sandboxing, lock integrity and actual host approval are not verified.

## Ed25519 detached signature verification

`src/swing_trading/reference_checkpoint_signature.py` supports **verifier-only** externally produced Ed25519 signatures over an explicit domain-separated canonical payload binding the full P0.18 `JournalCheckpoint`, external key ID and signed-at UTC time. It uses vetted `cryptography` primitives installed via the optional `pip install -e ".[custody]"` extra. The default runtime package still does not require cryptography; a missing verifier dependency fails closed.

`DetachedJournalSignature` uses a strict, versioned JSON schema and canonical base64 of a 64-byte Ed25519 signature; `verify_detached_journal_signature` requires a caller-supplied 32-byte Ed25519 public key **and a preapproved SHA256 public-key fingerprint**, explicit expected key ID and expected store ID. Invalid/mismatched signatures, store/key/clock identity, untrusted public key and altered checkpoint fields fail closed. Opt-in wrappers `verify_signed_journal_backup`, `restore_signed_journal_backup`, and `verify_signed_journal_prefix` validate signature before running P0.18 backup integrity, new-path restore and historical prefix checks.

**Trust boundary:** This code NEVER generates, provisions, persists or exports real keys, and it has no signing service. Signing occurs only inside synthetic tests. External public-key fingerprint provenance, signer independence, key rotation/revocation, signed timestamp authority, audit approvals, and independent third-party custody all remain UNVERIFIED. Signature validity merely proves a holder of the corresponding private key signed the canonical manifest; it DOES NOT establish licensed prices, quality, approved storage, market-source entitlement, or profitability.

## Data and project invariants

SSI and DNSE remain logical provider partitions inside **one SQLite reference store**. Quote cache remains opt-in and nonactionable under P0.17, not approved by any P0.20 function. P0.18 metadata-only backups continue to exclude OHLCV, and Ed25519 verification does not revive expired quotes. No new MCP credentials, storage volume, background schedule or broker orders. No modifications to UI-1.0 DESIGN_LOCKED, CK2, FX2, Scanner or MOCHI.

CI (Python 3.11 and 3.12) installs the optional verifier dependency and runs `python -m unittest discover -s tests -v`. Synthetic tests cover pinned file/parent inode changes, sidecar set changes, unsafe modes, symlinks/hardlinks, Git ancestry, invalid SQLite headers, public-key fingerprint pinning, signature tampering, cross-store key/clock binding and signed no-overwrite restore.

## NEXT GĐ4/P0.21 — remain fail closed

1. Obtain explicit approval for host+volume, SQLite native access model (descriptor-safe design with WAL handling), encryption/ACL/lock semantics and independent signer trust-anchor provisioning.
2. Add a host-bound read-only MCP transport harness only after permissions are reviewed. Never equate GitHub CI or local Python fixtures to a continuously active Plugin.
3. Verify SSI/DNSE historical licences, first-known timestamps, session calendars, corporate actions and native M1/M5/M15 before calibrating B5 SHORT/SWING slots or attempting real BT/OOS.
4. Preserve no-market-order policy and locked UI.
