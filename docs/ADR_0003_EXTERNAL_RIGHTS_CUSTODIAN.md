# ADR-0003 — External provider-key provenance and independently retained custody state

**Date:** 2026-11-07 (Asia/Ho_Chi_Minh).
**Status:** Engineering boundary specified/tested in P0.29; **actual provider root, host and custodian NOT_SELECTED / NOT_VERIFIED / NOT_DEPLOYED**. No operational authorization or source right is granted.

## Decision

Separate verification of metadata signatures from the external evidence that makes a key authoritative. A private repository, connected market-data MCP, native Google Doc, user assertion, test fixture and self-consistent fingerprint are insufficient to enrol a provider key or attest a fresh complete revocation stream.

P0.29 ships only a pure verification contract plus an external `CustodyFloorStorePort` interface. It does not select a cloud vendor, create infrastructure, contact SSI/DNSE, collect credentials, sign licence events or use MOCHI. Its root/actor/evidence/floor inputs are explicitly **claims**, with every operational permission denied. Conditional cross-signatures prove key continuity, not independent human/organizational approval.

An actual custodian must be selected only after the following evidence is verified out of band and its concrete implementation reviewed. Contracts, account identifiers and private credentials remain outside GitHub/Handoff; only approved opaque evidence references, decisions and metadata belong there.

| Required gate | Evidence needed before approval | Current state |
| --- | --- | --- |
| Provider/account/product rights | Account-bound vendor approval, exact product/version/terms, six P0.26 scopes, historical window, expiry/revocation and raw/derived retention/deletion/backup permissions | NOT_VERIFIED |
| Key ownership/enrolment | Independently authenticated provider/custodian identity, exact public-key fingerprint/algorithm, issuer/provenance/version/expiry, authenticated revocation contact and designated reviewers | NOT_VERIFIED |
| Custodian independence | Named real operator and separate authorized reviewer; documented separation of control from engine code, request caller and repository/backup administrators | NOT_SELECTED |
| Current-head authority | Authenticated, available source of complete ordered vendor events; nonce-bound signed current-head response; trusted UTC and expiry; source outage/partition/emergency suspension behavior | NOT_DEPLOYED |
| Monotonic state and atomicity | Independently controlled persistent serial/sequence/registry/floor, durable serializable CAS, access controls/encryption, consumed-challenge handling, concurrency/crash/restart and rollback-resistant backup/restore evidence | NOT_DEPLOYED / NOT_RUN |
| Rotation and compromise recovery | Normal old/new/root signature path; separate reviewed root/compromised-key recovery preserving floors, event history and sticky holds; no silent rebootstrap or automatic reinstatement | CONTRACT_ONLY / RECOVERY_OPEN |
| Approved host integration | Explicit host/storage/transport approval, independently verified read-only native API and account/product binding; no authority decision on an expired response or uncommitted floor | NOT_APPROVED |

No current evidence establishes an eligible actual service. The next milestone must review concrete external evidence or state what is missing, rather than designating an existing connected tool as the custodian. Host/service selection and any deployment are significant decisions requiring user approval with a concrete reviewable proposal.

## Failure and rollback rules

Missing/corrupt retained state, unavailable authority, stale challenge/head, conflicting CAS, suspicious key transition, lost key or incompatible schema must leave rights closed. Restore of application code or journal metadata must never lower the independently retained custody high-water marks. A root change cannot silently bypass the old floor; a lost floor cannot be treated as an empty new ledger. Recovery requires independently authenticated evidence and review, not a test key or a repository snapshot.

No authority, high-water store or real recovery drill exists yet. Synthetic verification/CAS tests establish engineering behavior only. Provider-source quality/licensing, approved SQLite WAL/VFS/ACL/encryption/erasure, B5 executable calibration, trade simulator and historical BT/OOS remain separate blockers. UI-1.0 stays locked and other trading projects/devices are unchanged.
