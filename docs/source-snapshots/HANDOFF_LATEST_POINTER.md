# Swing Trading 1.8 — Latest Master Handoff

Canonical Google Doc: https://docs.google.com/document/d/1TBGth5NXh-pPYRemsFIKeNjm1_VPhrFAWMsslALq9FI/edit

**Latest decision: §27.28 / GĐ4-P0.5 (source triage partial)**, 2026-11-06.

The [full-text GitHub snapshot](00_MASTER_HANDOFF.txt) is copied from the canonical Google Doc through §27.28 and must be checked for exact equality after merge into `main`. It is a point-in-time text export, not automatic two-way sync or native Google Docs formatting.

- P0.1–P0.4C: foundation, versioned calendar, provenance, quality axes, migration/quarantine, local SQLite evidence and independently pinnable checkpoints; previous full Handoff sections §27.22–§27.27 retain exact scope and limits.
- **P0.5:** [PR #18](https://github.com/ngluonghoa/swing-trading-1-8/pull/18), merge `700bf781afbf432bfe8c6a5b3ff56c1f4aa9de0d`. [main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42166186119) **106 tests PASS** each on Python 3.11 and 3.12.
- [SSI source audit details and B01–B08 evidence](../P0_5_SSI_SOURCE_TRIAGE.md): read-only SHS/VGI D1-vs-M1 open discrepancies; missing early-history SSI MCP intraday; connector response date-order conflict; source parity and RAW/ADJUSTED separation fail-closed. All source blockers still **OPEN**.
- **P0.5 is partial**: no verified provider-native timestamp semantics, market calendar, licensed replay-ready history, FastConnect entitlement, usable volume/CA/source policy, executable detectors, fill/cost/settlement simulation or historical backtest/OOS.
- NEXT: SSI B01–B08 entitlement/time/coverage verification with independently reviewed source evidence, source revisions and calendar; then first executable detector and simulator for first real historical backtest, without waiting for all 16 detectors.
- MOCHI deferred, UI-1.0 DESIGN_LOCKED, CK2/FX2/Scanner unchanged; no broker trading.

Google Drive remains the authoritative Handoff for subsequent decisions.
