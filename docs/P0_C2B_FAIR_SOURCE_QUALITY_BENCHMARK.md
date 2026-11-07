# GĐ4 / C2B — Three-source fair-workload and conditional D1 quality benchmark

**Date:** 2026-11-07, Asia/Ho_Chi_Minh. **Status:** READ-ONLY CONNECTED SAMPLE + OFFLINE BENCHMARK ENGINEERING; **NOT production trading data validation**. The authorized baseline is Master Handoff §27.59 on `main` commit `8f2915713038a00c3cb59b73567c80aedeab5d0c`. No code from discarded ChatGPT Work P0.29/F1 branches was used.

## Rationale: speed is not a fair comparison unless scope matches

SSI's connected MCP D1 detailed tool accepts coarse date ranges (`range=1d` includes target and previous session). DNSE connected `price_get_history` accepts **symbol only** and returns a full DAY history. VCBS `vcbs_get_history` permits `start_date` and `end_date` (calendar-bounded D1). Even when the *analytical target* is the same 2 sessions, the three APIs **return different payload sizes and server workloads**. Three or nine Saturday calls cannot establish fastest provider, normal-session p95, real availability/SLA, licensed streaming, or superior execution data. No connected tool has a verified changed-since cursor; no exact five-minute subday data fetch is established. Do NOT feed naive across-endpoint response times into the C1C adaptive router as comparable observations.

## New in C2B

- `src/swing_trading/c2_fair_source_benchmark.py`: pure Python module; `D1Target` requires exact symbol, venue and bounded common session range; `CallerReportedProbe` requires exact connected endpoint, task and request scope, records only elapsed time, row counts and approximate reserialized JSON bytes **from injected/synthetic metadata**. No MCP tool calls or persisted quote rows.
- `summarize_endpoint_probes` groups by **provider + endpoint + task + exact target + requested scope**, not by global provider. Reports purely descriptive median and nearest-rank p95 after ≥5 successful samples, within same scope. It can NEVER mark cross-provider latency comparable, live-session-verified p95 or router-authorized. Its `approximate_json_bytes` is NOT HTTP transport bytes.
- `TransientD1Row` accepts Decimal VND OHLC, integer shares, enumerated price basis (RAW/ADJUSTED/UNVERIFIED) and volume basis (MATCHED/TOTAL_WITH_DEALS/UNVERIFIED), exact venue, session date and provisional marker, **only in RAM supplied by caller**. Impossible OHLC, NaN, negative/boolean shares, date outside target and forged authentication flags are rejected before parity.
- `compare_transient_d1_pair` compares only overlapping, nonprovisional sessions on the *same* reported price basis or volume scope. Returns aggregated common/comparable/equal/different/excluded counts **without returning price values, raw rows, dates, symbol, or market payload**. Unknown or mismatched basis excludes affected days; no guessing DNSE RAW price provenance or VCBS matched-vs-negotiated volume. Results are `COMPARABLE_REPORTED`, never provider-certified, regardless of equality.
- No call to `require_benchmark_source_authority` can succeed. No SSI/DNSE/VCBS legal agreement, market-data retention, official exchange finality, source key/head trust, actual normalized M1 history, operational scanner/cache or broker action can be inferred.

## Direct read-only cross-check, outside session (Nov 7, 2026)

An actual connector read-only comparison was made with three representative venues: **FPT (HOSE), SHS (HNX), VGI (UPCoM)**. All nine endpoint calls succeeded. For **Nov 5–6, 2026** each instrument had two overlapping target sessions. SSI D1 returned 2 rows per symbol, VCBS RAW D1 2, DNSE DAY history 247. Only **aggregate counts** were retained for the engineering note; no vendor price, volume row, symbol-specific market sample or source response was written to GitHub, Drive, or synthetic tests.

| Comparisons on six symbol×day pairs | Result | Interpretation |
| --- | --- | --- |
| SSI RAW OHLC vs VCBS declared RAW OHLC | **6/6 numeric OHLC matches** | Useful provisional parity; **not source authority**, no proof of source revision/closure |
| SSI `total_match_volume` vs VCBS `volume` labelled matched | **2/6 volume matches** | FPT both days matched, SHS and VGI did not; **do not use VCBS as blind RVOL / liquidity volume substitute** |
| SSI RAW close vs DNSE numerically converted DAY close | **6/6 numeric matches** | DNSE's complete RAW vs adjusted basis **not independently proved**; result is *numerical observation only*, not authorized RAW OHLC parity |
| SSI `total_match_volume` vs DNSE DAY volume | **6/6 numeric matches** | DNSE's per-record volume scope **not independently certified**; this is not exchange/entitlement proof |

The past C1C report of 3 sequential probes per source had unequal server-side scopes. The C2A batch-call durations were shared, not independent. Therefore **no new cross-provider latency ranking** is claimed here. The new source inspection did not take place during market hours; it does NOT prove live quote reliability, timestamp first-known, minute aggregation, auction handling, p95, provider rights, or 5-minute network delta savings.

## Acceptance and fail-closed rules

1. **Comparable target != comparable server call:** same symbol/date/venue plus correct basis permits conditional DATA overlap analysis; latency is grouped by actual endpoint and request scope and cross-provider latency never declared equal from these MCP methods.
2. **No assumed corporate action basis:** SSI detailed `*_raw` and VCBS declared `priceBasis=raw` can be compared as reported. DNSE DAY basis unknown must stay `UNVERIFIED` until authenticated basis/revision document exists; no back-filling assumptions to make mismatches disappear.
3. **No volume conflation:** SSI `total_match_volume` excludes deal volume; VCBS `volumeScope=matched` is a vendor/tool label not an independent definition guarantee; DNSE scope unspecified. `MATCHED` vs `TOTAL_WITH_DEALS` is strictly noncomparable. SHS/VGI differences demand correction audit; zero volume can differ from missing.
4. **No provisional or impossible candles:** one invalid OHLC row blocks that input rather than silently normalizing it. `provisional=true` rows excluded. Auction ATO/ATC session status, official close, corporate-actions revision and historical first-known not externally certified.
5. **No persistent quotes / no source trust escalation:** all code/test fixtures are invented synthetic values, and result types contain only metadata statistics. `source_integrity_verified`, `exchange_authoritative`, `legal_retention_allowed`, `actionable`, cross-provider latency ranking, real p95 and `provider_sla_verified` are hard FALSE. P0.29c independently authenticated provider legal / key / fresh-head / off-host witness remains EXTERNAL BLOCKER.
6. **Full release regression:** new synthetic tests include typed endpoint/target, task isolation, counterfeit clock/rights assertions, sample minima, scope separation, p95 not SLA, invalid OHLC, volume basis, corporate action basis, provisional exclusion, no-overlap, duplicate days, no price payload in output, irrevocable denial of authority. Read local tests as engineering, not a substitute for external vendor QA. Verify GitHub CI Python 3.11 and 3.12, PR and postmerge main, before marking completed.

## Next recommended milestone C2C

- When the market reopens, **read-only live-session repeatable probes** covering HOSE/HNX/UPCoM, multiple days and session/auction phases, with per-call monotonic wall timing on actual authorized client and distinct serialization/transport byte measurements; collect **aggregate, metadata-only** observations and source error codes. Avoid automating calls without an explicit approved schedule/rate limit.
- Obtain provider-specific legal retention, adjusted/raw price semantics, matching/deal volume definitions, official close/finalization and provider revision / corrections and current product entitlements. SSI/DNSE/VCBS comparisons should be done for identical quality-certified target sessions; only the comparable task subset may be given to C1C dynamic ranking.
- Once separately authorized, implement incremental L1–L5 pipeline with windowed API only where available, local comparison for whole-session/full-history APIs, invalidation of affected indicator suffix, verified cold/warm parity and real bandwidth/CPU telemetry. Live persistence, 5-minute automatic scans, broker actions and real BT/OOS remain DISABLED until approved.

Preserve locked UI v1.0, SHORT/SWING, B1–B8/S1–S8, eight-step audits, CK2/Forex/Scanner/MOCHI separation and user ban on reusing discarded ChatGPT Work code.
