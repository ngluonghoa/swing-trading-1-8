# Swing Trading 1.8 — Latest Handoff pointer

**Canonical Master Handoff:** https://docs.google.com/document/d/1TBGth5NXh-pPYRemsFIKeNjm1_VPhrFAWMsslALq9FI/edit

Latest decision: **§27.24 (GĐ4/P0.3)**, updated on 2026-11-06. This file is a short *status mirror*, not an export of the full Google Doc.

- P0.1 session boundaries PR #5: main commit `b88324437e54d96e346f622ff22a446da227bc7f`.
- P0.2 three-axis source quality PR #7: main commit `b4efcfe18209eea22839098d25e900838518e7dc`.
- P0.3 controlled migration and quarantine PR #9: main commit `8c2efed1fd85aabfc93df561a698c480dad7efdc`.
- Latest P0.3 main CI: https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42155168124 — PASS Python 3.11 and 3.12, 64 engineering unit/negative tests each.
- Code: `src/swing_trading/legacy_migration.py`, `src/swing_trading/quality_audit.py`, corresponding tests and [P0.3 limits](../P0_3_LEGACY_MIGRATION_QUARANTINE.md).
- Legacy data is staged as UNVERIFIED/UNKNOWN only. Duplicate rows, unknown lifecycle, missing lineage or future revisions are quarantined. Original data is retained **in memory**, not yet in durable append-only storage.
- NO real SSI source validation, confirmed license/source semantics, approved provider resolution, executable detector, historical backtest/OOS, or live trade readiness. SSI B01–B08 remain OPEN.
- NEXT: durable raw/quarantine audit store with verified recovery; independently verified endpoint timestamp/calendar/source rights; approved source-resolution policy and executable detectors.
- MOCHI backup deferred; UI v1.0 locked. No other trading project was modified.

**Full snapshot now synchronized:** [`00_MASTER_HANDOFF.txt`](00_MASTER_HANDOFF.txt) was updated directly from the canonical Google Doc through **§27.24**, and its text was read back and compared **exactly** with the Google Drive export. It is a *verified point-in-time full-text snapshot*, not a continuously synchronized mirror; for subsequent changes, check the Google Doc and repeat the sync. Google Docs native formatting is not captured by the plain-text file.
