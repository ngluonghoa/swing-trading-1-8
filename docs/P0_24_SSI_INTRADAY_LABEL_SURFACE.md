# GĐ4/P0.24 — SSI historical intraday clock-label diagnostics and conservative gap audit

**Date:** 2026-11-06 (Asia/Ho_Chi_Minh). **Engineering scope:** read-only direct source probes plus synthetic testable diagnostics, **NOT** qualified M1/M5/M15 bars, historical replay, or real backtest.

## 1. New real source evidence (SHS, HNX)

| Called MCP method | Requested scope | Observed result | Meaning |
|---|---|---|---|
| SSI `marketdata_list_intraday_stock_infor` | `symbol=SHS, range=1d, toDate=14/10/2026` | `status=ok`, **223** ticks, **223 distinct textual time labels**, descending from `14/10/2026 14:45:00` to `14/10/2026 09:00:00` | Proves endpoint returned time-labelled observations for *this one query*, **not** source-native or complete M1 bars |
| Same SSI alternative endpoint, *descriptive label arithmetic only* | Label strings from 14/10, conditionally read as DD/MM | **16** differences >1 minute between consecutive distinct minute labels, longest **92 minutes** | NOT 16 lost bars. Local lunch, non-trading minutes, auctions, timestamp meaning, aggregation, and endpoint availability are not certified |
| SSI `marketdata_list_stock_infor` | `symbol=SHS, range=1d, toDate=13/10/2026` | **Second separately executed call** returned `DOWNSTREAM_UNAVAILABLE` | The full pagination/sysToken endpoint is still untestable in these two checks, but not proved permanently unavailable |
| Previously verified P0.23 | SHS 13/10 | Alternative SSI intraday **215** unique labels, SSI D1 **2 rows**; DNSE `price_get_history` **248 DAY** labels | No newly approved historical source, no data-rights or first-known evidence |

**Session context, not acceptance:** The [HNX official FAQ](https://cbinfo.hnx.vn/vi-vn/hoi-dap.html) describes HNX listed-equity continuous trading 09:00–11:30, 13:00–14:30 and the closing auction to 14:45. A large discontinuity spanning lunch is therefore expected from labels of actual events, not necessarily proof of missing candles. Still, the endpoint's labels may represent last events or aggregates rather than minute-start/end bars. The published HNX hours are venue context, **not** independent certification of complete SHS source records for 14/10/2026.

**Different services must not be conflated:** [SSI FastConnect Data API specifications](https://guide.ssi.com.vn/ssi-products/fastconnect-data/api-specs) list a separate `IntradayOhlc` product with a resolution parameter and a `dd/mm/yyyy` date schema. That is **not the same connected MCP action** we queried, and this account has not proved its licence, entitlements, historical retention rights, access credentials, quote revision timeline, or coverage. We have **not** called or connected the FastConnect `IntradayOhlc` API. The connected SSI MCP's description includes an `MM/dd/yyyy` example while actual SHS labels `14/10/2026` and `13/10/2026` necessarily fit DD/MM. This narrows observed date syntax for these samples but does NOT certify the general endpoint timestamp policy or what each label denotes.

**Privacy and data governance:** No raw OHLCV/volume/ticks, credentials, user token, original payload or downloaded price file were saved to GitHub, Google Drive, Mac, or SQLite. Only source method, requested session, state, row counts, textual label endpoints and *diagnostic* gap count/maximum appear in this record.

## 2. Code boundary

New `src/swing_trading/ssi_intraday_label_diagnostics.py` implements `inspect_ssi_intraday_surface(endpoint,response,symbol,requested_day,checked_at_utc)`. It reuses P0.23 `summarize_source_capability` to validate SSI type, row identity, bounded ephemeral parsed response (4 MiB) and UTC observation clock, then:

- Requires a typed SSI intraday allowlisted endpoint, explicit requested `datetime.date`, 10,000-row maximum, exact `xx/xx/yyyy HH:MM:SS` label syntax, valid clock components and consistent session/date-order candidates.
- Does NOT silently select MM/DD or DD/MM for ambiguous source labels. Returns a **conditional** date-order evidence classification. If both conventions can match, returns no minute geometry.
- For a consistently unambiguous conditional order only, counts distinct textual labels/minute positions, repeated minute labels, ordering (ASCENDING / DESCENDING / MIXED), number and size of gaps **between observed label minutes**. It does NOT fill slots, assume HNX session-calendar completeness, create OHLCV or a timestamped bar, or parse source labels into UTC market instants.
- Returns immutable `IntradayLabelDiagnostics` with no raw quotes or values, plus immutable hard-coded FALSE properties `timestamp_semantics_verified`, `observed_gap_is_missing_candle`, `publisher_first_known_verified`, `source_retention_rights_verified`, `eligible_for_m1_m5_m15`, `historical_backtest_qualified`, and `actionable`.

This **does not** approve market data, signal release, real backtests, live MCP hosting, or persistent SQLite/WAL. SSI and DNSE remain provider-partitioned within one reference-only logical store with quote persistence default OFF; the P0.18 signed metadata-only backup path remains unchanged.

## 3. Synthetic verification and next evidence gates

`tests/test_ssi_intraday_label_diagnostics.py`: conditional DD/MM vs MM/DD inference, fully ambiguous date labels, mixed conflicting formats, duplicate events within a minute, lunch-like 90-minute gap, invalid date/session/clock, wrong symbol/provider, empty/error response, row-size constraints, no raw quotes, no first-known/bar promotion, immutable unforgeable approval fields and conflict with P0.5 endpoint timestamp policy. Both Python 3.11/3.12 GitHub Actions CI must be green prior to merge.

**P0.25 next:**
1. Independently verify whether connected SSI/DNSE MCP (not another API product) exposes native historical M1/M5/M15 bars or an approved bar-construction procedure, with **source publication/first-known time** and revision handling. Verify timestamp date order, label semantics (start/end/last event), auction representation, zero-volume/no-trade and lunch/multi-venue calendars **without inventing missing candles**.
2. Explicitly obtain and document **provider/account rights** for historic data acquisition, long-lived cache, derivative aggregates and offline backtests. Public documentation and successful API calls do not establish contractual rights.
3. Review live SQLite native VFS/WAL and protected host volume, ACL/encryption, independent custody/signature pin. Existing P0.17 path-based writer remains NOT_DEPLOYED and not production-safe.
4. Keep B5 calibration 24 numeric slots, executable detector, cost/fee/fill/slippage/tax/T+2 simulator and historical OOS **NOT_RUN** until a complete, legally usable source and simulator exist.

**No UI changes** (UI-1.0 DESIGN_LOCKED), CK2/FX2/Scanner/MOCHI untouched, no orders.
