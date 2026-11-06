# Rights custody floor — CAS and independent recovery specification v0.1

**P0.30 / 2026-11-07. Status: PROPOSED; NOT_IMPLEMENTED; ALL OPERATIONAL DRILLS NOT_RUN.**

This is a concrete boundary for reviewing a future implementation of P0.29's `CustodyFloorStorePort`. It does not select a host or create an authorization path. P0.29 authority flags stay False even if a future store commits a floor.

## Threat model and separate control

A database transaction can prevent competing updates within one running database. It cannot detect an administrator restoring **all** that database's state to a mutually consistent older backup. A checksum/signature stored beside the backup has the same problem. P0.29 explicitly demonstrates complete-floor reset passing conditional integrity again.

This proposal requires two separately controlled planes before operational acceptance:

- **A — primary floor coordinator:** stores the exact current floor, pending transition and append-only transition/audit metadata. Engine/caller permissions cannot update a floor directly, enrol a root, clear a hold or restore its database.
- **B — independent high-water witness:** retains an authenticated, monotonic sequence of floor commitments outside A's restore/administrator domain. A's operators cannot delete, roll back or re-enrol B. B's key/identity and monotonic recovery boundary need independent verification; a second table/bucket under the same restore privileges is insufficient.

Detection below assumes B remains trustworthy/current when A is restored or compromised. Coordinated compromise/rollback of A, B and every external pin is **outside the guarantee**. Signed receipts alone do not make B nonrollbackable; its control and recovery procedures require actual evidence. No eligible A/B service or operator has been selected.

## Exact records and invariants

| Record | Required metadata | Invariant |
| --- | --- | --- |
| Enrolment | Anchor hash, authority policy/version, approved root fingerprint, opaque privately verified evidence references, independently approved initial floor | Missing state never auto-creates a bootstrap; root replacement requires separate recovery review |
| Current floor | Exact immutable P0.29 floor bytes/digest, generation, head serial, event sequence/tip, key epoch/registry tip, UTC, last challenge and sticky hold | Never lower a counter, rewrite an observed prefix, clear a hold or change anchor through ordinary CAS |
| Prepared transition | Opaque transaction ID, expected floor digest, exact proposed floor bytes/digest, verification/challenge receipt and state | One pending transition per anchor; transaction ID can only replay the same exact proposal |
| Witness receipt/state | Independent issuer/key reference, anchor, previous witness commitment, exact independently validated floor metadata/digest, next generation, transaction ID and observed UTC | Conditional update of the witness's own current commitment; no unsigned receipt, unrelated anchor or blind attestation of an arbitrary digest from A |
| Cancelled-transition fence | Anchor, transaction ID, expected digest and durable CANCELLED outcome authenticated by B | Late requests for that cancelled transaction cannot commit; A cannot infer cancellation from a timeout |
| Completed transition | Matching prepared record, authenticated B receipt and final floor; audit record persisted atomically with A's finalization | No success before A and B agree on the exact floor and transaction |

Records contain only approved nonsecret metadata. Original agreements, account identifiers, API secrets and OHLCV remain outside these records. Witness signature format/algorithm, enrolment, storage product and crypto implementation are **not specified as an existing vendor capability** and need a reviewed implementation contract.

## Commit order

All steps below are a proposed **external coordinator**. The current pure Python verifier does not perform them.

1. Authenticate the independently approved enrolment. Read A and B; both must refer to the same current floor commitment. Refuse pending, missing, corrupt, stale, divergent or unavailable state. Issue a new challenge bound to that exact retained floor using the approved clock/nonce issuer.
2. Verify the head, full event prefix and key registry with P0.29. Keep the exact `expected_floor_sha256` and `proposed_floor`. This is conditional integrity, with no permission grant.
3. In a durable A transaction, compare the current digest/generation and absence of pending work. Store a unique **PREPARED** transition containing the complete proposal and verification receipt. A's old floor remains retained; ordinary reads/authority decisions for that anchor now block. Do not overwrite a different pending proposal or silently recreate an enrolment row.
4. Submit the exact prepared transition and its verification evidence to B. B independently validates the canonical proposal, signatures under its independently enrolled root/policy, floor/prefix monotonicity, sticky hold, challenge and freshness using its approved clock. It retains the exact floor metadata needed for these checks; it must not trust a bare digest or A's success Boolean. B atomically compares its current commitment with the expected old one, checks the transaction is not fenced/cancelled, and records the new commitment plus transaction ID. Repeated same-ID/same-payload calls may return the same authenticated receipt; same ID with different bytes is a conflict. A timeout is an unknown outcome, not proof of failure.
5. In a durable A transaction, validate B's receipt and the still-matching prepared transition/old floor. Advance to the exact proposed floor, persist the witness receipt/audit metadata and mark **COMMITTED** atomically. Preserve the old immutable audit record. Never update B back to the old commitment if A finalization fails.
6. Read back authenticated A/B agreement before reporting commit success. If the process/response expired, retain the newer security floor but deny any time-sensitive authority decision and obtain a new head/challenge. Committing monotonic security evidence does not extend licence/head expiry.

There is **no claim of one atomic transaction across A and B**. The explicit pending state and reconciliation protocol are required because they can fail independently. Availability is sacrificed while evidence is uncertain; a stale/uncommitted floor never enables a read/cache/backtest operation.

## `CustodyFloorStorePort` result semantics for a future implementation

- `read_floor(anchor)` returns a floor only after authenticated witness agreement; pending/divergent/unavailable/missing state raises a typed failure and never bootstraps.
- `compare_and_swap(expected_digest, next_floor)` returns **True** only for a confirmed A/B commit of that exact transition. It returns **False** only for a known comparison conflict with no newly applied transition. An unknown/partial outcome raises and requires reconciliation; it must not be reported as a harmless False and retried with a different proposal.
- Same exact transition replay is resolved through its durable transaction/receipt. A fresh authority check still needs a new valid challenge against the committed floor. A caller-supplied Boolean or in-memory CAS does not satisfy the port's operational acceptance.

The existing Python protocol has no coordinator/transaction-ID implementation. Its signature is not evidence that these semantics are deployed. A concrete adapter may need a separately reviewed typed internal transaction interface; do not silently add it to a live path.

## Crash, restore and uncertainty handling

| Observed state | Required handling | Forbidden shortcut |
| --- | --- | --- |
| No prepared transition; A/B agree | Restart with a fresh challenge | Reuse an expired response |
| A PREPARED; B still old | Block normal access. Reconcile the exact transition with authenticated B; retry same valid proposal, or have B atomically record an irreversible cancellation fence for that transaction before A removes PREPARED. If B cannot prove/fence the outcome, remain blocked | Treat a timeout as proof B did nothing, or cancel only in A while a late B request can still commit |
| B advanced; A still PREPARED/old | Complete A from the retained exact prepared bytes and B receipt, or remain blocked if evidence is unavailable | Lower B or create a different proposal from the old floor |
| A/B committed; caller lost ACK | Resolve by exact durable transaction/receipt and readback; retain the new floor | Start from a new bootstrap or duplicate the semantic observation |
| A restored older; B ahead | Quarantine. Reconstruct only from retained exact transition/evidence matching B under independently reviewed recovery. Missing payload means blocked recovery | Restore B to match A or recreate an empty enrolment |
| A ahead of B; B missing/unavailable/corrupt | Block and investigate trust/recovery integrity | Trust A's local signature alone |
| Root/anchor changed, expired/compromised continuity key or incompatible floor schema | Separate authenticated recovery proposal preserving observed history and holds | Automatic root replacement, un-revoke or counter reset |
| Head expires during pending work | Preserve any committed newer floor, reconcile uncertain work, then refresh before any future authority decision | Roll back the floor to make old evidence usable |
| P0.29 reaches 128-event/16-epoch bound | Remain blocked until a reviewed authenticated checkpoint/compaction protocol exists | Truncate history or reset its sequence |

Application release rollback is independent of security-state rollback. A previous engine version must consume the current floor/history or stay denied if incompatible. No recovery here restores old market quotes as current data, erases audit history or releases a sticky suspension.

## Acceptance drills — SPECIFIED / NOT_RUN

| ID | Required external test | Current evidence |
| --- | --- | --- |
| CUST-DRILL-01 | Two competing real coordinators: at most one exact floor commit | NOT_RUN; P0.29 in-memory fixture is insufficient |
| CUST-DRILL-02 | Crash/restart at every A prepare, B witness, A finalize and ACK boundary | NOT_RUN |
| CUST-DRILL-03 | Lost B/A response, duplicate transaction and same-ID/different-payload rejection | NOT_RUN |
| CUST-DRILL-04 | Restore A to an old backup while B stays current: detection and denial | NOT_RUN |
| CUST-DRILL-05 | Attempts by A/engine administrators to delete/re-enrol/restore B | NOT_RUN; requires real control-plane review |
| CUST-DRILL-06 | Corrupt/missing floor or witness, clock rollback/expiry and prolonged partition | NOT_RUN |
| CUST-DRILL-07 | Key/root compromise recovery and sticky holds across engine rollback | NOT_RUN |
| CUST-DRILL-08 | Encrypted durable writes, access controls, audit retention and independently verified recovery evidence | NOT_RUN |
| CUST-DRILL-09 | Complete A+B+pin rollback threat review and explicit accepted limits | NOT_RUN; cannot be inferred from ordinary CAS |
| CUST-DRILL-10 | B rejects a forged/stale/regressing proposal from A; cancellation-vs-late-commit race cannot produce two outcomes | NOT_RUN |

A named service proposal, exact ownership/permission model, cost/region, independently verified source authority and user approval are prerequisites to implementing/deploying this design. No infrastructure, new trust root, private key, storage volume or external connection is created by this specification.
