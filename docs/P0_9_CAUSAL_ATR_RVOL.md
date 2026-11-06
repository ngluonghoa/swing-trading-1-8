# GĐ4/P0.9 — Causal Wilder ATR14 (D1) and RVOL_TF20 engineering primitives

Date: 2026-11-06. **Engineering-only / synthetic validation / nonactionable**.
Authoritative source: 01 MASTER_SPEC §§14.2–14.3 and 24.4, 05 DATA CONTRACT §§2, 17–18, and the canonical native Handoff §27.32.
Implementation: `src/swing_trading/causal_indicators.py`, tests `tests/test_causal_indicators.py`.

## What is actually implemented

1. `calculate_wilder_atr14()` returns the Wilder-smoothed **D1 ATR14 raw number**. There must be **15 source-qualified closed D1 bars** (one prior close for the first of 14 True Range observations). For each later bar:
   - `TR(t) = max(H(t)-L(t), |H(t)-C(t-1)|, |L(t)-C(t-1)|)`.
   - `ATR14_seed = mean(TR(t))` for the **first 14** eligible TR observations (15 complete source bars).
   - `ATR14_next = (13 * ATR14_previous + TR_next) / 14`.
   - A zero/negative ATR refuses to normalize; do not manufacture a small value.
2. `calculate_rvol_tf20()` returns **RVOL_TF, not RVOL_TOD**, using exactly 20 source-qualified comparable, closed bars of the **same timeframe and source lineage before the target**:
   - `RVOL_TF20 = target.volume / (sum(prior20.volume)/20)`.
   - The target is excluded from its own denominator. Zero target volume is numerically 0, **not** missing; a missing comparator volume or zero total comparator volume fails closed.
3. A typed immutable `VolumeComparisonBar` supplies explicit `session_class` (DAILY, CONTINUOUS, OPENING_AUCTION, CLOSING_AUCTION, SHORTENED) and a `comparison_policy_version`; they must match across target and history. These **caller-supplied labels have not been independently validated** against HOSE/HNX/UPCoM schedules. The calculation refuses to silently compare D1 with intraday or auction with continuous classes.
4. Both functions return `BLOCKED` or `COMPUTED_UNCALIBRATED`, with `data_certified=False`, `parameter_approved=False`, and `actionable=False` hard-coded. Values are **descriptive math**, not B5 phase passes, signal labels, trade advice, a licensed market dataset, or evidence of trading efficacy.

## Required source and causal checks

Every underlying `ResolvedBarSnapshotV12` must select **exactly one revision** visible as of the requested clock and satisfy `confirmation_prerequisites(as_of)`, `coverage_state=COMPLETE`, closed lifecycle, explicit verified quality, non-null volume, source evidence flags, verified calendar cutoff, and no quality flags. Some provenance flags can be asserted in fixture objects; **there is still NO independent SSI entitlement/cutoff verification**.

For ATR14, the selected rows must arrive sorted ascending, without duplicates or overlapping intervals, all D1. Every bar must share the same instrument, exchange, instrument class, timeframe, price basis, calendar version, aggregation policy, project/provider/origin/stream and adjustment revision. `known_before_utc` is a separate cutoff that rejects a later-known/retrieved/verified correction, even when that bar is visible in a subsequent scan; it is intended for the B5 **prior ATR** requirement.

For RVOL_TF20, 20 historical comparable source bars must also share the target's entire context (including adjustment revision), timeframe, session class and comparison policy. All comparator bars must be closed, first-known and **verified before the target bar starts**, not merely before the current scan. Duplicates, source conflicts, partial coverage, mixed basis, invalid time, late revisions, zero denominator or missing evidence block the calculation.

The code uses deterministic `Decimal` arithmetic and does not independently repair source chronology, provider revision conflicts or price adjustments.

## Explicit limits and intentionally unimplemented features

- **RVOL_TOD NOT IMPLEMENTED**: it requires comparable per-session, same exchange-local slot, real cumulative intraday volume, 20 matched previous session slots (subject to approved lookback/mincount), versioned auction/lunch/short-session semantics and source-entitled historical coverage. Do not replace it with `RVOL_TF20` or compare full-session volume to 15-minute volume.
- No independent **continuous trading-session calendar / completeness certificate** exists yet. Supplying 15 arbitrary D1 bars or 20 arbitrary same-TF bars can pass *structural* checks while omitting historical trading dates: the code cannot certify that the input period is gap-free or long enough for SSI. External source completeness is a separate gate.
- No official **Wilder ATR14 comparison against real market data** was performed. `COMPUTED_UNCALIBRATED` means only the arithmetic passed on the provided snapshots; a caller must not silently set B5/P0.8's ATR receipt to `verified=True`.
- No approved parametric RVOL breakout/low-volume threshold, risk policy, phase detector, 8-step actionable audit, simulation engine, real historical BT-01..16 or OOS/walk-forward.
- The SSI connector read-only intraday endpoint previously returned `DOWNSTREAM_UNAVAILABLE`, while Daily OHLCV worked; do not infer SSI historical absence or normalize partial intraday to verified. SSI B01–B08 remain OPEN.
- No changes to UI-1.0, CK 2.0, FX 2.0, Scanner, MOCHI or broker execution.

## Acceptance tests

`tests/test_causal_indicators.py` covers known-hand-computable Wilder ATR seed/smoothing and prior-close price gap, zero ATR, 14 vs 15 bar warmup, source/coverage/quality mismatch, no future known cutoff, stream/provider/adjustment/price-basis version mismatches, out-of-order/repeated bars and conflicting corrections.

RVOL tests cover exactly 20 comparators; target 0/2x/missing volume, zero history mean, same timeframe/source/segment policy, provisional/later-known comparator, target leakage, auction vs continuous, D1 vs intraday, explicit reason states and immutable no-action gates.

Tests are deliberately synthetic, not tests of real SSI price/cumulative volume or B5 profitability.

## Next

1. Build an approved source/calendar completeness certificate and sufficient D1/M15 history from a licensed provider; independently verify adjustment, native timestamps, revisions, gap/auction semantics and price basis.
2. Implement a separately versioned `RVOL_TOD` contract only with actual same-slot cumulative historic data and provider-specific original-data quality.
3. Reconcile ATR14 and RVOL_TF20 batch vs incremental/revised history, including a confirmed no-lookahead replay in both Signal and Backtest cores.
4. Present B5 R_C/R_E/R_F SHORT/SWING candidate parameter grids for approval; only then implement executable detector, simulator and the first qualified historical backtest.
