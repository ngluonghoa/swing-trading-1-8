# GĐ4/P0.16 — SSI/DNSE read-only MCP transport bridge and provider-separated receipts

Date: 06/11/2026. **Engineering source adapter contract only. No production plugin deployment. Reference-only, nonactionable.**

Authority: Master Handoff §27.39, P0.15 reference-only router, 05 DATA CONTRACT §§2,17–18. Code: src/swing_trading/d1_mcp_transport_bridge.py. Tests: tests/test_d1_mcp_transport_bridge.py.

## Actual read-only connector response evidence

On 06/11/2026 the connected SSI marketdata_list_daily_stock_infor was checked again for SHS on 13/10/2026: response envelope contained status=ok, data.stocks, error and meta.asOfUtc. The exact-date row had OHLC 11600/11900/11500/11700 VND, total_match_volume 5,177,600. The response can contain the prior trading date: choose only the requested date.

Connected DNSE price_get_history for SHS returned data.t/o/h/l/c/v with 248 aligned DAY entries, plus nextTime; the envelope also had disclaimer and responseFormat. DNSE's 02:00 UTC (=09:00 VN local) daily timestamp is a session label, not a D1 close or provider first-known timestamp. DNSE price scales to thousand VND; historical price adjustment/corporate action policy is NOT independently certified. DNSE DAY cannot replace SSI M1/M5/M15 or qualify historical RVOL_TOD/B5.

## Implemented P0.16 Python bridge

ReadOnlyMcpD1Bridge accepts four injected inputs: authorized read-only SSI callable, authorized read-only DNSE callable, a UTC retrieval clock, and ProviderSeparatedReferenceCache. It calls the pre-existing P0.15 SSI-first D1 router. The library itself has NO network/client credentials and no ability to call MCP tools from GitHub Actions.

The SSI callable receives symbol, range=1d, toDate=DD/MM/YYYY, pageSize=5, pageIndex=1. Its response parser requires the observed status/data.stocks schema; chooses exactly one matching trading date; verifies symbol, positive finite decimal OHLC and nonnegative integer total_match_volume; sets price basis UNKNOWN. If SSI has usable receipt, DNSE is not called. Explicit DOWNSTREAM_UNAVAILABLE or absent exact date permits fallback; malformed SSI, unknown error, authorization error, invalid/request errors do NOT silently turn into DNSE fallback.

The DNSE callable receives symbol. Its payload data.t/o/h/l/c/v is wrapped as a historical snapshot with actual receipt clock and raw JSON digest; existing P0.15 parser selects the exact D1 session, verifies aligned arrays, ascending nonduplicated 09:00 local labels, OHLC geometry, integer volumes and converts thousand VND to VND without assuming raw/adjusted basis.

The D1 route refuses non-D1 BEFORE calling providers; rejects same-day D1 without verified close, future retrieval in retrospective as-of replay and source/date mismatches. A result is PRIMARY_SSI_REFERENCE_ONLY, FALLBACK_DNSE_REFERENCE_ONLY or BLOCKED. All signal/indicator/backtest/actionability/source-qualification fields stay FALSE.

BridgeRun includes immutable SourceFetchReceipt entries, ordered SSI then DNSE if fallback. Only provider, endpoint, instrument, venue, target date, retrieval time, response SHA256 and state (FETCHED, UNAVAILABLE, TARGET_DATE_ABSENT) are retained in the returned log; no raw response bodies, API keys or provider native source-event identifiers are invented. The digest is an ingestion checksum, NOT true native revision/first-known proof.

ProviderSeparatedReferenceCache is an explicitly namespaced, volatile in-memory DIAGNOSTIC quote cache, keyed by provider+symbol+venue+date+source snapshot digest. Provider must be specified when looking up; the D1 route never uses a cached quote automatically if the live provider fails. It is NOT licensed persistent historical storage, production Smart Cache L1–L5 or an authorization to coalesce SSI and DNSE feeds.

## Tests and deployment boundaries

New synthetic test suite covers real observed SSI/DNSE envelope shapes, SSI-first calls and fallbacks, unknown provider errors, malformed payload and volume, exact date handling, 09:00 timestamp and lookahead, missing/duplicate sessions, digest stability, provider namespace isolation and no false approval/production flags. GitHub Actions checks Python 3.11 and 3.12, synthetic tests only.

**Not implemented:** actual auto-wiring of user's authenticated ChatGPT MCP connector calls into a deployed long-running plugin runtime, persistent/cache database, source retention rights, actual provider native revision IDs or official market calendar, eligible historical source, B5 executable detector or actual backtest. Users may call both connectors in ChatGPT read-only; this Python library takes host-provided callbacks but cannot call the user-connected tools on its own. Do not claim automatic fallback is already live.

Next: obtain approved running environment and connect authenticated adapter transports; add durable provider-separated audit/cache with governance for retention/first-known, then independently verify source calendar and adjustment basis, and obtain licensed intraday data. SSI B01–B08 remain OPEN, B5 24 numeric slots NONE, BT-01..16/OOS NOT_RUN. No orders, UI-1.0 changes, CK2/FX2/Scanner/MOCHI edits.
