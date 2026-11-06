# GĐ4/P0.7 — B5 phase-evidence manifest / predicate-readiness contract

Date: 2026-11-06. Status: **ENGINEERING_ONLY / RECEIPTS_UNCALIBRATED**.
Canonical input: Master Spec `01` §24.4 B5 manifest, `B5_CAUSAL_FEATURE_PACK.md` and P0.2 v1.2 source lineage contracts.

## Why this increment exists

P0.6 added causal M5/M15 replay and B5's first feature extractor already measures raw distance relative to a prior pivot, but neither computes the full B5 R_C/R_E/R_F predicates. An executable B5 would also need a versioned pivot retest window, a verified prior ATR, an explicit M15 reclaim/failed-break branch and higher-timeframe support / micro-high / volume / risk confirmation.

A set of generic `verified=True` flags is insufficient. P0.7 therefore provides an immutable receipt manifest **without pretending the predicates, thresholds or SSI data rights are approved**.

## Canonical phases and ingredients

| Phase | Canonical predicate ref | Required evidence receipt |
| --- | --- | --- |
| R0 | `B5.R0.PRIOR_BREAKOUT_EVENT` | Existing B5 feature-extractor's pivot + D1/H1 breakout source qualification |
| R_C | `B5.RC.EXACT_PIVOT_RETEST` | `RC_PIVOT_RETEST` M15 same event; `RC_PRIOR_ATR` D1 closed, known before retest; `RC_WINDOW_POLICY` versioned policy reference |
| R_E | `B5.RE.M15_RECLAIM_OR_FAILED_BREAK` | `RE_M15_TRIGGER` same closed M15 retest bar, explicit `B5/E_RECLAIM` or `B5/E_FAILED_BREAK` branch |
| R_F | `B5.RF.RETEST_SUPPORT_BREAK` | `RF_SUPPORT_H1_D1`, `RF_MICRO_HIGH_BREAK` H1/M15 following retest, `RF_VOLUME` H1/D1, and `RF_RISK_POLICY` reference |

`RC_WINDOW_POLICY` and `RF_RISK_POLICY` are **references only**, not accepted numeric values, proof of an approved formula or a passed risk gate.

`M5` is still optional for entry precision; it cannot replace an M15 close or H1/D1 confirmation. `SHORT` and `SWING` are separately evaluated. The variants must not silently fall back from one to the other.

## Code and causal guards

- `b5_phase_contract.py` defines typed `B5Ingredient`, `B5PhaseReceipt`, `B5PhaseManifestAssessment` and `inspect_b5_phase_receipts()`.
- Input must first satisfy the existing B5 `EXTRACTED_UNCALIBRATED` base; missing or conflicting bars remain blocked.
- Every receipt binds the **same pivot event ID**, instrument, exchange, price basis and calendar version; bar receipts additionally require unique source-qualified v1.2 snapshots, declared fixture quality flags, exact source event ID membership, explicit timeframe, source revision and as-of-causal availability.
- Future-known receipts and revisions are rejected; prior ATR must already be known and verified before the retest begins; a claimed RF micro-high after retest cannot use an earlier/same retest bar.
- Duplicate ingredient receipts are rejected, even if one appears plausible; no silent latest-revision/provider selection.
- Missing items are `RECEIPTS_MISSING`, bad lineage is `RECEIPTS_UNVERIFIED`, and a full structurally present set is `PRESENT_UNCALIBRATED`.
- **Every output has `parameter_status=PARAM_CANDIDATE_NOT_APPROVED`, `detector_approved=False`, `actionable=False`.** No `DETECTED`, `NOT_DETECTED`, signal confidence, Entry/SL/TP, P&L, order or historical backtest.
- A receipt's numerical `observed_value` is caller-provided and never independently recomputed in this step. In particular, a positive ATR in a synthetic fixture is **not** validation of Wilder ATR14, warm-up, corporate actions, event window or tolerance.

## Tests and acceptance boundary

`tests/test_b5_phase_contract.py` provides synthetic positive/negative cases covering both strategies and both explicit E variants, missing/doubled receipts, future evidence, first-known vs verified-time, mismatched pivot/instrument/exchange/basis/calendar, event IDs absent from native source-bar event references, source-revision conflicts, bad timeframe, premature micro-high, missing/nonpositive ATR, invalid policy/UTC/type and source conflicts.

**STOP:** This is a receipt inventory, not executable B5 market logic. P01–P17 calibration, rule predicates for R_C/R_E/R_F, historical source provenance/entitlements, true retest event chronology, native/derived TF parity and market trading calendar remain unverified. SSI B01–B08 all remain OPEN; BT-01..16 and OOS/walk-forward remain NOT_RUN.

## Next action

Review and explicitly approve the mathematical definitions and per-strategy B5 variants, retest-window and ATR/volume/micro-high thresholds **with no-lookahead first-known-time policy**. Implement one truly executable B5 detector only after those decisions, with thorough unit and negative tests. Independently resolve enough SSI source rights/history/calendar and fill/fees/settlement simulation for the first real historical backtest. No UI-1.0, MOCHI, CK 2.0/FX 2.0/Scanner or brokerage changes.
