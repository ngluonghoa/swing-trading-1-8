# H2 — Legacy modernization and standardization (Swing Trading 1.8)

Status: H2-A audit implemented; H2-B..H2-E are separate modernization steps to be implemented and independently accepted. User approved retroactive standardization of ALL existing code through C4B, not just H1 standards for future code.

## Protected baseline

- H1 source PR #103 and docs PR #104 merged; baseline main SHA 5d343cfc903b9c34f8e897835238dfafdc378a49.
- Preserve C3C rollback PR #102; do not reuse PR #100/101 implementation, fixtures or dismissed branches.
- Preserve C3B partition chunks, C4A weekly segmented cache, C4B VN execution fixture, SHORT/SWING, 16 B/S zones, eight audit stages, UI v1.0 DESIGN_LOCKED.
- No edits to Forex Trading, CK2, Scanner, MOCHI, broker credentials or production services.
- Each code PR requires before/after fixture parity, dependency audit, Python 3.11/3.12 CI, wheel checks and scoped revert path. Never force-reset main.

## H2-A — Audit every module, automated

scripts/h2_architecture_audit.py uses Python AST and does not import any provider or run business code. It scans all source .py files and test_*.py files in the repository, producing a deterministic JSON inventory (h2.architecture.inventory.v1) attached to CI as h2-architecture-inventory (14-day retention). Evidence includes ownership class, file length, dependencies, direct-named test existence, missing direct tests and high fan-in modules.

Fail closed on unresolved internal imports, dependency cycles across the FULL package, core importing infrastructure/provider/SQLite/cloud, or reintroduction of the rolled-back C3C source/test. This is static engineering evidence only: source authorization=false, deployment approval=false, and backtest/OOS verified=false. A direct named test is not the same thing as dynamic line coverage; no coverage percentage is asserted.

## H2-B — Retrofit old module boundaries and dependency injection

Provider: d1_mcp_transport_bridge.py, dnse_d1_reference_fallback.py, vcbs_source_contract.py and adaptive_source_router.py. Use explicit provider/namespace and semantic version contracts at injection boundaries. Preserve read-only SSI/DNSE/VCBS behavior, source isolation, known-first semantics and fail-closed error states. No automatic fallback or live source-rights promotion.

Replay/detectors: contracts.py, backtest.py, engine.py, causal_indicators.py and B5 modules. Preserve first-known causal replay; unimplemented zones remain UNVERIFIED. Change detector math only with frozen old/new fixture parity and separate authorization.

Storage/cache: incremental_cache.py, cache_fetch_planner.py, partition_chunk_cache.py, segmented_cache.py, cache_snapshot_bundle.py, fixture_scan.py. Preserve old canonical byte format, digests and SQLite schema. Cross-provider/session/adjustment/indicator/source-rights namespaces never mix. Only derived state is rebuilt on invalidation; real market persistence remains blocked.

Custody/release: provider_*, reference_*, evidence_*, vn_release_rollback.py. Maintain conservative rights/retention, no false vendor grant, no signed LKG/deployed rollback from an engineering-only claim.

Retrofitting is incremental. Keep an already-correct module unchanged when refactoring offers no verified gain; record the decision. No mass rewrite for appearance alone.

## H2-C — Cache/data compatibility and migration

Explicit contract for read/write/restore and exact source identity. Test 5→20→1→20 symbol scopes, one dirty weekly chunk, cold/warm, rollback on missing/corrupt head, source outages, crash-before-publish, non-overwrite restore, revisions and global EMA20/ATR14 parity. A local weekly EMA seed is never a valid global indicator checkpoint. Cross-version N/N−1 destructive migrations remain unapproved until independently exercised.

## H2-D — Regression and substitution

Use consumer-driven tests against actual old modules (not only H1 dummy classes), with explicit source/clock/cache boundaries and no accidental callbacks before validation. Include removal under pinned consumers, duplicate/unknown adapter rejection, permission fail-closed, partial history, stale corrections, wrong provider, and before/after behavior fixtures. Python 3.11/3.12 full CI and build install must be green.

## H2-E — Governance and acceptance

Every completed PR reports exact baseline/head SHA, file scope, dependency graph/inventory, regression count, rollback plan and source rights limitations. Only after code merges should canonical Google Drive Master Handoff and Cache Spec be appended, and their GitHub text snapshots compared exactly in a docs-only PR. Keep package 0.0.1; no release tag/LKG/operational trading claims.

Do not declare H2 complete until old-module audit, scoped retrofits, cache parity, independent CI verification and Handoff synchronization are all evidenced.
