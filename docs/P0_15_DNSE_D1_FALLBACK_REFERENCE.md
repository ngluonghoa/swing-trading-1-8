# GĐ4/P0.15 — SSI-first / DNSE D1 read-only fallback router (REFERENCE ONLY)

Date: 2026-11-06 (Vietnam). **ENGINEERING PORT + LIVE READ-ONLY CROSS-PROVIDER EVIDENCE; NOT PRODUCTION ADAPTER WIRING OR TRADING SOURCE CERTIFICATION.**
Authority: native Master Handoff §27.38, 05 DATA CONTRACT §2/17/18 (source identity, price basis, first-known, lifecycle), 01 MASTER_SPEC §24/§24.14, P0.9 causal indicators, P0.11 D1 session inventory, P0.12–P0.14 SSI source observations.
Implementation: `src/swing_trading/dnse_d1_reference_fallback.py`; synthetic tests `tests/test_dnse_d1_reference_fallback.py`.

## 1. Read-only live MCP observations

Connector DNSE `price_get_history({symbol})` was independently invoked for **SHS, SSI, DIG, VGI** on 2026-11-06. Each result reported **248 parallel `o/h/l/c/v/t` DAY rows** spanning UTC daily-session labels `2025-11-07T02:00:00Z` to `2026-11-06T02:00:00Z`. The endpoint offers a one-year snapshot; it is NOT an M1/M5/M15 historical feed or source entitlement certificate. The same date's `t` at 02:00 UTC is 09:00 Asia/Ho_Chi_Minh and **identifies the daily session, not the time the D1 candle finished or first became known**.

Cross-check performed using SSI detailed daily `marketdata_list_daily_stock_infor` for SHS/SSI/DIG/VGI, with SSI VND vs DNSE displayed THOUSAND VND:

| Symbol / venue | Date | DNSE close (thousand VND) | SSI close (VND) | DNSE volume | SSI `total_match_volume` |
| --- | --- | ---: | ---: | ---: | ---: |
| SHS / HNX | 13/10/2026 | 11.7 | 11,700 | 5,177,600 | 5,177,600 |
| SSI / HOSE | 13/10/2026 | 18.9 | 18,900 | 11,764,500 | 11,764,500 |
| DIG / HOSE | 13/10/2026 | 9.5 | 9,500 | 3,897,600 | 3,897,600 |
| VGI / UPCOM | 13/10/2026 | 77.3 | 77,300 | 99,200 | 99,200 |

The sampled 14/10/2026 DNSE volumes for SHS (10,160,800), SSI (13,466,000), DIG (3,714,200), VGI (118,500) also agree with previously checked SSI intraday/daily totals, but this read-only check does not establish complete daily calendars or entitlement.

**Historical SSI intraday gap dates still have DNSE D1** for SHS: 11/02/2026 (7,871,600), 13/04 (24,550,600), 01/07 (7,136,100), 14/08 (20,060,800), 01/10 (9,839,500). All are D1 snapshot volumes matching the observed SSI detailed daily totals; **none** is a replacement for missing SSI intraday rows. The absence of intraday on those dates remains B06 evidence OPEN.

**Price adjustment caution:** On 11/02/2026 SHS, SSI adjusted close is 17,573.49 VND whereas DNSE returns 17.57 thousand VND (17,570 VND). On 01/10 SSI adjusted close is 12,771.99 VND vs DNSE 12.77 thousand (12,770 VND). Both are close but **not exact**; DNSE's raw/adjusted/corporate-action revision/basis is not independently specified by the plugin response. Neither equality to SSI at another date nor thousand-to-VND normalization proves the same price basis or source independence. No tolerance-based promotion to “verified” is permitted.

## 2. Implemented fallback port and deterministic route

`D1ReferenceRequest(symbol,exchange,timeframe,session_date_local,as_of_utc)` and `route_d1_reference(request,fetch_ssi,fetch_dnse)` implement **actual read-only source selection control flow with injected adapters**:

- Explicitly refuse `timeframe != D1` **BEFORE invoking any adapter**. M1/M5/M15/M30/H1/W1 cannot be synthesized from DNSE DAY.
- When the requested trading date is the present or a future Vietnam-local calendar day, refuse it without independently verified close evidence. This deliberately conservative P0.15 port does NOT treat DNSE's 09:00 daily label as a closed D1 bar; same-day D1 support requires a separately designed verified exchange cutoff/first-known receipt.
- Call SSI first. A typed SSI D1 reference quote uses `marketdata_list_daily_stock_infor` and VND, same symbol/venue/day. If supplied and known by evaluation as-of, prefer SSI and do NOT invoke DNSE. If SSI returns missing `None` or raises the declared `D1SourceUnavailable`, call DNSE as a fallback; unexpected adapter exceptions propagate rather than being silently reclassified as missing data.
- DNSE adapter returns `DNSEHistorySnapshot(data,observed_at_utc,source_snapshot_id)` containing the exact received parallel `t/o/h/l/c/v` arrays. Parser enforces nonempty equal arrays, strict ascending unique Unix seconds, 09:00 Vietnam-local DAY label, exact requested local date, finite positive Decimal OHLC geometry, nonnegative integer volume, and unit `THOUSAND_VND` normalized by `×1000` only when reading the quote.
- The DNSE `price_basis` is forced `UNKNOWN`. All snapshots are tied to their **actual ingestion clock**, not a made-up historical first-known time or fabricated source native record ID. Reject future-retrieved primary/secondary snapshots when doing as-of replay.
- If source is missing for the exact date, malformed, unknown time label, mismatched SSI identity or not causally fetched, return `BLOCKED`. Source conflicts are never silently “repaired” by switching provider when a nonmissing SSI receipt contradicts the requested symbol/date.
- A successful selection is **`PRIMARY_SSI_REFERENCE_ONLY`** or **`FALLBACK_DNSE_REFERENCE_ONLY`**, both **NOT** certified/eligible for a v1.2 action indicator, ATR14, RVOL or real historical BT. The router returns the original provider quote/metadata, not a mixed provider candle. Source, snapshot and unit stay in the result.

`compare_ssi_dnse_d1` is a **diagnostic**: checks identical symbol/venue/day; exact matched-volume counts and normalized VND price equality. For the DNSE endpoint, price basis is always `UNKNOWN`, so even if all OHLC and volumes match perfectly the result is `VOLUME_EQUAL_PRICE_BASIS_UNVERIFIED`. If volume differs it is a `SOURCE_VOLUME_OR_PRICE_CONFLICT`. Never “certify” the feed from cross-provider agreement; the providers may use the same upstream exchange data.

`D1ReferenceAudit` permanently sets `data_certified=False`, `market_calendar_certified=False`, `source_rights_verified=False`, `first_known_for_history_verified=False`, `eligible_for_indicators=False`, `eligible_for_backtest=False`, and `actionable=False`. This is a safe engineering intermediate receipt, not a reason to turn on BUY/SELL/No-Trade logic.

**Not yet wired to a production/plugin runtime:** The GitHub Python module is a deterministic source selection port; the caller injects read-only authenticated MCP_SSI and MCP_DNSE adapters. ChatGPT's connector authentication/actions are not directly usable inside plain GitHub Actions code. The actual live automatic dual-provider plugin wiring, historical source persistence, licensed terms, approved calendar and revisions remain separate OPEN deliverables. Do not represent this module as an already deployed and automatically switching user-facing plugin.

## 3. Tests, acceptance boundaries and follow-up

P0.15 synthetic tests cover primary-first call order, SSI unavailable → DNSE fallback, no access to DNSE for intraday, same-day close guard, source session identity, future receipt/lookahead, prior as-of replay restrictions, missing target dates, strict Unix timestamp and array ordering/length, malformed price/volume, thousand-to-VND conversion, unknown price adjustment basis, SSI/DNSE volume mismatch and source unapproval flags. Test counts prove **software invariants only**; the live read-only connector observations above are evidence samples, not full source parity or exchange calendar certification.

Next:
1. Build genuine read-only adapter wiring only in an approved runtime with connected SSI/DNSE credentials and noninteractive source error normalization. Log fetch time, endpoint, original payload digest and provenance. Use separate provider namespaces in cache/SQLite, never coalesce into one source stream.
2. Independently verify DNSE corporate-action price adjustment semantics, 09:00 D1 label, source licence/retention and calendar/official close availability, and compare against SSI on more symbols including split/dividend days. Without verified first-known/source record IDs, do not claim historic replay.
3. For intraday SSI gaps, find a **licensed verified intraday feed**; DNSE's one-year DAY OHLCV cannot produce historical M1/M5/M15, cumulative matched-volume RVOL_TOD or B5 M15 confirmation.
4. Continue B5 SHORT/SWING label-policy/embargo and P01–P17 review when source/holdout/simulator gates are qualified. 24 numeric parameter slots remain empty, BT-01..16 and OOS NOT_RUN.

No UI v1.0 edits, MOCHI, CK2/FX2/Scanner changes, platform deployment, brokerage orders or automatic live signals.
