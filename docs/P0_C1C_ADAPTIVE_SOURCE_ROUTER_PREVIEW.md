# Swing Trading 1.8 — C1C Adaptive Source Router (REFERENCE-ONLY)

**Scope:** source selection design and independent, offline implementation in `src/swing_trading/adaptive_source_router.py` with fabricated tests. **No new MCP calls, automatic provider failover, real OHLCV storage, background refresh, live trading signals, or broker orders are performed by this module.** Follows approved C1/C1B (§27.54–§27.55), without using revoked ChatGPT Work code.

## Policy: qualify before optimizing

1. **Task-aware default priority**, not a single global source ranking:
   - **D1 OHLCV:** DNSE → SSI → VCBS, **only for sources that pass matching data-quality checks**. DNSE's current MCP exposes DAY OHLCV; that does **not** prove its full historical series is on the same price-adjustment basis as SSI raw.
   - **Native M1 OHLCV to build M5/M15:** **SSI candidate only**. Current DNSE MCP exposes DAY history; VCBS minute series are individual price points with cumulative-volume samples, not certified native M1 OHLCV. If SSI is unqualified or unavailable, return `BLOCKED`, **not** invented fallback minute bars.
2. **Mandatory diagnostic checks before ranking:** exact source/provider identity, task, raw vs adjusted price basis, VND price unit, verified source clock/calendar, closed-bar-only, complete coverage, native OHLCV, volume scope, corporate-action revision, OHLC integrity and external comparison. A failure or unknown excludes the source. An observation's `valid_until_utc` must include the requested decision clock.
3. **Performance feedback:** isolated probe observations are scoped to **provider+task**; ignore measurements older than 60 minutes and future-dated reports. Keep at most 20 recent samples for ranking. Require **five comparable recent samples for every eligible provider** before replacing the default ranking with measured median successful latency plus a failure-rate penalty (2,500 ms × failure ratio). Three recent consecutive failures open a 10-minute reported-failure circuit; unavailable source may yield another **reference candidate**, never an approved trading source.
4. **Fail closed:** no eligible source => `BLOCKED`. No source, however fast, bypasses price basis, quality, freshness or entitlement restrictions. Even when checks pass, output is always `reference_only=True`, with `rights_verified`, `source_authority_verified`, `persistence_authorized`, `indicator_eligible`, `trading_actionable`, `live_adapter_deployed` **all FALSE**. These are caller-asserted diagnostics for *offline modeling*, not independent vendor-grade evidence.
5. **No cross-provider cache poisoning:** C1/B `CacheIdentity` retains provider, endpoint, price basis, calendar, adjustment, quality, source-rights and indicator versions. This C1C module receives no candle payload and does not mutate cache. Reuse/refresh remains gated by authorized, source-scoped metadata and valid retention rights.

## Evidence and measured limitations

Direct read-only MCP sample from 07/11/2026 (Saturday), symbol SZC, 3 sequential calls each for D1:

| Connector | Median observed request elapsed | Request scope |
|---|---:|---|
| DNSE | 1,143 ms | ~247 D1 rows, whole history exposed |
| SSI | 1,525 ms | 2 rows, `range=1d` |
| VCBS | 1,742 ms | 2 D1 rows, bounded date window |

**Not equivalent request sizes**; sample size three is too small to establish long-run stability, p95, service-level reliability or relative bandwidth. There is no measured live market-session p95 or SLA. The router **does not prepopulate or hardcode these numbers as certified timings**. It will only use qualified, task-matched probe samples supplied at runtime by a future trusted observability service.

Four-symbol (FPT/SZC/SHS/VGI), 39 overlapping sessions per symbol, 156 comparisons against SSI raw D1:
- DNSE 133/156 raw OHLC matches and 156/156 volumes; price mismatches include corporate-action adjusted data and require like-for-like basis comparison. Never label DNSE "wrong" solely due to adjustment differences.
- VCBS 155/156 raw OHLC matches and 78/156 matched volumes. SHS and VGI volume-scope mismatches need root-cause reconciliation. VGI 2026-10-09 open exceeds high in VCBS sample; do **not** promote the anomalous bar.
- FPT SSI M1: 226 per-minute records on 06/11/2026, minute-volume sum matches its D1 `12,162,200` shares in the checked session. This supports further qualification testing, not full venue/auction/corrected-history certification.

## Release gates, tests, and remaining work

- New offline Python tests: default precedence, per-task source isolation, bad raw/adjusted/unit/volume, stale/future/incomplete/open/invalid OHLC, three-consecutive-failure cooldown, recent comparative performance reordering, too few/stale probes, duplicate observations, and immutable non-trading flags.
- This is a *pure policy preview*, not a deployed source router: all observations are caller-supplied and not signed/authenticated. No trusted provider-rights/entitlement/custody, persistence, actual feed quality, calibration or exchange calendar was granted.
- **Next in source authorization GĐ4/P0.29:** independently trusted provider key/head/rights and rotation/anti-rollback proof for SSI/DNSE/VCBS.
- **Next in cache engineering C2:** verify each MCP/API's entitlement, native M1/M5 source completeness and correction semantics, actual per-symbol/TF request bytes and end-to-end latency under live market load; implement trusted probe receipts with replay-safe window, signed quality/evidence and approved storage; integrate Adaptive Router with a source adapter only after those gates. Compare outcomes of cold/warm/incremental route and handle 16 B/S zones, SHORT/SWING, and eight-step audit without touching UI v1.0.
- No modification to CK2, Forex, Scanner, MOCHI or original GĐ4/P0.29 implementation path.
