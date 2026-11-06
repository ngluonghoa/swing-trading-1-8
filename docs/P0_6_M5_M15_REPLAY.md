# GĐ4/P0.6 — deterministic M5/M15 as-known replay and retransmission guards

Date: 2026-11-06. Status: ENGINEERING_ONLY; NOT SSI-certified, NOT an executable detector, NOT a historical backtest.

## Scope

- The existing P0.2 v1.2 source identity/quality contract remains the only input shape.
- New replay_batch module resolves an explicit, immutable tuple of requested bar keys at each historical as-of time. It uses the existing fail-closed resolve_as_known rule, which never implicitly selects a latest revision or preferred provider.
- Equal retransmissions (all fields, raw/normalized digests, evidence, and timestamps identical) collapse to one candidate, with the duplicate count retained per bar. A source-qualified observation/revision identity repeated with different content is explicitly flagged as a collision and must not produce a selected bar.
- More than one distinct visible provider/revision remains SOURCE_OR_REVISION_CONFLICT, including a correction that becomes visible after first-known time. Prior as-of frames cannot read that future correction.
- Missing bars are NO_VISIBLE_REVISION, not a no-trade conclusion. Source prerequisites still require complete/approved coverage, verified quality, correct lifecycle, known timestamps, rights flags and approval claims. The code NEVER asserts that fixture flags prove provider rights.
- Replay checkpoints cannot go backward, times must be aware UTC, output sorting is deterministic across source and key input order, and unrequested rows/duplicate requested keys are errors.

## Tests

Synthetic engineering tests in tests/test_replay_batch.py exercise M5/M15 time sequence, first-known and verification boundaries, exact retransmission counts, same-identity content collisions, later corrections, divergent providers, deterministic order, incomplete/unknown coverage, absent rows, invalid input and clock behavior.

These tests use explicitly synthetic approved-flag fixtures and are not proof of a real source, exchange calendar, historical B5 strategy efficacy, or ability to place an order.

## Deferred and excluded

No M1-to-M5/M15 aggregation, no native versus derived candle reconciliation, no OHLCV volume/value parity, no session auction/lunch/PLO classification and no source entitlement or provider timestamp resolution. SSI B01–B08 are still OPEN. No source credentials or licensed price history were copied.

No B5 R_C/R_E/R_F predicate, P01–P17 threshold, actionable signal, entry/SL/TP, transaction simulation, historical BT-01..16, OOS, production storage, MOCHI dependency, UI change, or CK2/FX2/Scanner integration.

## Next

1. Continue SSI B01–B08 with independently qualified source timestamp/rights/history and official session semantics.
2. Review B5 variant-specific executable predicates and P01–P17 calibration before allowing any detector output; use the shared replay domain for both future Signal and Backtest engines.
3. Once one detector and replay history are accepted, build fill/fees/taxes/settlement simulator and start the first qualified historical backtest. Do not relabel any synthetic engineering test as a real backtest.
