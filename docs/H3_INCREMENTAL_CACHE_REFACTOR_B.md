# H3-B — Legacy synthetic SQLite cache controlled decomposition

Status: refactor candidate implementation, acceptance only after PR and postmerge CI. This is a real code refactor of the EXISTING src/swing_trading/incremental_cache.py, not an extra disconnected framework.

## Protected baseline

- Parent: H3-A PR #111 merged main 52944205aa1010d569bd35edccfd67ded4ada5af. Previous H2 engineering baseline 7d89d0e74e9c08c5c21ea9a2fc727dcb26fecc37.
- Existing transaction, SQLite on-disk tables and row schema, cache key/digest, provider namespace, source revision/first-known and EMA20/ATR14 arithmetic MUST remain unchanged. No real licensed provider source or cloud data, C3C remains rolled back.
- Only synthetic fixture local SQLite is involved; no external fetches, broker orders, Forex project or UI changes.

## Measured before → after in H3 all-module AST review

| Metric | H3-A baseline | H3-B after refactor |
| --- | ---: | ---: |
| incremental_cache.py physical LOC | 411 | 441 |
| Longest function body (apply_fixture_window) | 121 | 83 |
| Highest rough branch score | 49 | 23 |
| Active consumer modules | 9 | 9 |
| H3 heuristic flags | FUNCTION_90_PLUS; HIGH_BRANCH_SCORE | HIGH_BRANCH_SCORE |

The module is longer because validation/checkpoint/cursor responsibilities are now explicitly named and individually testable. The main business method is shorter; lowering this approximate branch score is not evidence of improved latency, trading performance or algorithm quality. It remains an IMPROVE candidate pending further work.

## Actual decomposition

- New pure _validate_fixture_window validates typed CacheIdentity/FixtureBar, UTC observation/request interval, scope completeness, ordering, first-known, closed bars and unchanged source behavior BEFORE opening SQLite. Existing checks moved without changing order/error messages.
- New _recompute_dirty_tail replays minimal dirty window and rebuilds checkpoints INSIDE the caller-owned SQLite transaction; no independent connection, COMMIT or wider replay.
- New _persist_fixture_cursor validates monotonic observation clock and upserts cursor INSIDE the SAME existing transaction; still returns MAX(start_utc).
- apply_fixture_window retains BEGIN IMMEDIATE, append/backfill/revise, LINEAGE_ONLY, DELETE, rollback on exceptions and COMMIT ordering. Previously public method signature is unchanged.

## Behavioral proof

tests/test_incremental_cache.py existing cold/warm, append, backfill, full/incomplete scopes, corrections, source timestamps, open bars and SQLite lineage tests remain. New tests/test_h3_cache_transaction_parity.py adds observable golden states for cold 6-bar build, metadata-only revision, price correction/recompute tail, deletion and stored lineage event order, incomplete scope, open bars, atomic rollback AFTER writing on retrograde cursor, bad request rejection BEFORE SQLite connect, full reconciliation clock and hard-false live source flags.

Full CI on Python 3.11 and 3.12, H1/H2 contracts, whole package static graph, strict Ruff on modified module/tests, regenerable 63-module matrix, package wheel clean install must all PASS before merge. Source and docs changed in an isolated PR with a revert path.

## Rollback and limits

A normal revert PR restores the original complex function with exactly the same schema and stored fixture data; no migration is required. All sources remain synthetic; no independently signed source head/entitlement, no actual production rollback/LKG, no live five-minute provider delta, no validated OOS backtest or broker side effects. H3 is not yet complete for the other modules; do not falsely label 32 candidate modules as refactored.
