# GĐ4/P0.11 — RVOL_TOD20 causal same-slot contract and 2026 closure evidence anchors

Date: 2026-11-06. **ENGINEERING ONLY / SOURCE-CERTIFICATION PENDING / NO B5 DETECTOR**.
Canonical specifications: Master Spec §§14.2–14.3 (RVOL_TF vs RVOL_TOD and candidate lookback), 05 Data Contract §§2,17–18, Handoff §27.34.
Implementation: `src/swing_trading/rvol_tod_contract.py`, `src/swing_trading/vn_2026_closure_anchors.py`.
Tests: `tests/test_rvol_tod_contract.py`, `tests/test_vn_2026_closure_anchors.py`.

## RVOL_TOD math is not ordinary RVOL_TF

`RVOL_TOD20 = CUM_MATCHED_VOLUME(target, exchange_local_slot) / mean(CUM_MATCHED_VOLUME(previous 20 DISTINCT trading sessions, SAME exchange_local_slot))`.

- `target` and all 20 comparisons must be **individual CLOSED, source-qualified M1/M5/M15 v1.2 bar snapshots**, one market date each, visible as of the correct clock. Each observation provides an explicitly linked **cumulative volume through that slot**, not bar volume, not end-of-day volume.
- Distinguish `CumulativeVolumeDefinition.MATCHED_CONTINUOUS_ONLY` from `MATCHED_INCLUDING_AUCTIONS`. A source/provider cannot silently change definitions or count off-book volume in only some comparisons.
- Compare *exact local Vietnam slot end HH:MM* (source UTC converted at +07), identical interval timeframe, source stream, instrument/exchange, price basis, calendar/aggregation and adjustment revision. Session class (`CONTINUOUS/OPENING_AUCTION/CLOSING_AUCTION/SHORTENED`) and elapsed trading minutes must match; D1 and mixed DAILY are disallowed.
- Source `volume_event_id` must belong to the resolved bar's source_event_ids. Cumulative volume must be a nonnegative **int**, non-null and at least the selected source bar's per-bar matched volume. Cumulative evidence cannot predate source bar's end/verification and must be available by evaluation `as_of`.
- All 20 history observations must be from strictly older **distinct exchange-local trading dates and market session IDs**, in chronological order. Their source-bar and cumulative observations/revisions must have been **first known and verified BEFORE target bar starts**. A late revision discovered only when backtesting an old target is unusable.
- Zero target cumulative volume is a valid numeric `0` when underlying bar volume is also zero; an all-zero baseline is `ZERO_PRIOR_CUMULATIVE_DENOMINATOR` rather than infinite RVOL or fabricated 1. A missing/ambiguous/unqualified provider row never becomes a numeric 0.
- Exactly 20 history slots is a **candidate N** from the Spec, not an approved P15 threshold or proof these are the 20 immediately preceding *official* trading sessions. An external session-completeness certificate is still required before use in any detector/backtest.

**Outputs remain `BLOCKED` or `COMPUTED_UNCALIBRATED`**, with `data_certified=False`, `parameter_approved=False`, `actionable=False`; never DETECTED/NOT_DETECTED, signal strength, Entry/SL/TP, order or trade P&L. The source-linked cumulative count and session labels are supplied claims; this code does **not independently reconstruct cumulative volume from full raw M1/ticks**. A fixture can pass all structural guards while not representing a real exchange session.

## Primary-source HOSE/HNX 2026 published NON-trading dates

Independent cross-check found dated exchange announcements rather than relying on a generated weekday calendar:

- HOSE: [HOSE thông báo lịch nghỉ giao dịch năm 2026](https://www.hsx.vn/vi/tin-tuc/hose-thong-bao-lich-nghi-giao-dich-nam-2026/2437411), published 29/04/2026.
- HNX: [Thông báo lịch nghỉ giao dịch năm 2026](https://www.hnx.vn/vi-vn/chi-tiet-lich-nghi-gd-60021971.html?_page=1), published 03/12/2025, **and** [bổ sung nghỉ 02/01/2026](https://www.hnx.vn/vi-vn/chi-tiet-lich-nghi-gd-60022084.html?_page=1), published 25/12/2025. HNX's initial 01/01 notice must not override the later amendment.

The **scope-limited published closures** recorded in `vn_2026_closure_anchors.py` are 01/01, 02/01, 16–20/02, 27/04, 30/04, 01/05, 31/08–02/09, plus the Saturdays 10/01 and 22/08 (government make-up workdays on which exchange equity trading was still not held). They are **notice-derived date exclusions** for HOSE and HNX only. UPCOM is deliberately not inferred to be independently certified from HNX coverage.

`audit_2026_notice_closure_collisions(D1SessionInventory, exchange="HOSE"|"HNX")` converts the caller-supplied expected slot starts to Vietnam-local date, flags an expected D1 session placed on one of those announced non-trading dates, and refuses dates outside the year/notice scope. If no collision is found, the result is `NO_KNOWN_COLLISION_UNCERTIFIED`: **NOT** a declaration the other dates are valid trading days, and NOT a complete daily calendar/corporate action source.

Published notices are reference evidence as retrieved 06/11/2026; a production calendar must independently check current revisions, ad-hoc closures, market segment-specific rules, auctions, short sessions, IPO/symbol trading suspensions and licensed complete D1 history. Check independently against source records before any market-data certification.

## Regression tests and acceptance

- New synthetic no-lookahead tests for 20 prior **distinct sessions**, matching minute slot, segment class and elapsed minutes, source basis/stream/revision, missing cumulative data, all-zero comparison mean, zero target, future revisions, duplicate session, wrong M15→D1 substitution, stale source, source-event ID mismatch, wrong as-of clock.
- Exchange anchor tests exercise holiday exclusions, 02/01 HNX amendment and both Saturday make-up workdays, reject an out-of-year inventory and unsupported UPCOM attribution, and make explicit that a non-collision has no trading calendar certification.
- Test counts verify implementation arithmetic and structural contracts only. These are synthetic records, not a real SSI intraday extraction or historical BT-01..16/OOS, nor market-data entitlements.
- No changes to approved UI-1.0, CK2/FX2/Scanner, MOCHI or brokerage actions.

## Required for the next real-data step

1. Verify SSI B01–B08, endpoint/date order/first-known UTC+7 semantics, retained/licensed intraday market data, provider-native vs M1-derived volume, completeness of auction/lunch/short-day segments and actual cumulative matched volume. An intraday endpoint's previous `DOWNSTREAM_UNAVAILABLE` is NOT proof records are absent.
2. Obtain **complete versioned official HOSE/HNX/UPCOM trading-session calendar** with effective date/revision, market-segment rules and independent cross-check before certifying full expected D1 sessions or all 20 prior RVOL_TOD slots.
3. Rebuild the 20 historical same-slot cumulative figures from source-qualified M1/tick records, compare with provider cumulative values, test corrections/invalidation and require exact source event/volume definition parity. Only then consider detector input.
4. Submit separate B5 SHORT/SWING R_C/R_E/R_F parameter grids (P01–P17) for review and OOS calibration. Never implement executable signals or historical backtest until actual market data, risk/fill/fee/tax/slippage/T+2 simulator and governance gates are qualified.
