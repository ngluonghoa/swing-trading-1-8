# GĐ4/P0.13 — Multi-venue SSI sample matrix and B5 calibration preregistration

Date: 2026-11-06 (Vietnam). **Read-only observational SSI samples + synthetic-only engine checks. NONACTIONABLE.**
Canonical: Google Drive Master Handoff §27.36; 01 MASTER_SPEC §24 B5 / §§14.2–14.3 and 05 DATA CONTRACT §§2,17–18.
Code: `src/swing_trading/ssi_multivenue_review.py`, `src/swing_trading/b5_calibration_draft.py`.
Tests: `tests/test_ssi_multivenue_review.py`, `tests/test_b5_calibration_draft.py`.

## 1. Multi-venue SSI cross-endpoint read-only samples

Called `marketdata_list_intraday_stock_infor(symbol, range=1d, toDate)` and `marketdata_list_daily_stock_infor(symbol,range=1d,toDate,pageSize=5,pageIndex=1)` on 2026-11-06. Each daily response may contain two dates, so comparison selects the row whose `trading_date` equals **the exact queried date**. None of the intraday calls was a raw-tick historical FastConnect export. `sum(ticks[].volume)` is compared with **daily `total_match_volume`** only, not offer/bid volume or thỏa thuận.

| Symbol | Venue | Date DD/MM/YYYY | Intraday row count | Sum intraday volume | Detailed daily total_match_volume | Conclusion |
| --- | --- | --- | ---: | ---: | ---: | --- |
| SSI | HOSE | 13/10/2026 | 226 | 11,764,500 | 11,764,500 | EQUAL, UNCERTIFIED |
| SSI | HOSE | 14/10/2026 | 226 | 13,466,000 | 13,466,000 | EQUAL, UNCERTIFIED |
| DIG | HOSE | 13/10/2026 | 222 | 3,897,600 | 3,897,600 | EQUAL, UNCERTIFIED |
| DIG | HOSE | 14/10/2026 | 217 | 3,714,200 | 3,714,200 | EQUAL, UNCERTIFIED |
| VGI | UPCOM | 13/10/2026 | 142 | 99,200 | 99,200 | EQUAL, UNCERTIFIED |
| VGI | UPCOM | 14/10/2026 | 149 | 118,500 | 118,500 | EQUAL, UNCERTIFIED |
| SHS | HNX | 15/10/2026 | 233 | 16,614,500 | 16,614,500 | EQUAL, UNCERTIFIED |

Previous P0.12 samples SHS/HNX 12/13/14 Oct: 233/215/223 rows, totals 4,050,300/5,177,600/10,160,800, each matched the corresponding detailed daily volume. **Combined distinct sample evidence: 10/10 symbol-date records agree across HOSE (4), HNX (4), UPCOM (2).** This is a deliberately narrow diagnostic, NOT provider-independent validation: both endpoint families can share the same SSI upstream source.

Observed timestamps for HOSE SSI/DIG started 09:15, HNX SHS 09:00, UPCOM VGI 09:11 or 09:19 on these samples. This is merely the **earliest returned row**, NOT proof that an exchange session starts then. UPCOM first returned row varies, and any missing/no-trade minutes cannot be reconstructed from these samples. HOSE SSI/DIG last returned row 14:45, UPCOM VGI 14:59 in samples; these are not validated official session boundaries.

**Critical unresolved timestamp issue remains:** SSI MCP tool description documents `MM/dd/yyyy` but responses have `13/10/2026` and `14/10/2026`, unambiguously day-first strings for those rows. P0.12 requires explicit date layout in any parsed sample; P0.13 does not assert the provider's actual definitive parsing policy for all symbols or production history. First-known source timestamp, 20-session continuity, rights/retention, price adjustment and raw M1→M5/M15 parity still unverified.

## 2. P0.13 multi-venue review code

`SsiVenueSample` pairs a typed P0.12 intraday sample with its daily matched receipt.
`evaluate_ssi_venue_matrix(samples, as_of_utc)` *re-executes* the existing per-sample timestamp/volume checks, never trusts a caller-supplied PASS or total. It rejects duplicate `(venue,symbol,local-date)`, missing/empty/invalid source receipts, unsupported venue identity, inconsistent volumes, timestamps, future-fetched records and mixed venue/date. It reports per-venue counts plus blocked sample reasons.

- `ALL_VENUES_OBSERVED_UNCERTIFIED`: the **sample set** includes HOSE, HNX, UPCOM, and all per-sample totals match; not a full official calendar or source licence/coverage certificate.
- `PARTIAL_UNCERTIFIED`: every provided sample matches, but at least one venue has no sample.
- `BLOCKED`: empty matrix, unsupported/duplicate key or any failing P0.12 diagnostic.

Every output explicitly has `provider_independent=False`, `timestamp_semantics_certified=False`, `full_minutes_certified=False`, `source_entitlement_certified=False`, `suitable_for_rvol_tod=False`, `actionable=False`. Test fixtures exercise negative cases; observed SSI examples are documented evidence, not disguised synthetic source-qualified candles.

## 3. Preregistered B5 parameter grid — 24 cells, ALL EMPTY

The P0.8 SHORT and SWING symbolic formulas remain the authority for dimensions: separate **R_C window W**, **R_C ATR tolerance T**, **R_E M15 reclaim buffer E**, **R_F H1/D1 support buffer S**, **R_F micro-high breakout margin M**, **R_F volume RVOL ratio V**. The two explicit E variants are `B5/E_RECLAIM` and `B5/E_FAILED_BREAK`, and the latter independently requires a prior closed failed-break bar. This code defines 2 strategies × 2 variants × 6 axes = **24 separate candidate-value slots** in `build_b5_calibration_grid()`; it does not fill any candidate number. Units are `EXCHANGE_TRADING_SESSIONS`, `ATR14_D1_MULTIPLE`, or `RVOL_TOD_OR_APPROVED_RVOL_RATIO`.

The registry enforces `candidate_values=None`, `calibrated_value=None`, `parameter_approved=False` on **every slot**, and forbids merging SHORT/SWING variant identities, missing/duplicate axes, wrong units, fake threshold values or executable/approved flags. Risk/stop/entry/fee/tax/slippage/T+2 policy remains separate and **PENDING**, as do P01–P17.

A corresponding **four-protocol** registry (SHORT × SWING × 2 variants) records the required, still-NOT-RUN metrics:

- Signal frequency per eligible trading session; false alert rate, precision/recall with explicit labeling policy.
- Net expectancy after realistic execution/fees/slippage/tax, max drawdown, holdout stability, sensitivity to source gaps/basis/parameter perturbations.
- Pre-specified **train/validation/holdout isolation**, versioned official calendar, causal first-known replay and embargo/purge policy at leakage boundaries (architecture only, no actual data splits or execution).

No protocol can mark `holdout_selection_frozen`, `split_calendar_qualified`, `input_source_licensed`, `source_history_complete`, `first_known_replay_verified`, `fill_cost_settlement_simulator_approved`, `risk_policy_approved`, `oos_executed`, or `validation_approved` true. This is a **review-ready list of things to calibrate and verify**, not a calibrated parameter grid with working signals.

## 4. Acceptance, source blockers and next steps

GitHub Actions repeatable tests validate sample-matrix negative paths, 24 independent B5 slot identities/units and no-approval invariants. They do not prove a market source correct. Source B01–B08 remain OPEN, including previously observed `marketdata_list_stock_infor` raw/paged `DOWNSTREAM_UNAVAILABLE`, licence/retention, date-order/time semantics, independent historical archive, M1/M5/M15 session and auction/cumulative-volume correctness.

Next: obtain documented SSI timestamp semantics and official calendar/complete source history; reconcile independently reconstructed M1→M5/M15 native bars and provider cumulative slot volumes; design frozen train/validation/OOS/walk-forward split and label/fill assumptions for B5 SHORT vs SWING; submit candidate search ranges **for human approval before numeric search or detector execution**. Backtest needs executable tested B5 rules, licence-verified source and fill/cost/settlement simulator; no real historical BT-01..16 or OOS yet.

Do not change UI v1.0, CK 2.0, FX 2.0, Scanner, MOCHI, plugin UX or broker orders. Never promote SSI cross-endpoint volume parity or synthetic CI success to a verified trading signal.
