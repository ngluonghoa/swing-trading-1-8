# CURRENT_STATUS — 2026-11-06

## Canonical decisions and boundaries

- Google Drive's original Master Handoff §27.20 is the **latest decision**; §27.19 is implementation history. Original Drive specs remain canonical for design; `docs/source-snapshots` is a point-in-time text export, not automatic synchronization.
- GitHub `ngluonghoa/swing-trading-1-8` is authoritative for executable Python source and GitHub Actions CI.
- **Python-first:** Use ChatGPT's Python environment for on-demand computation, exploratory backtest/test fixtures when input data is accessible, and GitHub Actions for reproducible automated code testing. ChatGPT Python has no direct network access and is ephemeral, so neither Python sessions nor CI constitute continuous plugin hosting.
- **Colab is OPTIONAL / ON HOLD:** A notebook and guide are kept as spare utilities only. No Colab plugin connection, runtime, account authorization, token, step in mandatory workflow, CI gate or actual Colab test has been completed or is required.
- **MOCHI OFFLINE / DEFERRED:** optional local clone and backup later. Core/plugin architecture must be MOCHI-independent.
- Future always-on or scheduled plugin runtime with persistent storage is not yet selected/deployed; it must be approved independently.

## Implemented in code (not trading validated)

- GĐ4/P0.0 partial v1.2 typed market-bar/provider-observation/revision contracts with basic input validation and quality guards.
- First-known-time deterministic synthetic replay; fail-closed handling for not-yet-implemented 16 B/S zones.
- Python 3.11/3.12 GitHub Actions engineering unit tests. Optional Colab notebook syntax checking is **outside** the default CI test discovery.
- No executable detector, no SSI integration, no licensed historical backtest, no broker order interface or fill simulator.

## Still OPEN / BLOCKED

SSI B01–B08 source parity and entitlement, P01–P17 calibration and executable rule predicates, exchange calendar/session and time semantics, full source correction/quality gates, L1–L5 Smart Cache, eight-step engine and locked UI renderer/golden tests, fill/fees/slippage/settlement model, BT-01..BT-16 acceptance, OOS/walk-forward, persistent cloud runtime, monitoring and release/rollback.

**CI PASS = engineering fixture tests only, NOT historical validation or production readiness.**

## Required next engineering actions

1. Reconcile full 05 §2 source contracts and versioned calendar/session/quality gates.
2. Expand deterministic correction/dedup/M15/M5 negative tests, ensure replay has no lookahead.
3. Verify SSI B01–B08, history rights/coverage and correct timestamps.
4. Implement first approved executable detector with unit evidence and simulation including costs/fills/settlement before real backtest.
5. When the user later turns MOCHI on, clone and set up controlled Git sync and versioned Drive backup. This is deferred, not a requirement for items 1–4.

Colab has **no required next action**. Existing optional guide: [COLAB_QUICKSTART](COLAB_QUICKSTART.md).
