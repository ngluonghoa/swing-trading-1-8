# GĐ4/C2A — Connected MCP Capability and Metadata-Only Response Audit

**Date:** 2026-11-07 (Asia/Ho_Chi_Minh). **READ-ONLY ENGINEERING / NO MARKET-DATA RETENTION, AUTHORITY OR TRADING.** This milestone follows native Master Handoff §27.58 (main `95babca36ce8a59de154048e0f05dc5a6fa2e0a5`). It does not overwrite the original P0.29c requirement for independently authenticated vendor trust roots and off-host monotonic witnesses.

## Why this step is the next practical increment

The user wants a roughly **five-minute repeated scan** without redownloading unchanged candles or recalculating old indicators. C1 synthetic cache/planner and C1C reference-only Adaptive Router establish conditional selection; they do not prove that the *connected* SSI, DNSE or VCBS MCP tools can return `changed_since` deltas, what calendar bounds the tools support, or that market-data retention is permitted. C2A restricts its claims to the exact **connected MCP argument surfaces** and a bounded **in-memory response-shape** check. It keeps data rights hard-disabled.

## Direct connector inspection on 2026-11-07 (Saturday, not live-session SLA)

Read-only calls with **FPT**, scoped to 2026-11-06 where the method allowed dates, returned the following **transient** row counts and schemas. Market rows, prices, sessions, credentials and provider response objects are **not committed to the repository or Handoff**.

| MCP surface | Request argument granularity observed | Transient shape observation | Safe C2A conclusion |
| --- | --- | --- | --- |
| SSI `marketdata_list_daily_stock_infor` | Fixed `range=1d/3m/...`, `toDate`, pagination | 2 D1 rows for `range=1d` / selected end date; open/high/low/close, `*_raw`, `close_price_adjusted`, matched vs negotiated volume | Coarse day range, **not arbitrary date bound**, no revision cursor, source RAW/adjusted basis must be explicit |
| SSI `marketdata_list_intraday_stock_infor`, `range=1d` | **Whole trading day**, not minute-level `start/end` | 226 minute-labeled OHLCV-style rows | Can propose a **whole-session request and local diff**; bar closure, session coverage, auction semantics remain unverified |
| SSI `marketdata_list_intraday_stock_infor`, `latest=true` | Only latest record, no `range` in same call | 1 OHLCV-style row | **Reference snapshot**, not a complete/newly closed M1 bar history |
| DNSE `price_get_history` | Symbol only, DAY resolution | 247 D1 columnar rows (`t/o/h/l/c/v`) | **Full history request**, no specified `from/to` in currently connected MCP and no changed-since cursor; values in thousands of VND need unit normalization |
| VCBS `vcbs_get_history`, `interval=D` | Explicit `start_date/end_date` | 2 RAW D1 rows, price units VND, explicit `volumeScope` | **Date-window request** is possible, **not** an update-after-revision cursor; verify RAW/ADJUSTED, corporate actions and HNX/UPCoM volume parity independently |
| VCBS `vcbs_get_intraday_history` | Symbol only, current session | 226 points with `time/price` and non-bar supplementary fields | Minute **price points** only. Cannot substitute complete OHLCV M1/M5/M15 or infer per-minute volume |
| VCBS `vcbs_get_stock_price` | Single ticker or 2–20 symbols | Quote batch contract inspected from connector schema; row schema intentionally not certified by C2A | Snapshot/reference only; prices in **thousands VND**, missing symbols must not become price zero |

These counts merely describe the returned **shapes** of the six directly called endpoints. Three or fewer probes outside a live session cannot establish vendor uptime, true end-to-end p95, freshness, correction latency, or completeness. The connector calls were observed in a shared parallel tool batch, so apparent elapsed times are **not independent per-provider latency metrics** and must not be fed into C1C performance ranking.

### Implications for five-minute refresh

- **M1/M5/M15 path:** SSI session OHLCV-style feed is the sole connected candidate in this set, but the **current intraday MCP requires whole-session `range=1d`**, so requesting exactly 09:45–09:50 is **not supported by this method**. A future authorized adapter may redownload the day, compare only changed records, and reuse unaffected L2 checkpoints. Claim saved CPU, not network bytes, unless a distinct approved endpoint supplies true date/time windows.
- **D1 path:** DNSE remains the **conditional quality-first router priority** per C1C, but its current MCP has symbol-only YEAR/DAY history, so it can be faster in a small probe while returning more rows. SSI uses coarse day-range buckets; **VCBS allows `start_date/end_date`**, making it a more efficient option for narrow D1 revalidation, subject to quality/corporate-actions/volume and legal review. Neither date windows nor the `latest` option prove changes-only delta support.
- **No provider** in the connected inventory exposes a verified `changed_since` **revision cursor**, full correction provenance, or independently certified source clock/retention rights. Avoid marking closed bars immutable; retain periodic correction revalidation in the synthetic planning design. Do not infer market-data permission from successful MCP reads.
- **No conflation:** DNSE DAY adjusted/raw conventions, SSI detailed raw-vs-adjusted, VCBS D1 RAW vs quote-board thousand VND, and VCBS minute **price** vs SSI minute **OHLCV** need separate source/product/timeframe/version namespaces. C1/C1C are unchanged.

## New code and controlled API

`src/swing_trading/c2_source_capability_audit.py` describes **seven** connected MCP query surfaces using fixed, typed provider/product/request-boundary contracts. `advise_connected_refresh` is pure: it returns a **non-executable** request-boundary recommendation (`REFETCH_WHOLE_SESSION`, `REFETCH_FULL_HISTORY`, `REVALIDATE_DATE_WINDOW`, `REFETCH_COARSE_DAILY_RANGE`, `REFERENCE_SNAPSHOT`, `BLOCKED`) and rejects any demand for **true changed-since update** for all seven surfaces. No endpoint adapter, scheduler, host, runtime credential, real market quote cache or callback is shipped.

`conservative_c1_m1_capability` connects this inventory to the existing C1 planner **without starting a fetch**: SSI whole-session intraday maps to `SourceCapability.FULL_SESSION`; every other connected endpoint maps to `UNKNOWN`, never `WINDOWED` for M1. This prevents a daily VCBS calendar-window argument from being mistaken for a five-minute intraday delta API. Vendor rights and market quality are still unverified.

`audit_transient_response` accepts **caller-supplied in-memory** parsed JSON objects and produces a **metadata-only** report: provider, endpoint, observed row count, invalid row count, response state and approximate *locally reserialized* bytes. **It never returns or stores prices or quotes.** It runs bounded structure checks for SSI `stocks`/`ticks`, DNSE aligned monotone `t/o/h/l/c/v` series, VCBS RAW D1 OHLCV/unit/volume scope and VCBS minute `time/price` series. It checks finite positive OHLC prices, nonnegative volume and OHLC order. Source errors, partial/wrong array shapes, no data or invalid OHLC become `SOURCE_ERROR`, `SCHEMA_REJECTED` or `EMPTY_UNVERIFIED`; no empty-response optimism. It intentionally does **not** invent VCBS quote-batch response row mapping where the observed adapter has not been independently checked.

**Important:** a well-formed shape is not historical correctness. It does not prove trading session calendar, closure/finality, source revision history, performance or legal authority; counts and approximate JSON serialization size are not authenticated provider receipts or network bytes. All report flags `source_freshness_verified`, `closed_bar_finality_verified`, `source_rights_verified`, `price_adjustment_parity_verified`, `licensed_retention_approved`, `indicator_eligible`, `live_trading_enabled` remain **hard FALSE**. `require_authorized_c2_source` always raises. No C2 report may be used to turn on C1 fixture storage for licensed real data.

`tests/test_c2_source_capability_audit.py` has **63 offline fabricated unit tests** for all endpoint boundaries, each changed-since rejection, price unit isolation, malformed/missing/duplicate timestamps, impossible OHLC, invalid/mixed basis, provider errors, quote-batch unknown schema, no price leak in audit report, immutable unauthorizable fields and size/clock limits. New tests must pass together with existing repository full CI on Python 3.11 and 3.12. No real historical BT/OOS run.

## Acceptance and next milestones

| Requirement | State after C2A |
| --- | --- |
| Exact connected MCP query-surface inventory | **Engineering implementation + manual direct read-only shape inspection** |
| Local capability-safe refresh recommendations | **Offline unit-tested** |
| SSI minute feed completeness, official exchange auction/bar-close parity | **NOT VERIFIED** |
| Verified true five-minute delta API/cursor across current 3 MCPs | **NOT DEMONSTRATED** |
| Signed provider clock/provenance / correction + corporate-action history | **NOT VERIFIED** |
| Authenticated vendor account and raw/derived retention/redistribution rights | **NOT VERIFIED** |
| Real L1-L5 persistent cache on approved storage host | **NOT IMPLEMENTED / NOT AUTHORIZED** |
| Production p50/p95/error-rate or five-minute network savings | **NOT MEASURED** |
| P0.29c independent current-head custodian and protected monotonic floor | **EXTERNAL BLOCKER** |

**Next C2B:** independently verified, controlled read-only *equal-workload* probe matrix with exchange calendar and provider timestamp checks, source correction/adjustment and per-scope volume reconciliation. Avoid collecting or retaining licensed quotes until permission is documented; measure only metadata with approved monitoring. **Next P0.29c:** obtain external vendor/account/custodian evidence; GitHub/Google Drive/ChatGPT cannot self-issue a vendor licence or independent witness. Preserve UI v1.0 `DESIGN_LOCKED`, 16 B/S zones, SHORT/SWING, eight stages and all previously revoked Work branches. CK2/Forex/Scanner/MOCHI unchanged.
