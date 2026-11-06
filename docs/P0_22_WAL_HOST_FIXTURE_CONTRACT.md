# GĐ4/P0.22 — WAL-mode archive rejection and fixture-only SSI/DNSE MCP conformance

Date: 2026-11-06. **Engineering-only, synthetic CI; no live data ingestion or production authorization.**

## Problem and concrete boundary

P0.21 accepts signed offline P0.18 **single-file metadata-only** SQLite backups, reading via a pinned POSIX FD and in-memory SQLite validation. It already rejects visible `-wal`, `-shm`, and `-journal` sidecars. That was not enough: a SQLite main file can retain a **WAL-mode header even when its sidecars have disappeared**. Such a file must not be silently represented as a P0.18 standalone journal snapshot.

**P0.22 now requires SQLite header bytes 18/19 to be exactly `0x01 0x01`** (rollback-journal mode) for offline metadata archive validation. The header test is made against the already pinned FD before accepting bytes. Existing P0.21 detached Ed25519, whole-file SHA256, zero quote cache, row count/chain tip, and SQLite in-memory checks remain mandatory. A file with `0x02 0x02` WAL mode is rejected even if the manifest/signature are synthetically valid and no sidecar files exist. This is **not** a validator for live WAL databases; no coherent live WAL snapshot or descriptor-secure SQLite VFS has been deployed.

## Fixture-only host bridge contract

New module: `src/swing_trading/reference_host_dryrun.py`.

- `StaticMcpFixture.from_payload(provider, endpoint, payload)`: only SSI `marketdata_list_daily_stock_infor` or DNSE `price_get_history`. Requires a static dictionary, canonical serializable JSON up to 128 KiB, no nested credential/secret/token/cookie keys. Rejects callable or ambiguous JSON fixture values. This is **not an MCP connector** and cannot see a user's credentials.
- `FixtureOnlyD1HostHarness(ssi=..., dnse=..., clock_utc=...)` runs **one** typed `D1ReferenceRequest` through the already implemented P0.16 `ReadOnlyMcpD1Bridge`, providing only static in-memory response objects to exact-argument callbacks. Enforces the SSI query `symbol/range=1d/toDate DD/MM/YYYY/pageSize=5/pageIndex=1` and DNSE fallback `symbol` only. DNSE is reached only when the source router needs it. If fallback is required but no fixture is provisioned, fail closed.
- `DryRunConformance` returns the P0.16 reference-only `BridgeRun` plus call order. `live_mcp_deployed=False`, `data_rights_verified=False`, `production_authorized=False`, and `actionable=False`. It is transient test data, not a historical market feed or persistent smart cache.

**Explicit nonclaims:** Passing this dry-run cannot authenticate an SSI/DNSE MCP account, verify native provider response identity, grant source rights, start a real host process, or prove historical first-known bars. The transport and clock callbacks for actual connectors remain separately dependent on an explicitly authorized host. No network/API calls, scheduling or broker orders are made in these synthetic tests.

## Tests

`tests/test_reference_host_dryrun.py`: SSI primary call, SSI unavailable -> DNSE fallback and exact order, missing DNSE fixture, forbidden SSI error, no intraday/current-day substitution, single-use, static payload isolation, wrong endpoint/provider, callback/credential injection, size/canonical JSON bounds, future-observed quote rejection and missing data. Added `test_signed_wal_mode_database_rejected_even_without_sidecars` to `tests/test_reference_offline_verified_archive.py`: turns a valid standalone metadata fixture into WAL mode, signs its changed SHA256, confirms sidecars absent, and expects rejection.

All tests are engineering fixtures on Python 3.11 and 3.12; CI PASS must be verified before merge.

## SSI/DNSE and future stages

SSI and DNSE remain separate logical providers in **one** SQLite `ReferenceJournal`. P0.17 opt-in diagnostic quote cache remains unlicensed by default and unsuitable for signals. P0.18 metadata-only backup excludes all OHLCV values; P0.21/22 offline verification still cannot rescue live WAL security. UI-1.0 DESIGN_LOCKED; CK2, FX2, Scanner, MOCHI untouched.

**NEXT GĐ4/P0.23:** independently review/source-qualify live read-only MCP data entitlement, endpoint coverage/first-known timestamps/adjustment, obtain host+volume+trust-root permissions and a genuinely safe SQLite runtime/WAL access architecture. Only then implement a host-bound read-only connector integration. B5 calibration (24 numeric slots), M1/M5/M15 history, SSI B01–B08 and realistic fill/fee/tax/T+2 simulation remain prerequisites for real BT/OOS. Never issue orders or trading signals from fixture/diagnostic reads.
