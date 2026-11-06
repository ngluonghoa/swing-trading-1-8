# GĐ4/P0.19 — Read-only POSIX storage preflight and detached checkpoint custody MAC

Date: 2026-11-06 · **ENGINEERING PARTIAL / SYNTHETIC CI**.

The SSI/DNSE reference journal remains ONE SQLite database with provider-isolated diagnostic records. Its data-bearing cache is opt-in with P0.17 external licensing/security assertions; P0.18 snapshots remain **METADATA_ONLY**, never copying source quote-cache OHLCV. This milestone **does not deploy a production runtime, custodial service or key**, and has no permission to retain unlicensed data.

## Local storage permission preflight

Code: `src/swing_trading/reference_storage_preflight.py`. `inspect_reference_storage(root, database, expected_uid=...)` performs an **inspection only** on a caller-supplied existing POSIX SQLite journal path:
- Require absolute paths without `..`, database below the explicit private root; reject use of filesystem root.
- Inspect each path segment with `lstat`, reject symlink traversal, inspect private root and nested directories for exact owner UID and `0700` mode. Detect Git repositories in the ancestry and deny storing SQLite beneath them.
- Verify database is a regular owner-only `0600` file with exactly one hard link, and check any present `-wal`, `-shm`, `-journal` SQLite sidecar under the same policy.
- Return explicit reasons in `StoragePreflight.issues`; `require_reference_storage` raises `UnsafeReferenceStorage` on any violation. It never fixes ownership/mode or creates files.

`local_permissions_pass` is **NOT** deployment approval. Three flags remain `host_volume_approved=False`, `provider_retention_approved=False`, `production_authorized=False` regardless of local POSIX success. A check can race a concurrent filesystem change (TOCTOU); there is no openat/O_NOFOLLOW/dirfd enforcement during SQLite operations, and no independently checked ACLs, POSIX capabilities, SELinux/AppArmor, encrypted filesystem, remote filesystem semantics, hardware, monitoring or operational retention. This preflight is opt-in library code; it does NOT yet wrap all journal read/write operations or constitute a guaranteed sandbox.

## Detached metadata-checkpoint MAC integration contract

Code: `src/swing_trading/reference_checkpoint_mac.py`. The P0.18 `JournalCheckpoint` can be serialized and **sent to a separately authorized key custodian** who could call `create_candidate_detached_mac(checkpoint, signing_key, key_id, sealed_at_utc)`. The helper uses HMAC-SHA256 over a domain-separated canonical payload containing the **entire** checkpoint, key ID and seal time, and produces a strict-schema `DetachedJournalMac` without ever writing the secret.

The consumer must obtain **both** the independently supplied checkpoint manifest and detached seal, plus its trusted key material and expected store/key IDs, by an approved external mechanism. `verify_detached_journal_mac` compares HMAC in constant time; opt-in `verify_authenticated_journal_backup`, `restore_authenticated_journal_backup`, `verify_authenticated_journal_prefix` refuse to use a mismatched seal before proceeding with P0.18 backup chain/file SHA256, no-overwrite restore and prefix validation.

**Important security limitation:** HMAC is a *symmetric message authentication code*, not a digital signature. Everyone who knows the verification secret can forge a new MAC. Running signing and verification on the same compromised host or storing the key next to a backup does **NOT** provide independent custody or external signing proof. No actual external custodian/key service, key rotation/revocation, attested timestamp, signature, public-key verification, privileged protection or separate approval authority has been integrated. No secrets should be checked into the repo or stored in Handoff.

## Verification

`tests/test_reference_runtime_custody.py` checks: owner-only files/directories, weak permissions, symlinks, hard links, Git-tree and out-of-root/missing paths, SQLite sidecars, wrong UID, detached seal authenticity/identity/time/digest, altered checkpoint, wrong secret and key ID, malformed envelope, corrupted backup, no-overwrite restore and historical prefix. Run `python -m unittest discover -s tests -v` in CI on Python 3.11 / 3.12. Synthetic fixture PASS does NOT prove the eventual host or separate custodian.

## OPEN / NEXT GĐ4/P0.20

- Choose/approve **where** the SQLite DB runs and independently assess filesystem ACL, owner, encryption, non-POSIX policies, reliable storage semantics, network backup, RTO/RPO, secure expiry/erasure, disaster recovery, source provider rights and off-site custody.
- If a true independently verifiable *signature* is required, implement approved Ed25519/public-key verification with keys isolated in an external custodial service or trusted signing facility; this HMAC prototype is not that.
- Integrate host-bound authenticated MCP read-only callbacks, verify SSI/DNSE provider-specific retention, first-known timestamps, adjustment and native intraday M1/M5/M15; keep B5 24 numeric calibration slots/real historical BT/OOS and trade simulator blocked until independently evidenced.
- `UI-1.0 DESIGN_LOCKED`, CK2, FX2, Scanner and MOCHI unchanged. No orders or live signal.
