# GĐ4/P0.5 — SSI read-only source triage and fail-closed qualification

**Date:** 2026-11-06 (Asia/Ho_Chi_Minh).
**Status:** READ_ONLY_SAMPLES + ENGINEERING_TESTS; **NOT** source-certified, licensed historic replay, or live-ready.
Canonical blockers: 05_GD3_DATA_CONTRACT_SMART_CACHE_ARCH §13 and 00_MASTER_HANDOFF §22.9/§27.27.

## Source channels and limitations

The user-connected **SSI MCP** exposes `marketdata_list_stock_daily_data`, `marketdata_list_daily_stock_infor`, `marketdata_list_intraday_stock_infor`, `marketdata_list_stock_infor`, and index/adjustment tools. These are **NOT automatically equivalent to direct FastConnect v2/v3** APIs or to a licensed historical bulk data entitlement.

SSI official developer docs:
- https://developers.ssi.com.vn/docs/faq/market-data describes daily and intraday history with differing retention/access patterns and possible bulk download;
- https://developers.ssi.com.vn/docs/getting-started/terms-and-environments lists API registration, scopes, credentials/limits and historical service boundaries;
- https://guide.ssi.com.vn/ssi-products/fastconnect-data/api-specs describes **FastConnect v2**, whose request/response `TradingDate` notation is `dd/mm/yyyy`. This is **not** evidence of the SSI MCP connector's internal native date fields.

Never copy source credentials, session tokens, proprietary payload archives or unlicensed historic data into GitHub. All calls in this audit were read-only and sampled narrowly.

## Direct SSI MCP observations in this turn (read-only)

| Blocker | Specific observation / evidence | Current decision |
|---|---|---|
| B01 — SHS open | 04/11/2026 D1 compact and full `open=12400`; 235 returned intraday rows, earliest displayed 09:00 `open=12300`; difference **100 VND** | OPEN: unclear daily session open versus first intraday minute/auction; no correction assumed |
| B02 — VGI open | 04/11/2026 D1 compact `open=75000`; 143 intraday rows, earliest displayed 09:00 `open=74500`; difference **500 VND** | OPEN: do not silently replace either value |
| B03 — VNINDEX volume | 04/11/2026 D1 index `volume=785061515`; previous handoff M1 aggregate `785061420` (difference **95**) was **not replayed in this turn** | OPEN: precise intraday calendar/aggregation/revision parity still required |
| B04 — missing M1 slots | Previous audit: HNX missing **6/240** slots; UPCOM **127/270**. **Not independently recalculated in this turn** | OPEN: lack of ticks is not no-trade or proof of missing vendor data; require validated calendar/no-trade evidence |
| B05 — native TF | No direct native M5/M15/M30/H1 parity, H1 session partial, HOSE auction, HNX PLO or UPCOM after-hours validation in this turn | OPEN |
| B06 — long history | SHS intraday 01/09/2026 and 01/10/2026: `ticks=[]` from successful SSI MCP queries; 13/10/2026: **215 rows**; 04/11/2026: **235 rows**; SHS daily 01/09/2026 also returned `stocks=[]` in sampled request | OPEN: MCP access window **not proven adequate** for M5/M15 multi-month backtest; an empty API response is UNKNOWN, not no-trade |
| B07 — benchmark/CA/matched value | Sector benchmark history, CA adjustment factors and exact matched intraday value/VWAP not validated | OPEN |
| B08 — price basis | Compact daily endpoint describes adjusted OHLCV; full daily returns `close_price_adjusted` and `open_raw/high_raw/low_raw/close_raw`; intraday raw-basis parity not approved | OPEN: do not join ADJUSTED D1 and RAW M1 without independent mapping |

**Timestamp-format contradiction:** SSI MCP tool metadata describes intraday `trading_date` as MM/dd/yyyy HH:mm:ss, but the actual response for the explicitly requested **13/10/2026** contains `13/10/2026 09:00:00`. This is unambiguously day-first at the **connector output** layer (13 cannot be a month). Neither this response nor the FastConnect v2 docs establish that every MCP endpoint or provider-native timestamp uses day-first. For an ambiguous `04/11/2026`, blind MM/DD parsing would switch November 4 to April 11; prohibit that. Separately, even a resolved date does NOT establish whether time is the beginning/end of a candle or the last trade.

Observed as-of dates in the SSI MCP responses were 2026-11-06 around 04:54–04:56 UTC. Data were read only, summarized in this audit; full raw tick responses were **not** committed to the repository.

## Implemented P0.5 engineering contracts

- `src/swing_trading/ssi_source_qualification.py` defines versioned `EndpointTimestampPolicy` with independent `documented_date_order`, `observed_date_order`, source-review confirmation, and *separate* minute clock label confirmation. No global date guessing; contradictory or unverified formats return blocked `TimestampAssessment`. Daily date never synthesizes a timestamp or closing cutoff.
- `SourceCoverageObservation` distinguishes records observed, zero-row UNKNOWN, and request errors, while deliberately never granting long-term historical coverage from a single page/date.
- `DailyFirstRecordParity` keeps both observations and their delta without auto-repair; equality is **MATCH_UNVERIFIED**, not approved parity.
- `DailyVsMinuteVolumeParity` preserves unknown pagination and discrepancy even at **95 units**, with no hidden tolerance.
- `SessionMinuteSlots` explicitly classifies missing slots as `MISSING_UNCLASSIFIED` until session/no-trade evidence exists.
- `cross_timeframe_price_basis()` blocks RAW/ADJUSTED or UNKNOWN joins without separate adjustment lineage. Even where types align the gate remains observational only.
- `tests/test_ssi_source_qualification.py`: offline negative/unit tests on these contracts. **No network calls or SSI data credentials in CI.**

## Unresolved external approval gates

1. Confirm SSI MCP **per-endpoint** timestamp spec, normalized display format, native date/clock meaning and `asOf`/first-known semantics with official source/owner. Do not infer from samples alone.
2. Verify direct FastConnect/bulk access under user's own authorized scope, retention, complete pagination, rights to store/replay and any rate limits. No API credentials were created or requested.
3. Independently validate real HOSE/HNX/UPCOM session schedules and auction/PLO/after-hours gaps; reconcile D1/M1 raw vs adjusted basis and corporate actions; compare native vs derived M5/M15/H1.
4. Obtain a rights-cleared, replayable D1/M1 history and one executable detector plus fill/slippage/fees/tax/settlement simulator before **first real backtest**. Backtest only that first tested detector; no need to wait for all 16.
5. Storage production volume, external evidence checkpoint custody, encryption/ACL, offsite recovery and first-known source revisions still need approval/acceptance. MOCHI backup deferred; UI-1.0 locked; no CK2/FX2/Scanner changes.

**B01–B08 remain OPEN.** Passing P0.5 synthetic tests must NEVER be reported as successful historical backtest, out-of-sample efficacy, live signal validation or completion of data entitlements.
