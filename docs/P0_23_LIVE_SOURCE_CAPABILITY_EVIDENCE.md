# GĐ4/P0.23 — SSI/DNSE real read-only source probe and fail-closed evidence matrix

Observation date: **2026-11-06**, Asia/Ho_Chi_Minh. **Read-only user-connected MCP probes; no persisted OHLCV, raw payload, secret or broker action**. Engineering CI remains synthetic only; sample provider calls are **not** a licensed historical-data acquisition or production acceptance test.

## 1. Executed real read-only probes (SHS / HNX)

| Connector action actually called | Request / scope | Observed result | Critical limitation |
|---|---|---|---|
| SSI `marketdata_list_daily_stock_infor` | `symbol=SHS, range=1d, toDate=13/10/2026, pageSize=5,pageIndex=1` | `status=ok`, 2 `stocks` rows, including 13/10 and 12/10 | `range=1d` includes previous trading row; filter target trading date. No independent basis/first-known or retention right. |
| SSI `marketdata_list_stock_infor` | `symbol=SHS, range=1d, toDate=13/10/2026` | Connector raised error encapsulating **`DOWNSTREAM_UNAVAILABLE`** | No `sysToken` pagination or long-run coverage verified. This one failed call does **not** prove the endpoint is always offline. |
| SSI `marketdata_list_intraday_stock_infor` | Same SHS + `range=1d, toDate=13/10/2026` | `status=ok`, **215** `ticks`; first label `13/10/2026 14:45:00`, last `13/10/2026 09:00:00`; 215 distinct text labels in observed response | Endpoint returns intraday entries, but **not** certified native OHLC M1/M5/M15 with guaranteed every-minute/complete coverage. Provider metadata clock is not historical first-known. |
| DNSE `price_get_history` | `symbol=SHS` | Parallel `t/o/h/l/c/v` arrays, **248** rows; `t` Unix labels at 09:00 Asia/Ho_Chi_Minh, first 1762480800 / last 1793930400 | Connected MCP method is **DAY-only**; 09:00 is session label, **not** daily close or first historical publication instant; adjusted/raw basis still UNKNOWN. |

**Temporal ambiguity found:** SSI intraday connector description states one `MM/dd/yyyy HH:mm:ss` example, yet the observed response has date component `13/10/2026`, which cannot be parsed as US month/day. Therefore **do not infer timestamp formats from a sample or promote ticks into minute bars**; provider documentation mapping needs explicit correction/confirmation and tests before any historical replay.

**Independence of product channels:** Public [SSI FastConnect terms](https://developers.ssi.com.vn/docs/getting-started/terms-and-environments) say separate API registration/authorization and discuss intraday retention for FastConnect; they do **not** verify the permissions, data retention period or completeness of *this connected MCP tool*. The public [DNSE Market Data docs](https://developers.dnse.com.vn/docs/dnse/market-data/) enumerate additional intraday/timeframe capabilities; that does **not** mean the connected `price_get_history` MCP exposes them or that this account is entitled to retain data. **No signed licence terms/retention grant have been verified**, and there is no evidence of point-in-time historical revisions or source-publish timestamps.

The direct-source probes were observed through connected tools but are **not** checked into GitHub, Google Drive, MOCHI or a production SQLite file as quote data. This document stores only endpoint names, dates, counts, response categories, and structural/timestamp limits.

## 2. New code (metadata-only capability evidence)

`src/swing_trading/source_capability_evidence.py`:
- `ProbeEndpoint` allowlist distinguishes SSI full paginated intraday, SSI alternative intraday, SSI detailed daily and DNSE DAY; each has a **specific provider and response-kind**. No generic dynamic plugin or trading actions.
- `summarize_source_capability(endpoint, response, symbol, checked_at_utc)` observes an explicit parsed **in-memory** response, with 4MiB size cap, validates SSI status/row identity and DNSE six aligned timestamp arrays with monotonic 09:00 local DAY labels, returns only endpoint/provider, checked-at, **row count**, status and label class. No raw quote, response body, prices, source credential, cache or file is returned.
- `SourceCapabilityObservation` enforces provider identity, valid UTC, and hardcoded **False** on rights, historical first-known, adjustments, complete M1/M5/M15, pagination, independent clock attestation, backtest and trading eligibility. A provider's `asOfUtc` or a historical DAY 09:00 label is **not** evidence of first-known publication time.
- `audit_backtest_evidence(tuple_of_probes)` exposes only observed endpoint identities and explicit **unresolved gates**; never promotes a source response into a calibrated B5 detector/backtest or executable buy/sell.

Tests `tests/test_source_capability_evidence.py`: SSI D1/SSI intraday response shapes, downstream vs permission error classification, aligned/duplicate/bad DNSE DAY labels, wrong provider, malformed payload, 4MiB bound, no OHLCV/secret leakage into metadata report, attempted flag forging, and no-backtest-readiness matrix. Run CI on Python 3.11 and 3.12 and require green results before merge.

## 3. Current gate status, next P0.24

- **OBSERVED:** one SSI D1 endpoint response, one 215-row SSI intraday sample via alternative method, one DNSE 248-row DAY series, one failed SSI full paginated intraday call.
- **NOT VERIFIED:** provider source licence for ongoing local/server caching, historical M1/M5/M15 completeness (including missing/zero volume, lunch auctions and irregular timestamps), SSI sysToken full pagination, timestamp canonicalization, actual first-known timestamps and revision history, independent corporate-action adjustment basis, calendar coverage, entitlement to backtest historical quotes.
- **NOT RUN:** real history ingestion, Smart Cache L1–L5, calibrated B5 SHORT/SWING 24 numeric slots, fully executable B5 detector, trade fill/fees/slippage/tax/T+2 simulator, historical backtest/OOS, operational hosted MCP or brokerage orders.

**GĐ4/P0.24:** investigate an independently documented/authorized source-native M1/M5/M15 endpoint, explicitly validate one full session against expected session calendar and exchange auctions/OTC/zero-volume handling, confirm legal retention and first-known source timing, and make a reviewed host SQLite WAL/VFS plan before any persistent quote storage. If evidence cannot be supplied, keep M1/M5/M15 and real BT/OOS fail closed. `UI-1.0 DESIGN_LOCKED`, CK2/FX2/Scanner/MOCHI unchanged.
