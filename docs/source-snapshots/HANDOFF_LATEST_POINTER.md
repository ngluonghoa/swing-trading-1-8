# Swing Trading 1.8 — Current Handoff status

Canonical native Google Doc: https://docs.google.com/document/d/1TBGth5NXh-pPYRemsFIKeNjm1_VPhrFAWMsslALq9FI/edit

**Latest decision: §27.25 / GĐ4-P0.4**, as of 2026-11-06.
The [entire text snapshot](00_MASTER_HANDOFF.txt) has been refreshed from the canonical document through §27.25 and verified by exact text readback on the sync branch. This is a point-in-time text copy, NOT automatic synchronization or Google Docs formatting.

- P0.1 source/session boundaries: merge `b88324437e54d96e346f622ff22a446da227bc7f`.
- P0.2 provenance and quality axes: merge `b4efcfe18209eea22839098d25e900838518e7dc`.
- P0.3 migration/quarantine: merge `8c2efed1fd85aabfc93df561a698c480dad7efdc`.
- P0.4 local evidence-store prototype: [PR #12](https://github.com/ngluonghoa/swing-trading-1-8/pull/12), merge `22e1a40da987ed882b9a985f65de9683681a543a`, [main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42160716529): Python 3.11/3.12 PASS, 70 tests each.
- [P0.4 implementation and limits](../P0_4_LOCAL_EVIDENCE_STORE.md): local SQLite bytes/receipts, checksums, transaction rollback, backup/restore code only; no persistent production destination, no SSI ingestion or provider-entitlement verification.
- OPEN: raw-byte bridge for legacy quarantine, secure production storage and offsite recovery, SSI B01–B08, source time semantics/calendars, approved rules and historical backtest/OOS.
- MOCHI backup deferred; UI-1.0 locked; CK2/FX2/Scanner not modified.

The Google Doc remains authoritative. For later edits, repeat the full export-to-GitHub equality verification rather than assuming live synchronization.
