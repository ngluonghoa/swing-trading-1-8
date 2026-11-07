# GĐ4/P0.29b — External trust onboarding and witnessed monotonic-floor host plan

**2026-11-07 — OFFLINE ENGINEERING / SYNTHETIC ONLY.** Parent: [P0.29a signed head](P0_29_CUSTODIED_RIGHTS_HEAD_PREVIEW.md), [P0.28 rights prefix](P0_28_PINNED_RIGHTS_EVENT_CHAIN.md). No licensed source access, vendor-key enrollment, approved storage or permission elevation. This work is independently authored on top of canonical GitHub `main`, not copied from abandoned ChatGPT Work P0.29–F1 branches.

## Goal and boundary

P0.29a conditionally checks an Ed25519 custodian-signed head relative to a **caller-supplied** prior floor. Its replay resistance disappears when the caller/host can replace **both** the current checkpoint and the prior floor. P0.29b specifies the **external** onboarding and host requirements, plus an **offline, metadata-only** journal/witness fixture to demonstrate the failure mode and strict denial behavior. The fixture is **not** a production monotonic counter, host security check, externally signed witness, revocation service or legal grant. No actual SSI/DNSE/VCBS market data is fetched or stored.

### What is implemented

- `src/swing_trading/provider_custody_host_plan.py` exposes typed `EvidenceRole` and `HostControl` inventories, nonsecret evidence/actor IDs, per-product scope, expiry/recorded time, and mandatory separation of six claimed review actors. It rejects cross-product claims, duplicate roles, reused evidence/actors, future/expired role records, and incomplete/malformed inputs. Each claim still has `independently_authenticated=False` or `verified_on_host=False`, even if all checklist boxes are marked.
- `inspect_external_onboarding` lists missing roles and security controls while **never** promoting a complete packet into an approved trust root, legal source grant, licensed retention, trading, or real historical backtest. Missing-role and control reports are actionable to a human reviewer, **not** to the trading engine.
- `FixtureFloorRecord` and `append_fixture_floor` construct a domain-separated, SHA256-linked **metadata-only** reference sequence from P0.29a `ClaimedMonotonicFloor`. It binds the *exact* provider product, opaque account-binding digest, custody key ID+digest+epoch, signed-rights chain sequence/tip, UTC issued/observed time, prior record and checkpoint index. It rejects sequence rollback, same-sequence fork, out-of-order timestamps, account/provider substitution, same-epoch key substitution and **all rotation**, even if P0.29a could conditionally verify dual signatures: key rotation must be separately authenticated and approved in a future design.
- `ClaimedIndependentAnchor` holds an **externally claimed** expected sequence/index and digest. `inspect_fixture_floor_history` validates a bounded complete digest chain and compares the final checkpoint to that anchor, detecting truncated/replayed/reordered/modified fixture histories **only if the anchor stays independently protected**. The code never contacts or validates an independent witness; users can forge/replay **both** the local file and the claimed anchor. No filesystem writer or host enrollment API ships.
- **59 new Python `unittest` synthetic tests** cover positive reference flows, no-op/rollback/fork, key/epoch/account/provider isolation, corrupt in-memory object, exact witness comparison, local JSON file serialize/restart/rollback simulation and deliberate dual-replay counterexample. `require_external_trust` always raises; all report properties for vendor keys, external witness, cross-restart anti-rollback, host authorization, data retention and trading are **hard FALSE**.

## Six independent onboarding reviews — documents never imply approval

| Separate review role | Required externally verified evidence | Engineering state |
| --- | --- | --- |
| Provider key issuer | Vendor-issued signer identity, product and account binding, authenticated chain-of-trust and key compromise procedure | NOT VERIFIED |
| Independent head custodian | Out-of-band signed CURRENT head, complete revocation stream, publication cadence and duplicate/audit receipts | NOT VERIFIED |
| Account rights reviewer | Approved contract/product ID, read/derive/retain/backtest/OOS scopes, account binding, expiry, market-data terms | NOT VERIFIED |
| Independent floor witness | Immutable high-watermark receipt, authenticated delivery path, anti-replay clock and durable off-host counter | NOT VERIFIED |
| Storage security reviewer | OS/host owner, physical/logical access, encryption/ACL, backup/restore/incident controls and audit | NOT VERIFIED |
| Incident revocation owner | Emergency DENY, compromised key isolation, fresh revoke publication and mandated data purge evidence | NOT VERIFIED |

One actor cannot self-attest multiple review roles in this checklist. Actual independent identity verification is not performed by the code and cannot be inferred from distinct opaque IDs alone.

## Nine protected-host controls — architecture/acceptance, not deployed

| Control | Verification required outside fixture |
| --- | --- |
| INDEPENDENT_WITNESS_ANCHOR | Witness service account independent from cache/ChatGPT/GitHub/Drive operator; signed receipt and authenticated source |
| IMMUTABLE_MONOTONIC_COUNTER | Atomic append/high-watermark protection using independent ledger/HSM/KMS or other reviewed durable anti-rollback primitive |
| AUTHENTICATED_VENDOR_KEY_ENROLLMENT | Vendor trust-root/issuer certification, product/account scope and revocation/rotation source |
| ATOMIC_FSYNC_AND_LOCKING | Crash-safe write ordering, transaction boundaries, fsync parent and concurrent-writer fencing |
| NO_SYMLINK_OR_REPARSE | fd/path binding, immutable inode/FS validation and TOCTOU mitigation; SQLite path-opening still needs separate review |
| RESTRICTED_ACL_AND_ENCRYPTION | Scoped host identities, protected data-at-rest/in-flight, secret isolation, retention and key management |
| BACKUP_RESTORE_ROLLBACK_CHECK | Old snapshot restore MUST fail against independently held newer witness; backup alone must never reset entitlement state |
| CLOCK_AND_REVOCATION_MONITORING | Authenticated time/head freshness and detection of missing/new revocations (5-minute local staleness is insufficient) |
| EMERGENCY_DENY_AND_PURGE | Immediate stop of source reads/derived writes after revoked/expired grant, audited purge and incident escalation |

### Crash recovery and rotation runbook (DESIGN ONLY)

1. Obtain independently authenticated provider/account scope and custodian key enrollment **outside this repository**. If none, enter `NO_SOURCE_AUTHORITY` and deny all reads/cache/BT/orders.
2. Obtain an independently signed and fresh head with complete revocation history, and a protected witness anchor. Caller-supplied key/fingerprint/clock is never enough.
3. Verify P0.28 signed event prefix and P0.29a custodian-signed head/rotation **without** trusting a caller-generated enrollment. Retain sticky revoke/hold.
4. Under reviewed single-writer locking, atomically commit the new monotonic floor; obtain immutable off-host witness for the same event/index/sequence/tip and bind both to an approved account/product identity. Crash between writes must remain fail-closed pending reconciliation.
5. On restart/restore/backup replay, independently read both journal and witness. Reject stale, forked, missing, mismatched or unknown witness; do not reconstruct an 'approved' head from only local disk.
6. For vendor key rotation, require independent vendor-endorsed enrollment, dual-signature continuity, prior witness, explicit 1-epoch advance, approved incident controls and independent witness after rotation; local fixture intentionally denies rotation.
7. Emergency revocation/invalid grant: enter safe/deny state, stop all authorized live data operations, isolate/purge per contractual terms, retain metadata-only forensic evidence under reviewed policy. Do not silently use another MCP.

## Acceptance status and next work

| Gate | Status |
| --- | --- |
| Typed external onboarding evidence inventory, no self-approval | SYNTHETIC TESTED |
| Metadata floor linkage/replay with separately held claimed witness | SYNTHETIC TESTED |
| Deliberate attacker replaces both local record and anchor | **UNDETECTABLE IN FIXTURE** — shown in test |
| Vendor/account trust-root and legally binding source permissions SSI/DNSE/VCBS | BLOCKED / NO INDEPENDENT EVIDENCE |
| Immutable host-backed floor, signed independent witness and crash-safe atomic protocol | DESIGN ONLY / NOT DEPLOYED |
| Real current revocation feed, compromised-key recovery and independent key rotation | DESIGN ONLY / NOT DEPLOYED |
| C2 production MCP transport, licensed L1–L5 cache, authentic market minute bars | BLOCKED / NOT DEPLOYED |
| Live indicator signals/backtest/OOS/trading, R1–R7 production rollback | HARD DISABLED / NOT RUN |

**Next:** P0.29c or source-rights external procurement/review should obtain real independently authenticated vendor/account metadata and a genuinely separate protected head-floor witness. In parallel C2 may prepare **read-only** provider capability/parity diagnostics without treating successful MCP calls as storage rights. Preserve UI v1.0 DESIGN_LOCKED, SHORT/SWING, 16 B/S, eight-stage audit and SSI/DNSE/VCBS source isolation. No changes to CK 2.0, Forex, Scanner, MOCHI or released Work code.
