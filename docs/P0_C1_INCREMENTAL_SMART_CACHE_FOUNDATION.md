# GĐ4 / C1 — Five-minute Incremental Smart Cache Foundation (Synthetic Only)

**Date:** 2026-11-07. **State:** ENGINEERING FOUNDATION / SYNTHETIC_TEST_ONLY; **not deployed, not source-authorized, not L1–L5 production**. Read with canonical Data Contract §2, §§5–12 and §18 of document `05_GD3_DATA_CONTRACT_SMART_CACHE_ARCH`, latest Master Handoff §27.53, and existing P0.16–P0.28 source-rights gates.

## Problem and target

A user may request a symbol or basket scan roughly every five minutes. The desired behavior is: retain previously retrieved and validated **closed** observations; request only a source-supported range with a small correction overlap; calculate newly affected indicator checkpoints; and preserve unaffected history/derived results. No source is entitled to a fabricated delta API, eternal immutable history or unconditional cache freshness. If an actual SSI endpoint only returns whole-session data, the system must honestly request that whole session and avoid only *local* reprocessing, not claim it saved transfer bytes.

## What is implemented in this PR

1. `cache_fetch_planner.py`: explicit `SourceCapability` (`WINDOWED`, `FULL_SESSION`, `UNKNOWN`), validated as-of UTC/session-bound bar windows, a metadata-only `SourceCursor`, optional provisional refresh, one-bar default overlap, periodic full-session correction reconciliation and conservative `BLOCKED` for unknown capability or clock regression. Full-session after configurable reconciliation interval prevents the overlap from silently missing older corrections. The default 5-min refresh and 30-min reconciliation are **synthetic fixture examples**, not provider-approved timings, exchange calendar contracts or performance SLOs. `REUSE_CLOSED` never asserts `certified_source_freshness` or `data_authorized`.
2. `incremental_cache.py`: **offline fixture-only** SQLite storage with explicit project+provider+endpoint+instrument+exchange+timeframe+session+price basis+adjustment+calendar+aggregation+source-rights+source-resolution+quality+indicator version/parameters in a deterministic identity fingerprint. In one transaction it compares content digests, APPEND/BACKFILL/REVISE/DELETEs a complete *fixture* scope, preserves change-digest lineage (including metadata-only revision updates), ignores `OPEN` candle previews, and updates persisted closed-bar checkpoints. Omitted rows from incomplete responses cannot delete existing bars. The durable store is a test-only local path, **not** a permitted place for actual quotes.
3. Wilder ATR14 and EMA20 synthetic Decimal checkpoints: append only the new bar; on correction/delete, resume strictly from the preceding unaffected checkpoint, recalculate the impacted tail, and compare all checkpoint results against cold full recompute. No claim this is a calibrated/authorized production indicator, nor that L3/L4/L5 are executable.
4. `fixture_scan.py`: thin injected, **synthetic-only** coordinator and `FixtureScanReceipt` that counts fixture requests, returned rows and reported bytes; rejects untyped callbacks. It has NO SSI/DNSE MCP calls, real network transport, credentials, source entitlement, order placement or runtime schedule. No provider-specific API parameters are invented.
5. `invalidation_preview()` documents *potential* dependency edges for L1–L5; **no persistent L3 structure, L4 detector or L5 publication cache exists**. Locked UI v1.0, B1–B8/S1–S8, SHORT/SWING and eight-step audits are not modified.

## Deterministic demonstration, not real API savings

With a fixture stream containing M5 bars at 09:00, 09:05, ... (time labels local equivalent in a demonstrator):

| Synthetic run | Planned fetch | Records returned | Indicator checkpoint work |
|---|---|---:|---:|
| 09:45 cold | Session-to-now | 9 | 9 |
| 09:46 warm, no newly closed bar | None | 0 | 0 |
| 09:50 delta-capable fixture | Previous closed bar + 1 new bar | 2 | 1 |
| Same 09:50 scan with session-only provider | Whole session (cannot save provider bytes) | 10 | 1 |
| Periodic reconciliation | Whole session | All available | Changed suffix only |

These are exact assertions in tests, **not observations from a real provider**. The 5-minute interval is a scan request cadence, not evidence of a new M1/M5 candle or of source update frequency. Clock boundaries, gaps, volume zero vs absent, VN exchange session/auction rules and W1/D1 finality still require independently verified provider-calendar contracts.

## Failure and versioning rules

- Source lacking verified `WINDOWED` or `FULL_SESSION` capability => `BLOCKED`; no invented cursor support. The existing P0.16 reference D1 bridge continues to fetch before recording a diagnostic quote; it was deliberately not changed into a source-less cache fallback.
- A complete fixture scope can delete an absent observation **only within that exact scoped interval**. Incomplete pagination never deletes. Real SSI/DNSE missing-minute semantics are unverified and MUST NOT be mapped to deletion or no-trade without independent evidence.
- OPEN bars never persist as closed checkpoints. Corrections known later never appear earlier in a backtest clock. A previous `first_known` cannot move backwards. Historical source/digest corrections invalidate dependent descendants and preserve a diagnostic revision lineage.
- Separate SSI and DNSE cache identities even for the same symbol and period; unknown basis or source adjustment cannot be silently merged. A source-rights or indicator version change creates an independent key, without self-authorizing storage.
- Atomic SQLite writes and rollback-on-exception apply to **fixture transactions only**. No storage ACLs/encryption/WAL host conformance, off-host custody, secure expiry/erasure, concurrency crash matrix, legal retention, quota or disaster-recovery validation is claimed.
- Release/rollback ADR-0003 `R3 SOURCE/DATA` and `R4 SCHEMA/CACHE` are still OFFLINE/NOT_RUN for production; fixture cache cannot supply a real `Last Known Good` or actionable analysis.

## Tests and acceptance boundaries

New `tests/test_cache_fetch_planner.py`, `tests/test_incremental_cache.py`, `tests/test_fixture_scan.py`: **54 synthetic tests** run locally with `PYTHONPATH=src python -m unittest discover -s tests -v` against the standalone new test files, plus Python `compileall`. Before calling the milestone CI_PASS, inspect GitHub Actions on Python 3.11 and 3.12 **together with all existing tests** and verify post-merge main CI. No historical backtest/OOS/walk-forward or provider API measurement was performed.

**Not implemented yet:** independently approved SSI/DNSE rights and versioned native M1/M5/M15 adapter; actual data transfer reduction on the connected providers; production persistent raw or derived OHLCV cache; full L1 aggregation from native/derived candles; L2 RSI/MACD/ADX/OBV/RVOL-TOD/VWAP checkpoints; causal L3 pivot and structure persisted graph; L4 16 detector signals; L5 8-step report and atomic publication; multi-symbol batched calls, verified source rate limits/concurrency, cache backup/restore on an approved host, source-correction/revocation purge and retention. A benchmark SLI/SLO is still unapproved.

## Next engineering sequence

- Preserve existing NEXT **GĐ4/P0.29 independent vendor key/head/freshness/anti-rollback custodian** and no rights escalation. This C1 is a parallel performance foundation, not a replacement for P0.29.
- Review each connected provider's capability and account-specific permissions; ensure each adapter reports whether the response is windowed, complete and what bytes were fetched. Periodic reconcile policy must depend on supported provider correction history and quota evidence.
- Once authorized storage/retention/security/host exists, design a separately gated production implementation; never relabel fixture store or user-asserted rights as approved live storage. Build symbol/TF dependency DAG and all 5 layers with source-certified cold/warm/incremental output parity, clock-safe stage 8 and release-safe migration.
- Keep GitHub repo independent of CK 2.0 / Forex Trading / Scanner / MOCHI; UI v1.0 DESIGN_LOCKED; no broker transactions.
