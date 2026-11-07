# H1 — Module substitution, engineering versioning, and CI

Status: ENGINEERING TEST FOUNDATION ONLY. Baseline: PR #102, post-C3C rollback commit c02cc76f079d163b81d17f2a926c215893044ca6, with file contents equal to post-C4B PR #99.

## Objective and scope

Maintain Swing Trading 1.8 as a modular monolith with explicit ports/adapters so modules can be modified, added, replaced, removed, updated, tested and rolled back without unnoticed cross-dependency. Preserve C3B, C4A, C4B, UI-1.0 DESIGN_LOCKED, SHORT/SWING, B1–B8/S1–S8 and eight audit stages. Never touch Forex Trading, CK2, Scanner or MOCHI in this work. Do not reinstate old C3C.

## H1 versioning and reproducible engineering snapshots

- Package remains 0.0.1, not a production release. The package and runtime version must match.
- Version module contracts independently as MAJOR.MINOR.PATCH; an adapter must match exact contract ID and source scope, with matching major and supplied minor/patch no older than required.
- EngineeringSnapshot pins commit SHA, package version, dependency-lock digest, contract digest, docs digest, CI run reference and UTC capture clock. It serializes canonically to a deterministic SHA-256 fingerprint. It can NEVER set a signed release, LKG, licensed-data, deployment or trading authorization flag.
- A successful CI run does not create a Git tag, release, migration receipt, provider entitlement or last-known-good candidate. No Git tag or Release currently exists. Before a true RC, require locked dependency versions, immutable build output, independently approved source rights, signed release identity, verified schema N/N−1 migration and operational restore drill.

## Module contract tests — highest-priority requirement

The new engineering_contracts.py provides PortDescriptor and strict check_port / require_compatible_port. The structural check does not call an adapter and cannot certify its behavior or security. Each port is keyed by an explicit provider or namespace.

The tests/test_engineering_module_contracts.py consumer suite checks:

- Three distinct replacement source stand-ins (SSI, DNSE, VCBS). Exact scope can be injected; silent scope substitution fails.
- Same-major upgrades, breaking major or older minor/patch, duplicate methods, missing operations/non-callables, invalid metadata and false privilege elevation.
- Swapping two injected causal event sources under BacktestHarness; future-known revisions stay invisible; untyped events fail closed.
- Swapping fake registry behavior while all unimplemented B/S zones remain UNVERIFIED.
- C3B fake serialized partition determinism, provider/indicator namespace isolation, corruption and OPEN bar denial; C3B/C4A real-transport guards remain disabled.
- A domain dependency boundary via AST for contracts, market_data, causal, replay, engine and backtest: disallow provider/SQLite/http/cloud imports and dependency cycles inside this core set.

Adding a real adapter requires a separate declared request/response contract, provider source-rights/retention proof, venue/timeframe/data semantics, session/calendar and source-revision policies, independent negative tests, and any required N/N−1 migration. Structural method names alone do NOT qualify a vendor source.

| Change type | Before PR merge | Before real operation |
| --- | --- | --- |
| Replace SSI/DNSE/VCBS | Scope-specific ABI and mock error/correction/parity fixtures | Licensed source, comparable market data and authenticated current revocation |
| Add provider | Separate namespace, no implicit router promotion | Contract/product qualification and real provider acceptance |
| Replace cache/Drive backend | Digest/manifest replay, cold/warm/dirty parity, corrupt/revision checks | Authenticated binary transport, CAS/fencing, independent witness, KMS and approved retention |
| Upgrade indicator/detector | Causal first-known replay, parameter fingerprints, affected cache invalidation | Calibrated real historical simulation and untouched OOS |
| Remove module | No consumers/old artifacts become unsafe, explicit deprecation contract | Approved compatibility and state migration/retirement |
| Replace report renderer | UI-1.0 model invariants and snapshot contract | Renderer/golden tests and separately reviewed visual changes |

## CI and package checks

Retain the full unit-test jobs on Python 3.11 and 3.12. The additional engineering-contracts job runs pinned ruff lint (E4/E7/E9/F for the new files), pip check, all H1 contract tests, a standalone wheel build and a fresh venv install/import from outside the source tree. This proves the engineering package is installable and the tests do not depend on editable source layout.

Not yet implemented or certified: full-project strict type checking, comprehensive security/SBOM scanning, reproducible signed production builds, mandatory branch rules, true end-to-end provider integration, renderer golden tests, real external rights validation, backtest/OOS, live backend or release rollback.

## Git governance and rollback

- Use scoped PRs, reviewed diff, CI and explicit approvals; do not force-reset main. Keep discarded code reachable in Git history for audit.
- R1–R7 deployment/profile rollback is a DESIGN + OFFLINE PREFLIGHT, not operational LKG restoration. An EngineeringSnapshot is not an approved full execution profile.
- GitHub reported main protected=false; its rulesets endpoint was not available under the present plan/permission. CI is therefore procedural, not a technologically enforced required-status gate. Independently enable branch protection when capability permits.
- Google Drive Master Handoff and Data Contract are authoritative design sources; sync their point-in-time GitHub snapshots after source PR merge and verify exact equality.

## Acceptance and next milestone

H1 engineering scope passes only when the full original suite stays green on Python 3.11 and 3.12, new H1 job is green, main contains the merged source, and Google Drive/GitHub handoffs are synchronized. No trading/production release gate is met by these results.

After H1, reimplement C3C from post-C4B using harmless synthetic file readback, then plan C3D native chunks separately. P0.29c external custody/rights and C2C real-session data qualification remain blocked.
