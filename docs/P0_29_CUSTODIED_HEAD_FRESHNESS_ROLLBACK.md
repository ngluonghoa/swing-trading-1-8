# GĐ4/P0.29 — Conditional custody-head freshness, rollback and key provenance

**Date:** 2026-11-07 (Asia/Ho_Chi_Minh). **Engineering only, offline.** This milestone defines and tests a verification boundary. No real provider/custodian root, independent host, durable floor, account-specific grant or live current-head service has been verified or deployed.

## Reconciled starting point

- GitHub main `0e9d1e97ea0bf3e652af6c9eb8d4fcbe6df48892`, after [source PR #67](https://github.com/ngluonghoa/swing-trading-1-8/pull/67) and [Handoff PR #68](https://github.com/ngluonghoa/swing-trading-1-8/pull/68).
- Full canonical Google Drive Handoff §27.52 and GitHub `00_MASTER_HANDOFF.txt` matched exactly: **315,861 Unicode characters**, including the exported BOM/CRLF. No newer open PR at intake.
- Unlike the older Handoff's pending note, [post-merge main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42258673786) was independently checked: both `unittest (3.11)` and `unittest (3.12)` succeeded. Local baseline also passed **589 tests**.
- P0.28 proves event-prefix integrity under a caller-supplied key/head. A caller can replace the whole key/head set or omit a revocation beyond the supplied head. The original restrictions remain in force.

## New contract, not a source licence

`provider_head_custody.py` contains verifier-only immutable contracts. It has no signing API, random-nonce issuer, key enrolment, networking, filesystem/SQLite access, live callback, credential handling, account number or market-data retention.

| Contract | What is checked | What remains unverified |
| --- | --- | --- |
| `ClaimedCustodyAnchor` | Exact product, custodian/root IDs, 32-byte public key/fingerprint, opaque provenance evidence and distinct operator/reviewer **claims**; the entire anchor is hashed | Actual vendor key owner, real reviewer identity, account binding and organizational independence |
| `SignedLedgerKeyEpoch` | Contiguous registry from genesis; root countersignature, new-key proof of possession and previous-key continuity on rotation, all with separate signing domains; unique key IDs/fingerprints, publication/expiry and exact activation sequence | Whether a vendor or independent reviewer actually approved those keys; the signatures do not prove separation of duties |
| `HeadFreshnessChallenge` | Exact anchor and prior-floor digest, opaque challenge ID, 128-bit nonce, UTC issue/expiry, fixed maximum 60-second lifetime | Secure nonce issuance, a trustworthy host clock, authenticated transport or source availability |
| `SignedCustodianHead` | Root signature over challenge/floor/product, serial, complete registry tip, active ledger key/fingerprint, event count/tip, suspension and issue/expiry; response must be issued after its challenge and remain valid inside its lifetime | Whether the responding party is genuinely independent or has observed the latest complete vendor stream |
| `ClaimedCustodyFloor` | Retained serial, event sequence/tip, registry epoch/tip, UTC and sticky hold; bound to anchor and exact challenge; next generation proposed only after all checks | Durable, independent, nonrollbackable storage or atomic commit |
| `CustodyFloorStorePort` | Required external read/CAS interface and failure contract | No implementation, host, storage volume, recovery drill or operational concurrency proof is shipped |

The 60-second challenge/head bound is a local security contract, **not provider-certified freshness** and not approval of the separate trading TTL/cooldown policy. Schema and signing domains are `P0.29/.../v1`; P0.28 event bytes stay unchanged. Histories are bounded to **128 events and 16 key epochs**. At a limit the verifier blocks; it never truncates history, resets a floor or invents a compaction checkpoint.

## Shared event verification and rotation

P0.28 and P0.29 now use one private `_verify_rights_prefix` integrity loop. P0.28 still resolves one claimed key; P0.29 resolves each event using the checked key-epoch schedule. Both preserve exact sequence/previous hash, canonical Ed25519 signatures, unique event IDs/nonces, no future publication, expiry and irreversible revoke/suspend precedence.

Normal rotation requires signatures from the claimed custodian root, old ledger key and new ledger key over role-separated canonical bytes. Registry epochs and activation sequences strictly advance. A new key cannot sign an old prefix; an old key cannot sign after its replacement's activation sequence. An expired historical key may still verify events published during its valid period, but an expired old key cannot authorize a new rotation. Root and ledger public keys must differ. All previously observed registry and event prefixes must remain byte-identical through their retained tips. History is never re-signed to make a rotation pass.

There is no automatic recovery from a compromised/expired continuity key or root replacement. Such recovery needs separate externally authenticated evidence, preservation of the existing anti-rollback state and a reviewed protocol. No release/un-revoke event or automatic right promotion is added.

## Anti-rollback and commit boundary

The verifier requires the caller's explicit floor; `None`, an unrelated anchor, an old serial/epoch/sequence, same-sequence fork, longer rewritten prefix, stale response, wrong challenge or clock regression is rejected. A refresh of an unchanged event tip is allowed only under a new challenge and strictly higher head serial. A prior observed hold or authenticated-conditional service suspension remains sticky across refreshes/rotation and subsequent candidate claims.

On success the result contains **only a proposal**: `expected_floor_sha256` and `proposed_floor`. It does not update storage. An approved future host must read its independent retained floor, issue a fresh challenge bound to it, verify the response and history, then atomically/durably compare-and-swap the **whole** floor plus consumed challenge. A lost CAS race, missing/corrupt floor, unavailable service, expiry before an authority decision or storage failure must block/retry with a new read and challenge. An in-memory test model demonstrates competing proposals; that is not an operational storage or crash-recovery test.

**Critical limitation, explicitly tested:** replacing the entire external floor with a bootstrap and obtaining a matching response can pass conditional integrity again. Stateless code cannot detect rollback of all its inputs. Therefore `durable_rollback_protection_verified` and `current_revocation_freshness_verified` always stay **False**. The explicit engineering bootstrap helper must never be used to recover a lost production floor. GitHub/Drive snapshots, repository rollback and P0.20 journal checkpoint signatures are not independently retained provider-custody state.

Every actual authority property remains hardcoded **False**, including provider key ownership, custodian independence, durable rollback protection, current revocation freshness, read/cache permission, backtest, production and actionable status. `require_custodied_rights_authorization` always raises `PermissionError`, including for a fabricated report or after a successful fixture CAS. Crypto validity is never an executable licence.

## External custody decision

[ADR-0003](ADR_0003_EXTERNAL_RIGHTS_CUSTODIAN.md) defines the required evidence and host boundary. **No actual host/custodian has been selected or approved.** Selecting one without provider key ownership, account-specific rights and separately controlled persistent state would misrepresent the threat model. No existing GitHub connection, Google Doc, ChatGPT process, test key or MOCHI is enrolled as a trust service.

## Validation and rollback

The full suite adds **78 synthetic unit/security tests** to the 589-test baseline: **667 tests**. Cases include fresh refresh/append/rotation through three keys, preserved history, expired historical keys, changed root/provenance, wrong-domain/key/signature/role, cross-product substitution, fresh-signed old head and fork, nonce/ID replay, exact expiry, missing floor, key-epoch rollback, prefix rewrite, holds, competing CAS proposals and the complete-floor-reset limitation. [Source PR #69](https://github.com/ngluonghoa/swing-trading-1-8/pull/69) merged as `70b35f317b84e4e096ac9e70c17d4d75551b7a73` only after [exact-head PR CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42265844712) passed. That run and [post-merge main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42265987261) were independently checked, including logs: **667/667 tests on EACH Python 3.11 and 3.12**. No real vendor identity, grant, newest revocation, historical bars, source entitlement or trading efficacy was tested.

This is an additive engineering increment with unchanged P0.28 signed-event bytes and no production schema migration. Source rollback uses a new reviewed revert PR and CI; it is not a stable production release or permission to deploy. An eventual engine rollback must **preserve current custody floor/holds/key history**. If an older build cannot interpret them, keep access blocked; never restore an older floor/market snapshot to regain permission.

After source CI/merge, the original native Google Drive Handoff was updated in place to §27.53, including three current front-matter paragraphs. All other 933 original paragraphs and their order were preserved on readback. The complete 322,689-character export is copied in the separate documentation sync, with SHA-256 in HANDOFF_LATEST_POINTER. Documentation CI and exact Drive-versus-main equality are checked before closing the milestone.

**Next GĐ4/P0.30:** obtain/review a nonsecret external custodian/provider provenance dossier and an independently controlled floor/atomic recovery design before any live trust integration. If evidence is absent, keep the gate blocked and document the specific missing evidence; do not invent a host, request credentials or add another self-approval layer. All source licence/retention, native M1/M5/M15, source time/calendar/adjustment, B5 calibration/detector, fill/cost/T+2 and real BT/OOS gates remain open. UI-1.0, CK2/FX2/Scanner/MOCHI remain untouched; no orders.
