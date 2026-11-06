# Swing Trading 1.8 — Latest Master Handoff

Canonical Google Doc: https://docs.google.com/document/d/1TBGth5NXh-pPYRemsFIKeNjm1_VPhrFAWMsslALq9FI/edit

**Latest decision: §27.29 / GĐ4 — B5 first detector feature pack**, 2026-11-06.

The [full-text GitHub snapshot](00_MASTER_HANDOFF.txt) was refreshed from the canonical Google Doc through §27.29. It is a **point-in-time plain-text copy**, not an automatic two-way synchronization. Exact equality must be checked on `main` after merge, and the native Google Doc remains authoritative for later changes.

- P0.1–P0.4C: source/calendar contracts, quality axes, legacy quarantine, local SQLite evidence and independent-checkpoint candidate mechanism (no production storage or external custody deployed).
- P0.5 [SSI B01–B08 read-only audit](../P0_5_SSI_SOURCE_TRIAGE.md), [PR #18](https://github.com/ngluonghoa/swing-trading-1-8/pull/18) merge `700bf781afbf432bfe8c6a5b3ff56c1f4aa9de0d`: **all source blockers remain OPEN**, FastConnect access/long intraday replay not verified.
- **B5 first-detector preparation:** [PR #20](https://github.com/ngluonghoa/swing-trading-1-8/pull/20), merge `65550a2b54d672c37dc5d804ea15fe38d370db56`, [main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42168305891) 117/117 tests PASS each on Python 3.11 and 3.12.
- [B5 feature pack details and limits](../B5_CAUSAL_FEATURE_PACK.md): shared causal/as-of features for SHORT/SWING, no approved P01–P17 calibration and no B5 R_C/R_E/R_F executable predicates. All states remain uncalibrated/nonactionable.
- **NOT RUN:** real historic backtest, OOS/walk-forward, detector hit-rate evaluation, fill/cost/settlement simulation, live signals, brokerage actions, or production persistent storage.
- NEXT: approve first detector predicates/threshold process, independently verify SSI source coverage/rights/time semantics and realistic simulator; first historical backtest can start after one fully tested executable detector, not all 16.
- MOCHI backup deferred, UI-1.0 DESIGN_LOCKED; CK2/FX2/Scanner unchanged.
