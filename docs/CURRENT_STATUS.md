# CURRENT_STATUS — 2026-11-06

## Provenance and approvals

Read `docs/source-snapshots/00_MASTER_HANDOFF.txt` §27.18 before further implementation. Source documents in Drive remain canonical. GitHub snapshots are read-only representations of the fetched text on the day of import.

## Phase status

- GĐ1: 16 B/S detector design identifiers specified, executable formulas and calibrated thresholds still pending.
- GĐ2: UI-1.0 visual approved and **design locked**; renderer and UI tests not implemented.
- GĐ3: data/calendar/cache/replay architecture specified; SSI B01–B08 and source licensing open.
- GĐ4/P0.0: repository scaffold and runnable unit fixtures introduced here; **not yet equivalent** to full specifications.
- Backtest: typed harness and synthetic tests only. BT-01..BT-16 acceptance suite NOT_RUN. No historical results, OOS or release proof.

## Next engineering work (not automatically approved by this commit)

1. Build faithful v1.2 market-bar and provider-observation identity contracts, candle quality, session calendar and correction/version policy.
2. Implement shared indicators, risk and rule registry only after explicit executable predicate formulas and evidence contracts are reviewed.
3. Expand synthetic/negative tests to all acceptance IDs and ensure CI logs are reviewed.
4. Validate SSI B01–B08, clock policy, data retention/licensing before using historical candles.
5. Run first historical backtest only with an executable tested detector, verified eligible data and realistic fill/fees/slippage/settlement.

`CI passing` is never synonymous with `HISTORICAL_VALIDATED` or `RELEASE_ELIGIBLE`.
