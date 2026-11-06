# GĐ4 / B5 causal feature pack — first detector preparation

Status: **ENGINEERING_FEATURE_EXTRACTOR_ONLY** (2026-11-06). This is the first scoped preparation for an executable detector, not the first approved detector, live signal, market-data approval or real historical backtest.

## Canonical rules (not rewritten)

Master Spec 01 §3 B5 and §24.4: **B5 Retest after Breakout** has R0: verified prior D1/H1 breakout event and pivot, R_C: retest of same pivot in a versioned window with ATR, R_E: verified M15 CLOSED reclaim/failed-break and R_F: verified H1/D1 support, micro high, volume and strategy risk. SHORT/SWING must be evaluated separately. P01–P17 thresholds, pivot/retest windows, ATR/RVOL and phase predicates remain **SPEC_PENDING**, with no arbitrary numerical defaults.

## Implemented code

- `src/swing_trading/b5_feature_pack.py` defines `PriorPivot`, `B5Features`, `B5FeatureAssessment`, and `extract_b5_features()`.
- Takes the same `ResolvedBarSnapshotV12` and `Strategy` shared by future Signal Engine and Backtest Engine; no separate backtest rule implementation.
- Requires a visible unique revision for the D1/H1 breakout and M15 retest; explicitly checks source/candle v1.2 confirmation prerequisites against the replay `as_of_utc`, pivot known-time, prior event ordering, market identity, price basis/calendar version and M15 closure. Future revisions are never selected silently. No lookahead pivot or breakout discovery after the purported event boundary.
- Extracts only **raw price differences** relative to pivot and the retest bar, with Decimal precision; it neither establishes a valid breakout/retest window nor substitutes for ATR/volume/RS, position protection, session policy, P01–P17 calibration, fill fees or settlement.
- The output state is `EXTRACTED_UNCALIBRATED`, `PRECONDITION_NOT_MET`, `DATA_UNVERIFIED` or `INPUT_BLOCKED`. **Every output has `detector_approved=False` and `actionable=False`; no method returns `DETECTED`, `NOT_DETECTED` trading decisions or entry/SL/TP.** Extracted features in synthetic tests do not verify real SSI entitlements.
- `tests/test_b5_feature_pack.py` covers SHORT/SWING, positive numerical feature values, no lookahead, late source verification, correction conflict, missing data, mixed instrument/basis, wrong timeframe, no prior breakout, invalid clock/types and explicit uncalibrated status.

## Known blockers

- **Not an executable B5 detector:** no approved rule thresholds/variant-specific predicates and no source-qualified event provenance or market calendar. The presence of B5Features must never be interpreted as a candidate trade.
- No real-source B5 playback, M15/M5 confirmation, detector cross-validation, fill/cost/settlement simulation, or historical BT-01..16/OOS. All SSI B01–B08 remain OPEN, in particular old intraday MCP coverage, direct FastConnect access and source timestamp semantics.
- No new production persistence, MOCHI access, UI changes, broker operations or CK2/FX2/Scanner dependencies.

## Next

1. Obtain approved per-variant B5 formulas and calibrated window/ATR/RVOL thresholds with explicit time-of-knowledge and source evidence, then implement R_C/R_E/R_F as versioned predicates **in the shared domain core**.
2. Pair the first executable tested detector with replay-ready, entitled price-basis-consistent history and trade simulation before the first historical backtest; follow three-layer quality, trade and OOS evaluation from Master Spec §24.14.
3. Continue SSI B01–B08 resolution separately; do not wait for all 16 detectors to be implemented before the first real backtest once a single complete detector is accepted.

**Synthetic CI PASS proves only code behavior. It is not a B5 signal hit rate, profitability, trading recommendation or live release acceptance.**
