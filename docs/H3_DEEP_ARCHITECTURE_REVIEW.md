# H3 — Deep architecture review and controlled legacy refactoring

Status: H3-A deep 63-module audit MERGED PR #111, H3-B real legacy incremental cache decomposition MERGED PR #112; remaining H3-C/D/E manual review and selective refactors remain OPEN. Native Handoff §27.67, Smart Cache §30 and full source snapshots are being synced separately. H3 is user-approved because H2 only retrofitted four preexisting modules; the other old modules need evidence-based assessment, not blanket rewrites.

## Baseline protection

- Repository: ngluonghoa/swing-trading-1-8; main H2 finalized 7d89d0e74e9c08c5c21ea9a2fc727dcb26fecc37, postmerge CI Actions run 42442384580 PASS 1305 tests per Python 3.11/3.12.
- Previous source C3B/C4A/C4B, revoked old C3C PR #100/101 via PR #102, H1/H2 safeguards, UI 1.0 DESIGN_LOCKED, SHORT/SWING, 16 B/S zones and eight audit stages remain unchanged.
- Do not touch Forex Trading, CK2, Scanner, MOCHI, production licensed cache, external provider permissions or broker state.
- Separate each H3 refactor from auditing, preserve independent rollback and demonstrate behavior parity before altering transactional cache or source-routing code.

## H3-A — Deep 63-module static review

scripts/h3_deep_module_review.py analyzes ALL Python modules by AST, uses the H2 graph/test import audit as foundation, reports:
- Module ownership, LOC, class/function count, direct internal dependencies and consumer fan-in.
- Largest function body, deterministic rough branch score, bare and silent except handlers, exact function-body AST duplicates.
- Full provisional KEEP or IMPROVE classification, review priorities and feature restrictions. REPLACE and REMOVE are NEVER automatic; candidates must first demonstrate no viable consumers, compatibility, safe migration and scoped rollback. There is no approval to delete dormant source files.
- JSON report and full one-row-per-module Markdown matrix emitted in CI artifact h3-deep-legacy-review, retained 14 days. Generator source is durable, artifacts are regenerable. Static audit does NOT import execution modules, call live SSI/DNSE/VCBS, or confer market authorization.
- Automated gates: all modules present and H2 import boundaries still pass. Full unit suite on Python 3.11/3.12 plus whole-repo correctness lint, targeted strict lint and wheel test continue.

**Initial heuristic outcome (must NOT be conflated with manual signoff):** 63 modules reviewed; 31 KEEP and 32 IMPROVE. None approved REPLACE/REMOVE. High priorities include reference_pinned_fd (silent exception/branch), incremental_cache (121-line high branch score 49), b5_phase_contract (117-line score 46), d1_atr_reconciliation, legacy_migration, vn_release_rollback, provider_review_packet and b5_temporal_split_audit. replay has 31 consumers; market_data 17; high fan-in alone warrants stable contracts and golden tests, not rewriting their implementations. Identical AST function-body detected in durable_evidence:connection and reference_journal:_connection: DRY consolidation ONLY after proving separate custody/transaction requirements.

The complexity score is a static risk *heuristic*, not McCabe-certified cyclomatic complexity. Exception flags and duplicates are audit prompts, not proof of a production bug. IMPORT-only test references are not coverage; full branch coverage and mutation testing have NOT been measured.

## Initial manual assessment — avoid false-positive refactors

- reference_pinned_fd.py: the flagged FileNotFoundError handlers in verify_path_names/pin_reference_sqlite_files deliberately treat *absence* of SQLite sidecars or a .git sentinel as success; every present sidecar or Git marker is rejected in the opposite branch. They are not generic exception swallowing. Preserve them; H3-B may add fault-injection tests for unexpected OS errors/path swap, but cannot remove these catches just to reduce a static score.
- replay.py (31 downstream imports, ~26 LOC): small strict causal clock. KEEP existing behavior until consumer-level golden tests prove a need for change; high fan-in alone is not a refactor rationale.
- incremental_cache.py: 121-line apply_fixture_window, branch score 49. IMPROVE candidate because validation, transactional append/revise/delete, lineage, checkpoint replay and cursor update coexist in one function. First use golden before/after fixtures; split responsibilities without editing SQL schema or economic math. User has NOT approved a changed cache policy.

Full 63-module provisional table: [H3_MODULE_DISPOSITION_PROVISIONAL.md](H3_MODULE_DISPOSITION_PROVISIONAL.md). CI fails if this table diverges from the AST-generated version. Initial manual observations above are hypotheses based on inspection, **not** final approval for all 63 modules.

## H3-B — Prioritized bounded improvements

1. First protect complex historical synthetic cache code incremental_cache.py with actual golden scenarios: append, revision, metadata-only change, complete-scope deletes, open bars, source clocks, SQLite atomic rollback and global EMA20/ATR14 checkpoints. Separate validation/transaction/checkpoint responsibilities one at a time. No schema, wire format, retained revision or indicator math change.
2. Review existing reference_pinned_fd silent exception path for safety intent and fail-closed semantics before any edit. Security-related exception handling may be deliberately conservative. Never remove security handling because a static score is high.
3. Review B5 formula/phase temporal cases and provider rights modules separately with frozen snapshots and actual source attribution; any published behavior change requires separate user approval.

## H3-B accepted engineering slice

[Documented C1/C3B synthetic SQLite refactor](H3_INCREMENTAL_CACHE_REFACTOR_B.md) is merged main b022487e21aa552814cdba2144c4be60e38e50e2 with [postmerge main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42443799090) PASS 1323 tests per Python. H3-A+B do NOT amount to complete H3.

## H3-C — Module disposition proof

A module can be marked KEEP after independent evidence it has clear boundaries and appropriate behavior tests. IMPROVE after a PR reduces real measured complexity without changing valid behavior. REPLACE requires consumer parity across versions, no provider rights claim, and state migration/rollback proof. REMOVE requires evidence of unused public API, deprecation impact and source/custody retention review. All 63 need an explicit final disposition review; the H3-A provisional matrix alone is NOT completion.

## H3-D/E — Gate and documentation

For each improvement: old/new function path mapping, tests before/after, H2/H3 audit comparison, effect on import fan-in, PR CI green, changelog, no changes outside Swing. Final documentation updates go to canonical Master Handoff and Smart Cache Google Docs and exact GitHub text copies only after the code PR is merged. H3 cannot grant vendor rights, production migration, signed release/LKG or operational backtest. Next C3C remains postponed while H3 required risk reviews remain open.

Rollback: git revert each merged H3 PR in reverse order, verify full CI and canonical Docs parity. Never force-reset main or reinstate rolled-back C3C.
