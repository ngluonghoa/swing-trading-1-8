# GĐ4/C3A — Offline synthetic SQLite cache snapshot and Google Drive staging boundary

**Date:** 2026-11-07, Asia/Ho_Chi_Minh. **Status: OFFLINE / FIXTURE-ONLY.** Baseline canonical Master Handoff §27.61 and `main` commit `9f9d54da8785c31cc5f7131c9a36215a42302bc4`. Independently implemented; none of the discarded ChatGPT Work code reused.

## Storage decision and actual preparation

The user chose **Google Drive as the persistent backup location**, **SQLite/RAM as the local working cache** (RAM is ephemeral in ChatGPT Python). A private Drive folder was created beneath the existing Swing Trading project folder:
[**CACHE_SWING_TRADING_1_8__STAGING_SYNTHETIC_ONLY**](https://drive.google.com/drive/folders/1Wuaale6klzOH19204vCdjlNPfl-wubhp). This folder is a **staging namespace only**; it is not licensed/approved for real vendor quotations, cannot serve low-latency SQLite queries and does not automatically receive backups. GitHub remains authoritative for source, tests and version control, **never for raw cache databases**. MOCHI remains optional backup, not a dependency.

## What C3A builds now

- `src/swing_trading/cache_snapshot_bundle.py`: explicit snapshot creation, verification, restore of an existing `SyntheticIncrementalStore` only. Uses SQLite's online backup API instead of copying a WAL-backed live SQLite file or its incomplete journal. New **no-overwrite** snapshot and manifest files, bounded size and row-count quotas, exact known table/schema checks, SQLite integrity check, fixture normalized bar digests and **cold-versus-stored EMA20/ATR14 checkpoint parity** for each isolated synthetic provider key. No auto-connect, scheduling, trades, API or Cloud upload.
- Portable, canonical, metadata-only `FixtureSnapshotManifest`: generation, link to preceding manifest digest when generation >1, UTC creation, fixture SQLite SHA256/byte count, row counts by table and explicit hard FALSE for market-data permission and Drive-upload assertion. Does not contain price, volume, candle, symbol or account.
- `verify_fixture_snapshot` requires a separately supplied pinned manifest SHA256 and optionally a monotonic generation floor plus expected parent digest, checks byte integrity/schema/causal checkpoint parity **before restore**. `restore_fixture_snapshot` is no-overwrite and checks again after copying. An attacker controlling both manifest and pin can rewrite history; C3A has NO independently trusted custodian, key signature or durable monotonic floor and makes no such claim.
- Existing `SyntheticIncrementalStore` already supports source-specific cache identity, complete-window vs partial-page deletion, revision/correction detection, and tail-only replay. C3A regression tests cover three-provider round-trip, warm read without recompute, next bar append, historical source correction isolation, WAL backup, tampering, missing schema, forged production rights, rollback floor, no-overwrite and wrong JSON format.

## Intended *future* Drive transport workflow, not implemented here

1. Run synthetic SQLite locally in a separately approved **non-Git** working directory. Generate **new immutable** `*.sqlite` + `*.manifest.json` files by calling the explicit C3A API after an operator-driven snapshot trigger (not every five-minute market check).
2. When an authorized Drive upload adapter is separately implemented, upload content-addressed files to the staging folder. Verify new Drive file IDs, content hash on redownload and a separate protected pin/monotonic generation record; never assume a Google Drive file revision is a secure anti-rollback clock or that a manifest SHA by itself authenticates issuer rights.
3. Reopen later by downloading a snapshot and manifest into an approved temporary local directory, supply an *independently obtained* pinned digest/floor, verify bytes, schema and indicator parity, and restore into a NEW file. Do not restore over a live SQLite DB or source-controlled tree.
4. **Only after** vendor/account/product entitlement, licence retention, secure Drive sharing/quotas, correction/expiry/erasure controls, protected signing and head custody (P0.29c) plus production host review may a different **explicitly approved** real-data implementation be developed. No ad hoc real quote upload or auto 5-minute MCP polling.

### Cache refresh economics

Every user-driven scan can reuse valid closed bars and indicator checkpoints locally and compute only affected suffixes; this avoids replaying unchanged history. It **does not guarantee** reduced network transfer if MCP only returns a whole session/full history (SSI M1, DNSE D1), or if the source is not licensed for persistent caching. Keep provider-specific identity and normalized price/volume basis; never conflate VCBS minute price points with M1 OHLCV. A future batch upload policy should be tied to changed-byte threshold, version/correction events, explicit owner retention and recovery goals—not a blind five-minute timer.

## Verification / open gates

Check the new unit tests and complete GitHub CI both Python 3.11/3.12, including postmerge main run. This is synthetic engineering only; **no actual Drive snapshot bytes** have been uploaded, no Google Drive Python API adapter exists and no operational crash/RTO/RPO benchmark has been executed. Next: C3B read-only Drive object inventory/verification and independently authorized content-addressed transport for synthetic-only fixtures; C2C real live-session measurement on approved weekdays and P0.29c external trust/rights remain blocked. User locked UI v1.0, SHORT/SWING, 16 zones and eight-step audit preserved. CK2/Forex/Scanner/MOCHI unchanged.
