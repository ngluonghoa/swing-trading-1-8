# GĐ4/P0.8 — B5 symbolic formula draft and causal raw geometry

Date: 2026-11-06. **Status: DRAFT / UNCALIBRATED / NONACTIONABLE.**
Authority: 01 MASTER_SPEC §24.4 B5 phase manifest, §14.2–14.3 candidate formulas,
05 DATA CONTRACT candle quality and 06 M15/M5 Replay. Builds on P0.7.

## Why this step

P0.7 only checks that R_C/R_E/R_F *receipts* are present and source-linked.
It does not calculate ATR14, RVOL, the true retest distance/elapsed market
sessions or any phase predicate. This increment freezes a mathematical
**proposal**, implements only side-effect-free descriptive signed geometry and
formalizes the missing data/approval dependencies before a real detector.

The signed ratios below are not detection verdicts and **do not approve P01–P17**.

## Raw quantities: mathematically deterministic, NOT calibrated

Let `p` be the source-linked former breakout pivot (same instrument, price basis
and official calendar version); `a` a verified closed D1/H1 breakout bar; `b`
the verified closed M15 retest bar; `f` an M15/H1 follow-up bar closing later;
`h` a causally confirmed closed M15 micro-high anchor **known before** `f`
starts; and `A > 0` the candidate pre-retest ATR_D1 *receipt* from P0.7.

| Raw feature | Formula / meaning |
| --- | --- |
| breakout strength | `(a.close - p) / A` |
| signed retest penetration | `(b.low - p) / A`; negative means wick below pivot, not necessarily false break |
| signed reclaim close | `(b.close - p) / A` |
| recovery from intrabar low | `(b.close - b.low) / A` |
| H1/D1 support-close margin | `(support.close - p) / A` |
| follow-up micro-high margin | `(f.close - h.high) / A` |
| follow-up volume | Source `volume` count only, **NOT** RVOL |
| event elapsed duration | `(b.endUTC - a.endUTC).total_seconds()`; **NOT** trading-session count |
| failed-break antecedent | `(e.close - p) / A` from independent closed M15 `e`, if explicit variant `B5/E_FAILED_BREAK` |

P0.8 **does not recalculate Wilder ATR14**: the positive `A` is a
caller-provided P0.7 receipt and has not been independently confirmed against
a complete source-qualified D1 warmup. It cannot be used for actionable
confidence/position sizing. RVOL requires verified same-TF historical
comparators; historical length, bar/auction volume semantics, corporate
adjustment and the eligible session slots are still OPEN.

## Proposed predicates (not executed)

**R0**, unchanged: D1/H1 event `BREAKOUT_VALID` must have confirmed pivot
event_id, causal occurrence/first-known/revision, price basis, session and
separately approved breakout/volume conditions.

**R_C** (for each `strategy` separately):
`RETEST_OK(strategy) := pivotKnownBeforeBar AND atrVerifiedBeforeBar
AND officialSessionCount(a,b) <= W_strategy
AND minDistance(b.low,p,A) within T_strategy
AND invalidationNotSeen`.
Here `W_strategy` (eligible trading-session count), `T_strategy`
(ATR tolerance), the precise min-distance boundary, window starts, the
market-session calendar and invalidation conditions remain **proposed
parameters/definitions requiring approval**. P0.8 computes only signed
distance and elapsed wall seconds; it never evaluates RETEST_OK.

**R_E — explicitly chosen variants:**
- `B5/E_RECLAIM`: a verified M15 CLOSED candle closes back on the accepted
  side of `p + E_strategy*A`, with source-lineage causal and calendar validity.
  Intra-bar wicks or M5 provisional updates do not qualify as CLOSED.
- `B5/E_FAILED_BREAK`: in addition to a later M15 CLOSED reclaim, an
  **independent earlier closed M15** bar has a source-qualified close below
  the pivot, is known before the reclaim bar starts and occurs *after*
  the original breakout. A single M15 long lower wick cannot masquerade
  as a preceding closed breakdown. Choose variant explicitly, no fallback.

`E_strategy` and exact boundary/equality, number of bars and expiry policy
are **not yet chosen**. Receipt existence / signed close cannot certify either
variant, including in synthetic tests.

**R_F** (each strategy):
`SUPPORT_HOLD := VERIFIED_CLOSED(H1/D1) AND support.close >= p-S_strategy*A`;
`MICRO_BREAK := VERIFIED_CLOSED(f) AND f.close > causalMicroHigh + M_strategy*A`;
`VOLUME_OK := approvedVersionedRVOL(data) >= V_strategy`;
`RISK_OK := approved(position, liquidity, tick, price-limit, T+2,
maxEntry, stop/TP, netR:R, fees, tax, slippage, fill)`.
All conjunctions are mandatory when the final variant requires them; exact
`S/M/V` thresholds and disjunction alternatives need approval. P0.8
reports raw support/micro margins and one bar volume only, **no R_F verdict**.

The support, micro and volume evidence bar must close **after** the retest bar.
Micro-high anchor itself must be closed, have a unique qualified revision and
be known by the opening of its later follow-up bar. No right-bar pivot
lookahead, retroactive historical corrections or session-wall-time shortcuts.

## Separate SHORT / SWING formula slots (v0.1 candidates, all empty)

| Policy dimension | `B5/SHORT/FORMULA_DRAFT_0_1` | `B5/SWING/FORMULA_DRAFT_0_1` |
| --- | --- | --- |
| Evaluation horizon | SHORT 3–10 trading sessions (design) | SWING 10–60 trading sessions (design) |
| R_C permitted retest window | `W_SHORT = TBD` | `W_SWING = TBD` |
| R_C ATR tolerance | `T_SHORT = TBD` | `T_SWING = TBD` |
| R_E M15 reclaim buffer | `E_SHORT = TBD` | `E_SWING = TBD` |
| R_F H1/D1 support buffer | `S_SHORT = TBD` | `S_SWING = TBD` |
| R_F micro-high break buffer | `M_SHORT = TBD` | `M_SWING = TBD` |
| R_F volume threshold | `V_SHORT = TBD` | `V_SWING = TBD` |
| Risk, cost and T+2 approval | **PENDING** | **PENDING** |

One common value must **never** be silently copied between SHORT and
SWING. Distinct strategy parameters and hypotheses should be tested OOS
after approved data and backtest protocol. Even a paper-based candidate
value in Master Spec §14.3 is *not* already approved.

## Code

`src/swing_trading/b5_formula_geometry.py` contains:
`B5StrategyFormulaDraft` with intentionally empty numeric slots;
`calculate_b5_raw_geometry` first invokes P0.7 source/receipt review,
then requires closed causally known M15 micro-high anchor, with a second
independent prior closed M15 underpivot bar for FAILED_BREAK branch.
Outputs `BASE_BLOCKED`, `ANCHOR_BLOCKED` or
`RAW_GEOMETRY_UNCALIBRATED` only. `detector_approved=False` and
`actionable=False` are immutable constraints.

P0.8 also strengthens P0.7: all R_F support, micro-high and volume
market receipts must describe bars closed after M15 retest; earlier
source-qualified data are insufficient for confirmation.

`tests/test_b5_formula_geometry.py` and augmented phase-receipt tests
use synthetic fixtures to exercise both strategies/variants, arithmetic,
missing R_F inputs, time-of-first-knowledge/verification, wrong
instrument/adjustment, prior closed failed-break and no automatic thresholds.

## SSI source and backtest prerequisites

SSI MCP B06 re-check 2026-11-06: two READ-ONLY calls for SHS intraday 01/09/2026 and 13/10/2026 both returned `DOWNSTREAM_UNAVAILABLE` (no data); an unavailable downstream cannot be interpreted as empty historical coverage or a recovery. All SSI blockers B01–B08 (see P0.5) remain OPEN: daily-vs-intraday
first-open mismatch, minute-volume parity and gap classification,
native-vs-aggregated bars/auctions, response date order/clock labels,
older M1 coverage, licensed bulk/retention rights, corporate-action
price basis and sector context. **No SSI live backtest was run.**

Before any executable R_C/R_E/R_F:
1. Approve exact formula versions, required sources, categorical variants
   and STRATEGY-specific threshold candidate grids. Specify lookback,
   warm-up, tie/equality, date-order, clock and revision policy.
2. Verify source-qualified complete historical D1/M15/H1 and optional M5,
   and independently compute ATR14/RVOL-TOD; no fabricated trading
   sessions from elapsed seconds.
3. Implement and test full B5 phases, state transitions, invalidations,
   cooldown, dedup, revision handling, and the eight-step audit envelope.
4. Build fill/fees/tax/slippage/price-limit/T+2 simulator, then run the
   first real historical BT, walk-forward/OOS and A/B/C frequency comparison.

**No trade signals, realized or simulated P&L, or broker actions.**
UI v1.0 remains DESIGN_LOCKED; MOCHI deferred; CK2/FX2/Scanner unchanged.
