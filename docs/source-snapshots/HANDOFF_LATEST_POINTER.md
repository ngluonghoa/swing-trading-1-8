# Swing Trading 1.8 — Latest Master Handoff

Canonical Google Doc: https://docs.google.com/document/d/1TBGth5NXh-pPYRemsFIKeNjm1_VPhrFAWMsslALq9FI/edit

**Latest decision: §27.34 / GĐ4 — D1 expected-session inventory and ATR14 append/correction replay parity**, 2026-11-06.

The [full-text GitHub snapshot](00_MASTER_HANDOFF.txt) was refreshed from the canonical Google Doc through §27.34. It is a **point-in-time plain-text copy**, not an automatic two-way synchronization. Exact equality must be checked on `main` after merge, and the native Google Doc remains authoritative for later changes.

Editorial reconciliation on 2026-11-06 corrected stale read-first / PRE-CODE wording, a stray foreign-language token in §27.29 and obsolete sync-as-TODO wording in §27.28–§27.30. That editorial correction did not itself advance the technical milestone (which has since progressed to §27.34).

- P0.1–P0.4C: source/calendar contracts, quality axes, legacy quarantine, local SQLite evidence and independent-checkpoint candidate mechanism (no production storage or external custody deployed).
- P0.5 [SSI B01–B08 read-only audit](../P0_5_SSI_SOURCE_TRIAGE.md), [PR #18](https://github.com/ngluonghoa/swing-trading-1-8/pull/18) merge `700bf781afbf432bfe8c6a5b3ff56c1f4aa9de0d`: **all source blockers remain OPEN**, FastConnect access/long intraday replay not verified.
- **B5 first-detector preparation:** [PR #20](https://github.com/ngluonghoa/swing-trading-1-8/pull/20), merge `65550a2b54d672c37dc5d804ea15fe38d370db56`, [main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42168305891) 117/117 tests PASS each on Python 3.11 and 3.12.
- [B5 feature pack details and limits](../B5_CAUSAL_FEATURE_PACK.md): shared causal/as-of features for SHORT/SWING, no approved P01–P17 calibration and no B5 R_C/R_E/R_F executable predicates. All states remain uncalibrated/nonactionable.
- **P0.6:** [PR #22](https://github.com/ngluonghoa/swing-trading-1-8/pull/22), merge `9a1f367df67ebb1090dfb9d64ad5bdf954c8682d`, [main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42172733020) 128/128 synthetic engineering tests PASS on Python 3.11 and 3.12. [M5/M15 replay details](../P0_6_M5_M15_REPLAY.md): identical-retransmission dedup, future-correction isolation and identity-collision blocking; no SSI source qualification or executable detector.
- **NOT RUN:** real historic backtest, OOS/walk-forward, detector hit-rate evaluation, fill/cost/settlement simulation, live signals, brokerage actions, or production persistent storage.
- NEXT: approve first detector predicates/threshold process, independently verify SSI source coverage/rights/time semantics and realistic simulator; first historical backtest can start after one fully tested executable detector, not all 16.
- MOCHI backup deferred, UI-1.0 DESIGN_LOCKED; CK2/FX2/Scanner unchanged.

- **P0.7:** [PR #25](https://github.com/ngluonghoa/swing-trading-1-8/pull/25), main merge `e3b49a35a8ddc07f0f450a2343b32451a543a721`; [main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42176318156) **147/147 PASS** on Python 3.11 and 3.12. [Phase receipt contract](../P0_7_B5_PHASE_EVIDENCE_CONTRACT.md) adds source/clock/variant prerequisite checks, not executable predicates or data entitlement/Backtest approval.

- **P0.8:** [PR #27](https://github.com/ngluonghoa/swing-trading-1-8/pull/27) merge `4e5f50844f96a0dc2bf05eb19c63c06fe1cab2f7`, [main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42178103421) **163/163** synthetic engineering tests PASS each on Python 3.11 and 3.12. [Formula draft](../P0_8_B5_FORMULA_DRAFT.md) separates SHORT/SWING unapproved slots, causal geometry and explicit E variants. No executable detector, source-qualified SSI historical backtest, OOS or trade authority; B01–B08 OPEN and SHS B06 read-only calls returned DOWNSTREAM_UNAVAILABLE.

- **P0.9:** [PR #29](https://github.com/ngluonghoa/swing-trading-1-8/pull/29), main squash merge `0500727721ce9ec3d9ee9113cf88343ce2764f9e`, [main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42182737356) **190/190** synthetic tests PASS on Python 3.11 and 3.12. [ATR14/RVOL_TF20 contracts](../P0_9_CAUSAL_ATR_RVOL.md) use causal source guards but do not certify SSI entitlement/history/session completeness or actionable B5. RVOL_TOD and historical backtest/OOS remain NOT_RUN; B01–B08 OPEN.


- **P0.10:** [PR #31](https://github.com/ngluonghoa/swing-trading-1-8/pull/31), main merge `e6ab560fdba1a26ad2774c20823446a5eef5a28b`; [main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42184622891) **214/214 PASS** on Python 3.11 and 3.12. [D1 expected sessions and ATR replay contract](../P0_10_D1_SESSION_ATR_REPLAY.md) detects input-vs-manifest gaps and verifies batch/replay exact Decimal parity, but external calendars remain unverified and outputs nonactionable. SSI B01–B08, calibrated detector, RVOL_TOD and real historical backtest/OOS remain OPEN/NOT_RUN.
