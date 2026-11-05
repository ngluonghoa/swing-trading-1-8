# CURRENT_STATUS — 2026-11-06

## Latest decisions

- Google Drive Master Handoff §27.22 is the latest execution update (P0.1 session-boundary contracts and passing main CI). Earlier decisions remain subject to latest-decision precedence. The full GitHub 00 snapshot is only current through §27.21; see [Handoff latest pointer](source-snapshots/HANDOFF_LATEST_POINTER.md) and read the original Drive document.
- GitHub is the only authoritative **code** repository. GitHub Actions CI is the repeatable test environment; ChatGPT Python handles on-demand local calculations when inputs can be provided.
- The ChatGPT Python environment is ephemeral and has no direct network access. GitHub Actions is not a 24/7 server. A persistent production/plugin runtime and cache must be independently approved and verified.
- Unused auxiliary execution utilities and their token instructions have been removed from the current repository tree; they are not required, connected or part of the test/release workflow. Historical Git commits are not rewritten.
- Google Drive original documents remain the authoritative **specs/Handoff**. GitHub `docs/source-snapshots/` is an explicit, non-automatic text snapshot.
- MOCHI remains offline and its clone/document-backup work is deferred; the engineering core must not depend on it.

## Implemented

- Partial typed market-bar identity, provider-observation/revision, candle quality and data-eligibility contracts (foundation only).
- Synthetic deterministic replay and first-known-time guard; not-yet-implemented 16 B/S detector slots fail closed as UNVERIFIED.
- Python 3.11/3.12 GitHub Actions unit/negative tests with no external credentials.

## OPEN / NOT_RUN

SSI B01–B08 source parity/entitlement, approved P01–P17 thresholds and executable rules, verified market sessions and clock, source corrections, full L1–L5 Smart Cache, eight-step decision/risk gates and locked UI renderer, proper fill/fees/slippage/tax/settlement simulator, real historical BT-01..BT-16, OOS/walk-forward, durable runtime/storage, release monitoring/rollback.

**Engineering CI PASS is not market-data validation, live readiness, historical backtest or trading performance.**

## Next actions

1. Implement the remaining canonical source-quality/calendar/clock contracts against 05 §2/§18.
2. Add deterministic replay/dedup/correction and M15/M5 tests to verified fixtures.
3. Resolve SSI B01–B08 and rights to historical data.
4. Review and implement the first executable rule, then a cost/fill/settlement-aware simulator and qualified real historical backtest.
5. Backup code and versioned documents to MOCHI only when online; do not treat this as prerequisite for tasks 1–4.

## GĐ4/P0.1 increment — 2026-11-06

- [Versioned session-boundary contracts](P0_1_SESSION_BOUNDARIES.md) implemented with synthetic negative tests for lunch-gap isolation, auctions, version mismatches and explicit timestamp semantics.
- Official market calendars, SSI source timestamp semantics, B01–B08 and three-axis quality remain UNVERIFIED. This is **structural validation only**, not an actionable trading gate or a real historical backtest.
