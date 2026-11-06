# Swing Trading 1.8 — Latest Handoff pointer

**Canonical Master Handoff:** https://docs.google.com/document/d/1TBGth5NXh-pPYRemsFIKeNjm1_VPhrFAWMsslALq9FI/edit

Latest decision: **§27.23 (GĐ4/P0.2)**, updated on 2026-11-06. This GitHub file is a short *status mirror*, NOT an export of the complete native Google Doc.

- P0.1 session-boundary PR #5: merged at `b88324437e54d96e346f622ff22a446da227bc7f`.
- P0.2 source quality PR #7: merged at `b4efcfe18209eea22839098d25e900838518e7dc`.
- P0.2 CI: https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42153091655 — PASS, Python 3.11 and 3.12, 42 unit/negative tests each.
- Code: `src/swing_trading/source_quality.py`, `tests/test_source_quality.py`, `tests/test_resolution_guard.py`; [scope and blockers](../P0_2_SOURCE_QUALITY.md).
- New source-lineage and independent lifecycle/coverage/quality models are **engineering-only**; legacy consumers not yet migrated. Source entitlement, SSI B01–B08, verified calendar, 16 real executable rules, historical backtest/OOS, live trading are NOT_VERIFIED / NOT_RUN.
- Continue with controlled P0.3 migration and evidence-backed source quality. MOCHI backup is deferred and UI v1.0 remains locked.

**Known synchronization limitation:** `00_MASTER_HANDOFF.txt` is a historical text snapshot through **§27.21 only**. Read the original Google Doc for §27.22, §27.23 and any later decisions. Do not claim a full mirror or modify the original snapshot as if automatically synchronized.
