# GĐ4/C2C — Live-session telemetry readiness contract (offline foundation)

**Date:** 2026-11-07 (Saturday, Vietnam). **Status:** OFFLINE / SYNTHETIC ENGINEERING ONLY. Baseline: canonical Master Handoff §27.60, repository `main` commit `3a66ae57b2ea6e026997770b3121806fb74711b6`. Newly authored independently; no discarded Work branch or code reused.

## Why C2C cannot yet assert real live measurements

- The exchange is closed on Saturday; a Saturday historical read is **not** an in-session latency, availability, auction, finality, or freshness measurement.
- SSI D1 is coarse-day; SSI intraday re-fetches the session; DNSE D1 supplies full history; VCBS D1 accepts calendar dates; VCBS intraday exposes **price points**, not verified minute OHLCV. Their network and server workloads differ. C2B comparisons **cannot** establish a global fastest MCP.
- Connected MCP methods do not furnish independently authenticated vendor revision cursors, source rights, official exchange finality, or exact changed-since responses. A local cache can preserve computation work but does **not** prove 5-minute transport savings if the entire server response is re-fetched.

## Implemented offline contract

`src/swing_trading/c2_session_probe_readiness.py` and `tests/test_c2_session_probe_readiness.py`:

1. A `SessionProbe` is one metadata-only **caller-reported** observation. It binds typed provider and C2A endpoint to the same task, normalized ticker and HOSE/HNX/UPCOM venue, explicit request scope, Vietnam-local session date, caller-reported phase (including ATO/ATC/continuous/lunch), UTC observation, client-monotonic elapsed time, success/error class, returned/provisional/corrected-row **counts**. No market price/bar, credentials, account, source response, vendor revision or source-body content is emitted/persisted.
2. `ByteMeasurement.UNMEASURED`, `HTTP_RESPONSE_BODY`, and `NETWORK_WIRE_TOTAL` are different. Estimated reserialized JSON bytes cannot be labelled as wire traffic. A wire-number from a caller is only a reported measurement; trusted capture chain is still missing.
3. Optional provider timestamp is only an **unverified caller claim**. Results can count claimed timestamp-age >5 minutes, never certify source freshness or official close. The observed VN-local date must match; weekend samples are excluded from weekday coverage, but weekdays alone do not certify a live session, holidays or phase.
4. `summarize_session_probes` groups **exact provider + endpoint + task + ticker + venue + request scope + phase**. It derives descriptive within-group median and nearest-rank p95 only from >=5 nonempty successful samples. Failures and empty success are visible separately. Only >=5 truly reported NETWORK_WIRE_TOTAL samples show a separate median; neither HTTP-body nor JSON-estimated bytes qualifies.
5. `session_coverage` reports distinct weekday dates, reported continuous/auction phases, weekend exclusions and wire-sample counts. Missing evidence gates persist even if caller checks all boxes: exchange calendar and finality, authenticated provider entitlement/revision, equal server scope and validated live-session SLIs.
6. Every authority/release flag is **hard FALSE**: market-session verified, independent source timestamp, source integrity, cache rights, cross-provider SLA, network changed-since, router eligibility, trade actionability. `require_authorized_session_metrics` always refuses.

All fixtures use invented timing/count metadata; no provider API calls, quote downloads, real data persistence, scheduler, broker integration, UI changes or production deployment.

## Acceptance and next operational step

- Verify C2C unit tests and full existing test suite on Python 3.11/3.12 in GitHub CI before merging. The output is **readiness infrastructure**, not `LIVE_SESSION_VERIFIED`.
- During a **separately approved weekday market session**, on an authorized monitored client, perform bounded manual read-only probes on HOSE/HNX/UPCoM across continuous/auction and multiple days. Collect trusted monotonic timers, HTTP transport measurements with a declared byte basis, errors/limits, venue calendars, provisional/final rows and correction evidence. Respect entitlement/rate limits and never upload raw market payloads to GitHub/Drive.
- Request official per-provider adjusted/raw and matched/deal volume semantics; issuer data rights, account/product retention scope, signed current revocation stream and off-host monotonic custody. P0.29c is an **external blocker**. Only independently validated matched-task metrics may be reviewed for C1C routing; no blind auto-promotion.
- Keep the approved report UI DESIGN_LOCKED, SHORT/SWING, eight B/S zones per side, eight-stage audit and CK2/Forex/Scanner/MOCHI separations unchanged. No real 5-minute scan, licensed market L1–L5 cache or BT/OOS signal claims are enabled.
