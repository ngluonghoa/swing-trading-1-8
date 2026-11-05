# ADR-0002 — Python-first execution; Google Colab optional

**Status: APPROVED — 2026-11-06.** Supersedes plans implying Colab is needed for Swing Trading 1.8 development or backtesting.

## Decision

1. **ChatGPT Python** is preferred for interactive, on-demand algorithm tests and analysis when inputs are accessible. It is ephemeral, resource-limited and has no direct Internet access; it is not a continuous trading plugin host or persistent cache.
2. **GitHub Actions CI** runs versioned Python 3.11/3.12 tests after code changes for repeatable engineering checks. CI PASS is neither live-source correctness, OOS/profit evidence nor continuous hosting.
3. **GitHub Private** remains canonical for code; **Google Drive** remains canonical for Master Handoff/specifications and approved data/evidence.
4. **Colab** is *not connected, not run and not necessary*. Retain `notebooks/p0_foundation_smoke.ipynb` and `docs/COLAB_QUICKSTART.md` only as optional/on-hold utilities. Do not request a token, Colab sign-in or Colab session as part of the current plan. Colab-specific notebook syntax checks are outside default CI. Colab is not a milestone, dependency, release gate or requirement for the first real historical backtest.
5. **MOCHI** remains offline; clone and local backup are deferred. Runtime architecture must remain MOCHI-independent.
6. A future scheduled/always-on plugin needs an independently selected and approved reliable runtime with persistence and monitoring. ChatGPT Python, GitHub Actions, Colab and MOCHI are not substitutes for that deployment.

## Acceptance boundary

- Standard code tests must succeed without Colab, MOCHI or credentials.
- Optional notebook remains in source control with no saved outputs/secrets; optional manual validation available if requested.
- Real historical backtesting requires tested executable detector, licensed verified history, validated event/calendar clock and fill/fees/settlement simulator. The UI-1.0 design is locked; CK 2.0, FX 2.0 and Scanner remain unchanged.

Google Drive Master Handoff §27.20 governs this latest execution decision.
