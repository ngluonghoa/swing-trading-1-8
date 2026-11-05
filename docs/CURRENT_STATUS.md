# CURRENT_STATUS — 2026-11-06

## Canonical source and implementation boundary

- Original Google Drive documents remain **canonical** for project design. See 00 §27.18, 01 §24/§24.14, 05 §2/§18, 06 §14–16, UI 02, and QA 09 §14.
- GitHub is authoritative for executable Python source / CI; `docs/source-snapshots` is a fixed text snapshot, **not** auto-synchronized.
- MOCHI is **OFFLINE / DEFERRED**; design requires **MOCHI-INDEPENDENT** core and future plugin operations.
- Google Colab only on-demand engineering execution; not operational cache or live trading runtime.

## What this code implements

- P0.0: typed **partial** v1.2 market bar / provider observation / revision contracts; basic quality validation.
- Revision `first_known_time_utc` checks and fail-closed, typed, deterministic replay fixture.
- Unimplemented 16 B/S zones return UNVERIFIED, never a confirmed trading decision.
- Synthetic tests in GitHub Actions on Python 3.11/3.12; a private Colab smoke notebook is present but has **NOT** been executed in Colab.
- No broker API, no real historical backtest, no detector numerical thresholds, no source feed nor trade simulator.

## NOT_IMPLEMENTED / OPEN

SSI B01–B08 source parity and entitlement, executable predicates and P01–P17 calibration, real exchange calendar, time semantics and session policy, quality gates / source corrections, full L1–L5 Smart Cache, eight-step engine + UI binding/renderer, valid cost/slippage/tax/settlement simulation, BT-01..BT-16 acceptance and OOS/walk-forward, persistent runtime, monitoring/SLO and recovery.

**CI PASS means engineering foundation tests only. Historical and release readiness are NOT_RUN / BLOCKED.** Do not use synthetic fixtures as claims of signal profitability.

## Next steps

1. Review this branch and CI result, then merge when green.
2. Reconcile full 05 §2 contracts and build versioned calendar/session fixtures; implement exact minimum eligibility gates.
3. Expand negative and deterministic replay tests including corrections/dedup and M15/M5.
4. Validate source B01–B08 / rights before any SSI-backed backtest.
5. Approve one executable detector and simulator before first historical backtest.
6. When MOCHI later comes online, clone repository and configure safe sync + Drive document backup, no impact to runtime.
