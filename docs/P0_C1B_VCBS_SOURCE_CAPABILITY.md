# Swing Trading 1.8 — C1B: VCBS as third provider (read-only capability audit)

Date: 2026-11-07. Scope: **separate provider registry / synthetic-only tests**. Parent C1: `docs/P0_C1_INCREMENTAL_SMART_CACHE_FOUNDATION.md`. This document does not grant any vendor licence or authorize OHLCV retention, real-market indicator generation, trading or production deployment.

## Evidence from connected MCP VCBS (read-only, no stored market rows)

The connector was directly invoked on 2026-11-07 for an SZC RAW D1 date window (2026-11-03 through 2026-11-06), current intraday history, and two-symbol quote batch (SZC/FPT). All three calls returned parseable results. This shows *technical access to those surfaces only*; it does not prove provider-granted storage rights, retention, real-time freshness, history completeness or exchange-authoritative candlestick semantics. Calls were on Saturday, so intraday output referred to the previous trading session; it must not be treated as live Saturday trading.

| VCBS API | Request capability | Safe mapping into Swing |
| --- | --- | --- |
| `vcbs_get_history` D | `start_date` + `end_date` bounded **date window** | RAW D1 OHLCV **diagnostic candidate only**; `priceBasis=raw`, `price_unit=VND`, `volumeScope=matched`; require calendar/basis/finality/source rights for canonical acceptance |
| `vcbs_get_history` W/M | Date window or number of weeks/months; provider aggregates | Reference only until exchange calendar, partial period and adjustment policy parity established. Here `M` means **month, not one-minute M1** |
| `vcbs_get_intraday_history` | **Current/recent session only**; no `from/to/since` arguments | Price-per-minute series, ATO/ATC, price-board OHLC, cumulative matched volume. **NOT a genuine native M1 OHLCV candle series**; cannot derive accurate per-minute RVOL/volume/VWAP from it |
| `vcbs_get_stock_price` | 1 or batch up to 20 symbols | Reference quote, units **thousand VND** (convert to VND only with explicit unit policy), no history delta |
| `vcbs_get_technical_indicators` | D/W/M indicators | Separate externally computed reference/consistency check; price basis and `partial_bar` / `as_of` must be preserved; never silently replace local causal features |
| `vcbs_get_corporate_events` | Per-symbol reference records | Potential adjustment invalidation evidence; not independent authoritative factor/complete revision feed |

## Cache integration contracts

1. C1 synthetic `Provider` extends `SSI`, `DNSE` to `VCBS`; every cache `CacheIdentity` retains its **provider/endpoint/price_basis/source-rights/calendar/policy fingerprint**. Do not share raw candle/observation identities or price-basis authority across providers. An SSI outage cannot silently promote VCBS or DNSE to qualified primary data.
2. A bounded D1 **date** query does not imply a `changed_since` cursor or true incremental revision feed. The planner may constrain requested D1 dates, but must revisit overlapping days and periodically reconcile historical corrections/corporate actions. Intraday VCBS remains **FULL_SESSION or NO_NATIVE_OHLCV**, never `WINDOWED` M1 OHLCV.
3. VCBS `priceBasis=adjusted` changes selected `price`/adjusted close; row `openPrice/highPrice/lowPrice` are *not proven adjusted OHLC*. Do **not** combine adjusted close with raw O/H/L. This PR parser accepts `raw` diagnostic D1 only; adjusted inputs are refused pending verified factor/price basis semantics.
4. Intraday `series[].price` is not a minute OHLCV; `recentTrades[].volume` is cumulative session matched volume, not per-minute matched volume. Treat no trade or absent minute as missing/unknown, not automatically zero.
5. Partial/no-data/last-session/late index values are explicit freshness/coverage states, not zero or proof of an unchanged price. Preserve arrival time separately from source business/trading date and actual first-known. Provider transport error report and per-provider quota/bytes/cache metrics must be separate.
6. Persistent C1 storage remains `SYNTHETIC_TEST_ONLY` and cannot receive actual VCBS rows. `vcbs_source_contract.py` exposes **pure inspections of invented fixtures** and permanently nonactionable, nonretained results. A real VCBS authenticated adapter/retention policy requires independent acceptance gates.

## Test and release status

- New offline tests verify six VCBS endpoint capabilities and fail-closed diagnostic RAW D1 parsing, unit/price basis mix-ups, null vs zero, volume scope, invalid OHLC, provisional state and unverifiable permissions. Existing full-suite tests must remain green on Python 3.11 and 3.12.
- TODO: source rights and retention evidence, provider endpoint/ACL/version/freshness audit, historical parity against SSI/DNSE on identical raw/adjusted and matched/total scopes, D1 close/session semantics, correction replay benchmark and production L1–L5 cache authorization. C1B is **NOT** end-to-end VCBS cache enablement.
- Original next phase GĐ4/P0.29 trusted provider source-rights chain remains independent and OPEN. Do not reuse revoked ChatGPT Work branches, change UI v1.0 or affect CK2, Forex, Scanner or MOCHI.
