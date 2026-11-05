# ADR-0002 — Python-first computation and reproducible automated testing

**Status: APPROVED — 2026-11-06.** Governs the current source-code and experiment workflow.

## Decision

1. **ChatGPT Python** is the preferred environment for ad hoc calculations, algorithm development experiments, synthetic fixtures and qualified on-demand backtests when permitted data can be provided. This Python runtime is ephemeral, resource-limited and lacks direct network access. It does not host a live service or permanent market-data cache.
2. **GitHub Actions CI** automatically runs code-based tests on Python 3.11/3.12 for versioned commits. CI is a reproducible engineering gate, not proof of source parity, market signal efficacy, profitability, out-of-sample performance or production readiness.
3. **GitHub Private** is canonical for executable source. **Google Drive** is canonical for Handoff/specifications and separately authorized data/evidence storage. Store sensitive credentials in approved systems only; never in source, fixtures, or outputs.
4. Only the Python package, its real engineering test fixtures and approved runtime interfaces belong in the active build/test path. Auxiliary notebook-hosting artifacts are not necessary and have been removed from the active tree. Previous Git history is retained for audit.
5. **MOCHI** is offline and optional for later source clone/document backup. It must not be on the critical runtime path.
6. A future scheduled/always-on plugin requires a separately selected stable runtime, storage, security and monitoring; the chat's Python session and GitHub Actions jobs are not such a service.

## Acceptance boundary

- Engineering unit tests operate without external notebook services, tokens, MOCHI or external cloud runtime credentials.
- Historical simulation requires at least one executable tested detector, validated/licensed market history, causal clock/calendar and realistic fill/fees/slippage/settlement.
- UI-1.0 remains DESIGN_LOCKED; other trading projects must not be changed. All unverified B/S zones must remain fail-closed.
