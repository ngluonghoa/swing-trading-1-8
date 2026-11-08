# H3 — Deep architecture review and controlled legacy refactoring

Status: H3-A **automated static review implemented**. Human architectural acceptance and H3-B..H3-E refactors are separate reviewed PRs. H3 is user-approved because H2 only retrofitted four preexisting modules; the other old modules need evidence-based assessment, not blanket rewrites.

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

## H3-B — Prioritized bounded improvements

1. First protect complex historical synthetic cache code incremental_cache.py with actual golden scenarios: append, revision, metadata-only change, complete-scope deletes, open bars, source clocks, SQLite atomic rollback and global EMA20/ATR14 checkpoints. Separate validation/transaction/checkpoint responsibilities one at a time. No schema, wire format, retained revision or indicator math change.
2. Review existing reference_pinned_fd silent exception path for safety intent and fail-closed semantics before any edit. Security-related exception handling may be deliberately conservative. Never remove security handling because a static score is high.
3. Review B5 formula/phase temporal cases and provider rights modules separately with frozen snapshots and actual source attribution; any published behavior change requires separate user approval.

## H3-C — Module disposition proof

A module can be marked KEEP after independent evidence it has clear boundaries and appropriate behavior tests. IMPROVE after a PR reduces real measured complexity without changing valid behavior. REPLACE requires consumer parity across versions, no provider rights claim, and state migration/rollback proof. REMOVE requires evidence of unused public API, deprecation impact and source/custody retention review. All 63 need an explicit final disposition review; the H3-A provisional matrix alone is NOT completion.

## H3-D/E — Gate and documentation

For each improvement: old/new function path mapping, tests before/after, H2/H3 audit comparison, effect on import fan-in, PR CI green, changelog, no changes outside Swing. Final documentation updates go to canonical Master Handoff and Smart Cache Google Docs and exact GitHub text copies only after the code PR is merged. H3 cannot grant vendor rights, production migration, signed release/LKG or operational backtest. Next C3C remains postponed while H3 required risk reviews remain open.

Rollback: git revert each merged H3 PR in reverse order, verify full CI and canonical Docs parity. Never force-reset main or reinstate rolled-back C3C.
