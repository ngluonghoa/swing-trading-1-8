# GĐ4/P0.29 — Custodied rights-head freshness and anti-rollback **conditional preview**

**Date:** 2026-11-07 (Asia/Ho_Chi_Minh). **OFFLINE / CRYPTOGRAPHIC PREVIEW ONLY; NO REAL PROVIDER ENROLMENT OR DATA LICENCE.** This P0.29 implementation was independently authored from authorized current `main` after §27.56; it reuses **none** of the abandoned ChatGPT Work P0.29–F1 branches, commits, code or handoffs.

## Problem and boundary

P0.28 verifies a synthetic Ed25519 rights-event chain against a **caller-supplied** event signer, public fingerprint, chain head and timestamp. This is conditional integrity only; one can supply a fresh self-made key and head, or substitute an earlier *self-consistent* revoked-then-forgotten history. P0.29 adds a **separately signed custody-head claim** bound to a previous floor, account digest and event signer, with dual-signed key-rotation checks. These remain **untrusted caller-provided claims**: there is no authenticated external vendor trust root, protected monotonic high-watermark store, live revocation feed or legal rights approval.

**Source files:** `src/swing_trading/provider_head_custody.py`, `tests/test_provider_head_custody.py`, `tests/test_provider_head_custody_integration.py`. The new module has no network, private key generation/signing, persisted state, market data, automatic polling, session data, broker orders or live cache access. The tests use synthetic throwaway keys and invented SHA256 fingerprints only.

## Exact preflight, deliberately narrow

1. `CustodyProduct` is a strict typed product/endpoint identity: SSI connected intraday, SSI FastConnect native OHLC, DNSE connected DAY, DNSE signed OpenAPI OHLC, and **VCBS connected D1**. The VCBS product is represented for future onboarding, but P0.28's `BarProduct` does **not** contain it; it cannot inherit an SSI/DNSE signed event chain or authorization.
2. `ClaimedCustodianKey`: expected external **custodian** Ed25519 public key, key ID, fingerprint, epoch and opaque `EVID-` enrollment reference. Both key-origin and independent enrollment remain **hard FALSE**. Never place a private key, API secret, user account identifier or licensing contract in the repo, tests or Handoff.
3. `SignedCustodyHead`: a **different signing key** from the P0.28 rights-event signer, exact product, account-binding SHA256 claim, event signer key ID+SHA256, sequence and chain tip SHA256, issued/expiry timestamps, custody key ID+epoch, and signature over a new domain-separated canonical serialization. A validity interval over five minutes, malformed signatures, stale/future heads and mismatched products/keys are rejected. The five-minute budget is a **local clock policy only**, not evidence of a provider current head.
4. `ClaimedMonotonicFloor`: externally **claimed** previous sequence, tip, head issuer key ID+fingerprint, epoch, last issuance time, observed time and account-binding hash. The auditor blocks decreasing sequence, the same-sequence different-tip fork, decreasing issuance time, key downgrade/epoch skip, wrong account and same-epoch key substitution. This detects rollback **only relative to the supplied floor**; an attacker replacing both floor and head can still pass. There is NO durable protected floor writer or proof of monotonicity across restarts.
5. `DualSignedKeyRotation`: for exactly one-epoch transition, require both **old and new** custodian keys to sign the same canonical transition bound to the previous key fingerprint, new key fingerprint, previous floor sequence+tip+account digest, product, nonce and transition time. All keys/rotation documents are caller-supplied; this is not a provider-endorsed key rollover or attested custody operation. No rollback to older key/epoch or silent key substitution.
6. Optional integration with the *existing* P0.28 verifier calls `verify_pinned_rights_event_chain` on the **complete** signed tuple (bounded by P0.28), requires exact product/event key fingerprint/sequence/tip/issuance binding to the separate custody head, and checks that the entire P0.28 signed history retains the **original chain hash at the claimed floor sequence**. This catches a re-signed alternate history with greater sequence. Signed `PROVIDER_REVOKE` / `SECURITY_SUSPEND` remain sticky holds even after a later synthetic candidate grant.
7. `ConditionalHeadAudit` exposes **cryptographic checks against provided claims** and P0.28's nonactionable event state. `vendor_key_origin_verified`, `fresh_revocation_stream_authenticated`, `anti_rollback_across_restarts_verified`, `rights_to_read_or_cache`, `market_indicators_allowed`, `historical_backtest_allowed`, `trading_actionable` are ALL **hard FALSE**. `require_authenticated_provider_rights()` always raises. Do not wire this result into C1/C1B/C1C as a privilege elevation.

## Test and acceptance boundaries

New synthetic tests exercise valid conditional signatures, P0.28 complete prefix and sticky signed hold, malicious fork/truncation, same-sequence conflict, sequence rollback, key substitution and downgrade, epoch skip, dual-rotation proof tampering, stale/future head and floor, account-binding mutation, type/schema/nonce/sig rejection, VCBS separation, and continuous denial of all live data permissions. CI must pass on Python 3.11 and 3.12. **Test PASS is NOT an independent custodian/vendor signature**.

| Gate | Status |
| --- | --- |
| Conditional Ed25519 head and optional P0.28 prefix verification | ENGINEERING/SYNTHETIC ONLY |
| Relative sequence/tip floor anti-rollback | ENGINEERING/SYNTHETIC ONLY |
| Dual-signed rotation verification | ENGINEERING/SYNTHETIC ONLY |
| Independent vendor key ownership proof for SSI/DNSE/VCBS | NOT VERIFIED |
| Externally authenticated current revocation head and continuity feed | NOT VERIFIED |
| Protected monotonic trusted storage across restarts and hosts | NOT IMPLEMENTED |
| Provider-approved account/product/scope/retention/expiry/corporate-action rights | NOT VERIFIED |
| Live M1/M5/M15 source, licensed persistent L1–L5, real BT/OOS | NOT AUTHORIZED / NOT RUN |
| Source grants, trading signals or orders | HARD DISABLED |

## External prerequisites — do not fabricate

Vendor compliance and independent custodian review must establish the actual **account-scoped grant, signer identity, enrolled key fingerprints and revocation publication authority**, evidence of who can rotate/revoke keys, key-compromise recovery and emergency HOLD, an independently signed **current** head with first-known/monotonic journal consistency, durable protected floor/high-watermark, cross-replica anti-equivocation witnesses, and fail-closed fetch/cache/purge infrastructure. These must be reviewed separately for SSI MCP/SSI FastConnect V2/V3, DNSE MCP/DNSE OpenAPI, VCBS MCP and each API product. Passing a supplied screenshot, public portal page, synthetic signed head or invented `EVID-` marker must never satisfy that gate.

## Next work

Proceed with **P0.29b external evidence checklist and host-bound monotonic floor design** if vendor/custodian artefacts become available, while C2 can continue with **read-only source-capability and quality evaluation** without storing raw vendor OHLCV. Do not implement pretend source licences, wire simulated rights to real data or deploy a production reader. Preserve UI v1.0 DESIGN_LOCKED; no changes to SHORT/SWING, B1–B8/S1–S8, eight-stage pipeline, FX2, CK2, Scanner or MOCHI. Canonical native Google Drive Handoff is authoritative and source snapshots must be synced only after source CI.
