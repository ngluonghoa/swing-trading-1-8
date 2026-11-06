# GĐ4/P0.10 — D1 expected-session inventory and ATR14 correction replay parity

Date: 2026-11-06. Status: **ENGINEERING-ONLY / SYNTHETIC / UNVERIFIED MARKET CALENDAR / NONACTIONABLE**.

Canonical references: Master Spec §§14.2–14.3 / §24, Data Contract §2 and §§17–18, native Master Handoff §27.33. Builds on P0.9 `causal_indicators.py`; does **not** modify the approved UI-1.0.

## Delivered

- `src/swing_trading/d1_atr_reconciliation.py`: typed immutable `D1ExpectedSession`, `D1SessionInventory`, `audit_d1_session_inventory` and `reconcile_atr14_d1`.
- `tests/test_d1_atr_reconciliation.py`: synthetic tests for gap/extra/overlap/session/timeframe/calendar/basis conflicts, first-known clock and source quality, ATR append parity, early-seed correction, post-seed correction, idempotency and revision conflict.

## Exact expected-session comparison

`D1SessionInventory` accepts an **externally provided** ordered sequence of `(session_period_id, start_utc, end_utc)` for a particular `calendar_version`, `manifest_revision` and first-known UTC. D1 history is compared against these slots **exactly**. The audit fails closed for:

- An expected session missing from data, an unexpected session, duplicated or unsorted session keys.
- A mismatch in bar start/end UTC, calendar-version, source quality, provider/basis/revision, or a slot manifest only known in the future.
- Overlaps, malformed or internally duplicated expected slots, non-D1 source bars, source conflicts and revisions not yet known.

A matching set reports `MATCH_UNCERTIFIED`, **never `calendar_certified=True`**. This is a comparison against a *supplied* list only; it cannot establish that the list contains all official HOSE/HNX/UPCoM sessions, unscheduled closures, special/half trading days or auction boundaries. Inventing weekdays as an official market calendar is not permitted. Data rights, external calendar source, source timing and completeness remain unverified.

## ATR14 replay/incremental reconciliation

`reconcile_atr14_d1(old_history, current_history, inventory, old_as_of_utc, as_of_utc)` requires **two separately causal** v1.2 snapshots of the historical D1 series. The old checkpoint must have been qualified at `old_as_of`, the current series at the later `as_of`, and the unverified slot manifest must have been known at the old checkpoint.

It rejects source/provider/basis/adjustment changes across the checkpoint, removed history, non-prefix historical session insertion, mismatched expected slots, unresolved source revisions, future-known corrected data or a revision whose new first-known timestamp is not later than the old checkpoint (such a correction was already visible then).

The algorithm finds the **first changed bar** by comparing complete immutable selected candle payloads, including source revision metadata. It then:

1. If no bar changed, returns `PARITY_UNCERTIFIED` with zero work (idempotent case).
2. If the change is within the first 15 D1 bars, **throws away the old checkpoint** and re-seeds from 14 True Ranges using 15 current bars. It does not reuse an invalid early ATR seed.
3. If the first change is after the seed, **recomputes the ATR of the unchanged old prefix at the old clock**, then replays exactly from the dirty index using the current bar and the immediately preceding close. This captures next-bar TR effects when an earlier `close` was corrected.
4. If only new bars were appended, reuses the old checkpoint and replays the new suffix without downloading/recomputing previous TRs (the test ensures arithmetic equality).
5. Independently computes the full ATR14 using P0.9 from the same new snapshot and requires **exact Decimal equality**. Any divergence is `DIVERGED`, not a silently tolerated difference.

Output states are `BLOCKED`, `PARITY_UNCERTIFIED`, or `DIVERGED`, with first dirty/replay indices and number of replayed true ranges for auditing. All outputs have `calendar_certified=False`, `source_certified=False`, and `actionable=False`. Parity proves *only* two implementations agree on the same provided input under synthetic test conditions; it does not validate actual Wilder ATR14 against an independent external implementation/market source.

## Negative-path / acceptance boundary

Synthetic tests cover gap/extra/duplicate/overlap expected sessions, invalid manifest timing and calendar revision, selected source unverified, missing/partial history, change to early-seed bar, edit after seed, same-payload repeat, late corrected source revision, revision conflict, future information, old checkpoint known too late, truncated history and adjustment rebase.

Market-data blockers **B01–B08 SSI remain OPEN**; rights/retention, native/derived D1/M15 parity, actual official day/session completeness and source adjustment provenance still require independent evidence. The previous intraday SSI endpoint outage cannot be interpreted as loss of all historical data. No real source parity test, B5 executable R_C/R_E/R_F predicates, P01–P17 approval, live signals, real historical BT-01..16, walk-forward/OOS or realistic trade simulator was run.

## Next

- Establish an independently verified and versioned official market-session manifest and licensed/qualified D1 historical corpus, then reconcile native/adjusted series against the exact expected slots and an external reference implementation of Wilder ATR14.
- Specify the separate **RVOL_TOD** same-exchange-local-slot cumulative-volume contract only after qualified intraday history and auction/lunch/session semantics are independently verified. Do not substitute RVOL_TF20 for it.
- Approve B5 SHORT/SWING rules and calibration grids; only then develop executable phase predicates, realistic fill/fees/slippage/tax/T+2 simulator and genuine historical BT/OOS.
- Do not touch locked UI-1.0, MOCHI, CK 2.0, FX 2.0, Scanner or broker order actions.
