# GĐ4 / Release Foundation F1 — engineering manifest and rollback preflight

**Date:** 2026-11-07, Asia/Ho_Chi_Minh. **Status:** offline engineering implementation; operational release/rollback NOT_IMPLEMENTED / NOT_RUN.

## Why this work can proceed

The current P0.31 **provider-rights branch remains BLOCKED_PENDING_EXTERNAL_INPUT** under Handoff §27.54. The user's instruction to continue does not supply a grant, authorize a provider enquiry or choose a host. No change is made to that gate.

Handoff §25.1–25.8 already requires independently versioned components, immutable artifact identity and safe rollback as part of the core foundation. Master Spec REQ-REL-01..12 / SPEC-T10 and Data Contract §18's version/persistence boundaries record the same backlog. No release-manifest/version-registry implementation existed in `src/` at intake. F1 implements a bounded **independent foundation slice** of that approved work; it is not another rights/custodian review stage or a redefinition of P0.31.

Starting main: `daadde680ec2dac042b5a55b368f2320fba7a03b`, after PR #72; no newer/open PR at intake. Fresh Handoff §27.54 matched main exactly: 330,411 characters, SHA-256 `af85fcfa4e16d7c48c177f61522db9ae2ee937f8a8c4e91ab5aa5549bb7bc1b2`. Main CI `42269777409` passed both Python versions; local baseline 667 tests passed.

## Manifest v1 and artifact verification

`src/swing_trading/release_manifest.py` adds immutable, machine-readable engineering metadata:

- Exact release/artifact IDs, canonical SemVer identity, pinned 40-hex source revision, UTC creation time, artifact SHA-256 and byte length. A moving branch/path/URL cannot replace the source pin.
- Exactly eight independently versioned/hash-pinned components: ENGINE, RULE_SET, PARAMETER_SET, DATA_SCHEMA, PROVIDER_ADAPTER, MARKET_CALENDAR, CACHE_FORMAT and UI_TEMPLATE. Material is explicitly SOURCE, DESIGN_SPEC or SYNTHETIC_FIXTURE; hashing a specification does not make its rules executable/calibrated.
- UI_TEMPLATE is pinned to **UI-1.0 / DESIGN_SPEC**. This identifies the locked design snapshot; it does not claim a renderer or golden UI test exists. Preflight checks its hash against an explicit supplied locked-spec pin.
- Explicit, bounded lists of exact schema fingerprints readable by the candidate for **market data, audit history, custody floor and position context**. There is no wildcard/implicit default/automatic migration. The manifest must declare its own market schema readable.
- Build-recipe, dependency-**specification** and test-suite fingerprints plus an optional exact rollback-target **manifest digest**. Dependency-spec identity is not a resolved dependency lock or reproducible build proof.

`EngineeringReleaseManifest.from_canonical_bytes` accepts only the exact v1 canonical ASCII JSON shape with `ENGINEERING_CANDIDATE` scope. It rejects missing/unknown/nested duplicate fields, unsupported format/scope, noncanonical encoding, mutable/unbounded input, malformed pins/UTC and placeholder zero hashes. The in-memory limits are 64 KiB for manifest bytes and 8 MiB for engineering artifact bytes; these are parser bounds, not approved production capacity/SLO.

`verify_engineering_bundle` requires an explicit expected manifest digest and verifies the exact artifact bytes/length against the pinned manifest. Changing both artifact and manifest still fails against an unchanged expected pin. Verification **does not establish who provisioned the pin**, prove all declared component hashes correspond to a built artifact, verify a source commit with GitHub, or make a candidate approved/stable. Full pin provenance and actual build/content inventory are later gates.

There is no signing, file extraction/read/write, subprocess, network, SQLite, source adapter, deployment, promotion or permission API. A raw artifact is opaque bytes and is never executed or restored. No production approver/approval timestamp/ACTIVE field can be smuggled into this v1 format.

## Offline rollback preflight

`src/swing_trading/rollback_preflight.py` verifies current/target engineering bundles and an explicit supplied digest of immutable **current retained-state metadata**. That metadata contains all four state-format/snapshot pins, observation UTC and the current release-cache namespace. Missing position context is not inferred to mean flat/no position.

The planner checks:

| Check | Failure result |
| --- | --- |
| Artifact/manifest/retained-state identity | Reject input before returning a plan |
| Target equals current manifest's exact rollback-target digest, distinct release ID and valid chronology | BLOCKED findings; no version-label shortcut |
| Current and target readers both declare every retained state format | BLOCKED for the exact unreadable state kind; no restore/downgrade fallback |
| Current/target UI design hashes match the supplied UI-1.0 spec pin | BLOCKED on drift |
| Retained cache namespace matches the current manifest | BLOCKED on wrong/stale release-cache metadata |

For example, if the current custody floor uses schema B and the old candidate only declares schema A, the plan blocks. It never drops the floor, clears a hold or restores an older custody snapshot so the old code can run. A declared compatible reader is still metadata; actual reader/migration compatibility must be tested before any operational switch.

The returned immutable plan preserves **the exact current market-data, audit, custody and position snapshot pins**, and identifies the **whole target component set**. Target parameters are not mixed with current-engine parameters. Cache namespaces include release/build and every component/recipe/dependency/test fingerprint; any changed pinned input/version partitions the namespace. A rollback plan marks the separate target namespace as requiring rebuild/revalidation rather than making old caches current. No cache is actually deleted, rebuilt or read.

Results are only `BLOCKED` or `METADATA_COMPATIBLE_REVIEW_REQUIRED`. There is no execute method, active-pointer update, stable registry, production authorization or claim that the supplied retained snapshot is independently fresh/trusted. A successful metadata plan cannot bypass source rights, host/custody freshness, schema reader acceptance, position reconciliation, realistic simulator, release qualification or manual operational approval.

## Traceability — do not close full acceptance prematurely

| Existing requirement | Implemented/tested slice | Still open |
| --- | --- | --- |
| REL-01 / SPEC-T10 | Canonical engineering manifest, source/component/artifact pins and byte-tamper rejection | Reproducible builder, resolved dependency lock, actual content inventory/build provenance, immutable distribution artifact and release approval |
| REL-02 | Explicit previous engineering target and complete target-version set in a plan | Actual last-known-good production baseline, restoration/switch and smoke evidence |
| REL-05 | Plan preserves exact current protected-state metadata | Real data/audit/custody/position preservation during deployment/recovery |
| REL-06 | Locked UI-1.0 **design** pin checked | Renderer, golden/accessible/responsive UI tests and runtime UI compatibility |
| REL-11 | Explicit schema-reader preflight blocks incompatible retained state | Real DB/cache reader/migration/restore compatibility and safe operational switch |
| Other REL-01..12 acceptance | Unchanged | Full end-to-end acceptance remains NOT_RUN; no production release is designated |

F1 is a work-slice name, not a replacement canonical REL test registry. New Python unit cases are synthetic engineering tests; they do not turn the full REL-xx requirements into PASS.

## Validation and next permitted work

52 new unit/security cases (29 manifest + 23 preflight) pass locally. Together with the unchanged baseline, **719 synthetic tests** pass on local Python 3.12; compile checks pass. Cases include exact canonical roundtrip, same-size tamper, whole-artifact/manifest substitution, every component's namespace, duplicate/scope/schema/UTC attacks, mixed parameter versions, old custody format, all protected state kinds, wrong UI/cache pins and immutable state-preserving plans. Full GitHub Actions on Python 3.11/3.12 must pass for the exact source PR head before merge. No real rollback, deployment, market backtest, rights approval or recovery drill is tested.

**Next independent foundation slice: Release Foundation F2**, a deterministic **source-only engineering bundle builder** and explicit content/version inventory that resolve these pins from bounded permitted inputs, with full-versus-repeat build/tamper tests. No provider data, secrets, original account documents, production tags/ACTIVE pointer or host deployment. F2 still cannot designate a stable production release. P0.31's external rights evidence remains a separate blocked track; this work never substitutes synthetic tests for it.

After source CI/merge, update the original Drive Handoff with both tracks, mirror its entire text through a separate docs PR, require CI, and verify fresh exact Drive-vs-main equality. UI-1.0/CK2/FX2/Scanner/MOCHI remain unchanged. No new dependency is introduced; provider permission code is untouched and source retention/BT/OOS remain blocked.
