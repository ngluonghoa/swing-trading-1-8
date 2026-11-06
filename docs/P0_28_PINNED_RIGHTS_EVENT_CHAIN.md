# GĐ4/P0.28 — Pinned Ed25519 source-rights event chain verifier (NO authorization)

**Date:** 2026-11-06 (Asia/Ho_Chi_Minh). Engineering-only verifier and synthetic crypto tests; no provider licence, live client, credentials, independent trust service, or production revocation enforcement.

## Narrow security problem

P0.27 can collect claimed `EVID-/ATST-/ACTR-/HOLD-` review markers, but those come from a caller and provide **no cryptographic provenance or complete revocation history**. P0.28 adds a separate verification path for an explicitly supplied, signed **event prefix** plus an externally supplied pinned head and public-key fingerprint. This demonstrates conditional tamper/replay detection and **does not create provider entitlement**.

New: `src/swing_trading/provider_signed_event_chain.py`. It is independent of the P0.20 Ed25519 *journal checkpoint* signature, which cannot validate a provider licence.

## Cryptographically checked parts

- `SignedRightsEvent` uses strict schema/version and domain-separated canonical bytes `SwingTrading1.8/P0.28/RightsEvent/Ed25519/v1`, exact `BarProduct`, `sequence`, `previous_sha256`, opaque `EVNT-/EVID-/KEY-` IDs, 32-hex nonce, published/effective UTC times, optional candidate expiry and typed six P0.26 scope claims. Event kinds: `GRANT_CANDIDATE`, `PROVIDER_REVOKE`, `SECURITY_SUSPEND`. There is **no approval, key-enrolment, un-revoke, release, renewal or signing API**; `GRANT_CANDIDATE` is a **signed claim only**, not evidence of an actual grant.
- Each event carries exactly one canonical Ed25519 signature. The verifier uses `cryptography` Ed25519, and a separately supplied pinned **32-byte public key** with an exact SHA-256 fingerprint and key ID. The SHA-256 link to the previous event includes a distinct chain domain, the signed canonical payload and signature bytes. A changed scope/identity/timestamp/nonce, invalid signature or broken order/previous digest fails.
- `ClaimedExternalLedgerPin` explicitly specifies product, opaque head/key ID, fingerprint, pinned expected end sequence, pinned tail digest and pinned UTC time. The verifier requires an exact complete sequence from genesis to that **claimed** head, maximum 128 events, strictly monotone publication dates, unique event IDs/nonces and a head supplied no more than 5 minutes old. This is a **five-minute local stale-head rejection policy**, NOT provider authenticated freshness.
- Signed revocation or security suspension is sticky **within the supplied signed prefix**: even a later signed candidate cannot release an earlier hold. Candidate expiry at the check time closes that status. A signed event prefix without holds yields only `SIGNED_CANDIDATE_UNAUTHORIZED`, or `SIGNED_CANDIDATE_EXPIRED`; a hold yields `SIGNED_HOLD_UNAUTHORIZED`.
- `RightsChainVerification.signature_integrity_verified=True` means Ed25519 integrity was checked **against the supplied key and pinned head**. The flags `signer_authority_verified`, `head_custody_independently_verified`, `current_revocation_freshness_verified`, `permission_to_read_or_cache`, `backtest_allowed` and `actionable` are all **hardcoded FALSE**. `require_rights_chain_authorization` always raises.

**Important adversarial boundary:** A caller can generate its own Ed25519 key and a self-consistent fingerprint/head. That would pass *conditional signature integrity* and still prove **nothing** about SSI, DNSE, the user's account, legal source rights or the completeness of revocations after the pinned head. Neither a pinned head from GitHub/Drive nor signed synthetic fixtures can prove live provider status. Live authorization would need separately audited provenance of key ownership, independent key enrollment/rotation, protected signed current-head publication with monotonic sequencing, authenticated account and product binding, external approved licence terms, live revocation freshness, operational emergency suspension, and host-enforced denial and purge.

## Synthetic CI coverage

`tests/test_provider_signed_event_chain.py` creates fixture-only Ed25519 keys, signs local synthetic candidate/revoke/suspend events, and verifies valid-prefix integrity and negative cases: forged public key/fingerprint, signature tamper, mismatched/cross-provider key, old/future pin, dropped/truncated/reordered events, wrong tip, changed scope, replayed nonce/ID, invalid clocks and schema, expired candidate, hold precedence even after later candidate, malformed base64, non-authorizable report, bounded lists and no leaked secret/price data. The synthetic private test key must **never** be reused as provider trust material. Run the full Python 3.11/3.12 CI; no real data or market backtest.

## OPEN and GĐ4/P0.29

1. Provider-issued trust roots, independent signer identity, ledger head custodian and authenticated revocation stream do **NOT** exist for this project. P0.28 explicitly does not elevate any access right.
2. No actual API enrolment/rights for SSI FastConnect Data V2/V3 or DNSE OpenAPI `/price/ohlc`; no source-native licensed historical M1/M5/M15, first-known/revision coverage, reliable exchange calendar/corporate actions, or validated pagination.
3. No approved persistent host/SQLite WAL VFS, access controls/encryption and audited purge; P0.17 path-based runtime and offline metadata-only P0.18 backups remain engineering-only. No OHLCV cached in this milestone.
4. No B5 SHORT/SWING 24 numerical calibration settings, executable detector, fills/slippage/fees/tax/T+2 simulator or historical BT/OOS results.

**GĐ4/P0.29:** define a *trusted-head freshness / rollback-prevention interface* with out-of-band authenticator and independent key-rotation/revocation evidence, but do not fake vendor keys or introduce executable permission flags. Focus on barriers to actual source legitimacy, not merely adding more synthetic tests. UI-1.0 DESIGN_LOCKED, CK2/FX2/Scanner/MOCHI unchanged and no broker orders.
