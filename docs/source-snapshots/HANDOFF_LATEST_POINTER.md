# Swing Trading 1.8 — Latest Master Handoff

Canonical Google Doc: https://docs.google.com/document/d/1TBGth5NXh-pPYRemsFIKeNjm1_VPhrFAWMsslALq9FI/edit

**Latest decision: §27.27 / GĐ4-P0.4C**, 2026-11-06.

The [full-text GitHub snapshot](00_MASTER_HANDOFF.txt) has been refreshed from the canonical Google Doc through §27.27; GitHub readback must match its Drive text export before the sync is accepted. This is a point-in-time plain-text copy without native Google Docs formatting, **not automatic two-way synchronization**.

- P0.1: session/clock boundaries, merge `b88324437e54d96e346f622ff22a446da227bc7f`.
- P0.2: provenance and three-axis quality, merge `b4efcfe18209eea22839098d25e900838518e7dc`.
- P0.3: downgrade-only migration/quarantine, merge `8c2efed1fd85aabfc93df561a698c480dad7efdc`.
- P0.4: local SQLite evidence-store backup/restore, merge `22e1a40da987ed882b9a985f65de9683681a543a`.
- P0.4B: original-byte bridge, merge `2c031b4d06145c7e178ae5f2676af1a7185b73dc`.
- **P0.4C:** [PR #16](https://github.com/ngluonghoa/swing-trading-1-8/pull/16), merged main commit `ca34aca792d97a20f861096274322d7c00303856`; [main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42164546420) PASS, **88 tests each** on Python 3.11 and 3.12.
- [P0.4C implementation and limitations](../P0_4C_INDEPENDENT_CHECKPOINTS.md): externally pinnable checkpoint, whole-backup SHA-256, history prefix verification and restore controls. **Independent checkpoint custody and persistent production storage are not deployed**.
- **OPEN:** actual SSI B01–B08 rights/source/calendar/time parsing and real historical data; approved detector and fill/cost/settlement simulator; backtest/OOS; separate storage approval, encryption/ACL/offsite restore and monitoring.

MOCHI backup deferred; UI-1.0 DESIGN_LOCKED; CK2, FX2 and Scanner untouched. Google Drive remains the authoritative Handoff for future decisions.
