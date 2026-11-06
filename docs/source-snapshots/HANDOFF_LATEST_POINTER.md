# Swing Trading 1.8 — Latest Master Handoff

Canonical Google Doc: https://docs.google.com/document/d/1TBGth5NXh-pPYRemsFIKeNjm1_VPhrFAWMsslALq9FI/edit

**Latest decision: §27.26 / GĐ4-P0.4B**, 2026-11-06.

The [full-text GitHub snapshot](00_MASTER_HANDOFF.txt) has been refreshed through §27.26 from the canonical Google Doc. It is a point-in-time text export (without native Google Docs formatting), NOT automatic bi-directional synchronization. Read the original Google Doc for subsequent decisions.

- P0.1: versioned market-session boundaries, merge `b88324437e54d96e346f622ff22a446da227bc7f`.
- P0.2: provenance and three-axis candle quality, merge `b4efcfe18209eea22839098d25e900838518e7dc`.
- P0.3: downgrade-only migration/quarantine, merge `8c2efed1fd85aabfc93df561a698c480dad7efdc`.
- P0.4: local SQLite audit store and backup/restore, merge `22e1a40da987ed882b9a985f65de9683681a543a`.
- **P0.4B**: [PR #14](https://github.com/ngluonghoa/swing-trading-1-8/pull/14), merge `2c031b4d06145c7e178ae5f2676af1a7185b73dc`; [CI on main](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42162223621) PASS, **80 tests each** on Python 3.11/3.12.
- [P0.4B design, tests and limitations](../P0_4B_RAW_SOURCE_BRIDGE.md): strict mapping from explicitly supplied raw bytes and source identity to P0.3 migration outcomes, then one atomic P0.4 SQLite batch.
- **Not verified / not deployed:** official SSI B01–B08 source rights/coverage, endpoint timestamp semantics, provider authenticity, persistent production volume, secure off-site recovery, executable trading signals or any real backtest/OOS. A matching SHA-256 is not proof of truthful upstream source data.

MOCHI backup remains deferred; UI-1.0 DESIGN_LOCKED and CK2/FX2/Scanner unchanged.
