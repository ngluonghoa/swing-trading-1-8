# H2-B — Retroactively standardize existing transport, replay and cache read ports

Status: ENGINEERING OFFLINE ONLY. Scope: existing source modules, not a new live adapter or an operational migration. Baseline H2-A PR #105 (whole-repo AST audit).

## Changes in existing code (not just new wrappers)

1. d1_mcp_transport_bridge.py: introduces D1ReferenceTransport. The SSI callback must be labelled SSI/marketdata_list_daily_stock_infor; DNSE must be labelled DNSE/price_get_history. Both carry a semantic version and hard-false source authority flags. ReadOnlyMcpD1Bridge.from_transports validates contract ID, provider scope, method and version BEFORE any callback executes. The historical constructor remains for backwards compatibility with existing qualified reference tests, but new wiring should use from_transports. No connector is contacted by class creation; source entitlement, real price quality and live retention are NOT established.

2. backtest.py: adds BacktestHarness.from_contracts for explicit replay event source and rule-registry ports. Both must be SYNTHETIC_TEST_ONLY with compatible contract IDs/versions. No simulation/ROI/order authority is added. Existing constructor and causal behavior remain unchanged.

3. partition_chunk_cache.py (C3B) and segmented_cache.py (C4A): both now implement the SAME read-only fixture interface get_head(identity) and read_partition(identity, pinned_digest=...) and expose PortDescriptor cache.readonly_fixture v1.0.0, SYNTHETIC_TEST_ONLY. C3B content-addressed bytes, SHA/manifest-chain, C4A weekly chunks, SQLite schema and existing write methods remain byte-for-byte unmodified; head values are only candidates until pinned read validates the chain.

## Actual old-module behavioral acceptance

tests/test_h2_legacy_ports.py uses REAL existing D1 bridge, old BacktestHarness and existing C3B/C4A classes (not H1 dummy-only registry exercises):

- Typed D1 source constructors give identical audit/receipt outputs as legacy constructors for SSI primary and DNSE fallback; source reversal, endpoint mismatch, version downgrade and privilege claims rejected pre-I/O. Malformed SSI response keeps its historical explicit ValueError.
- Retrofitted replay constructor preserves first-known event exclusion and rejects wrong source scope, rule version, absent method and invalid clock without evaluating injected callbacks.
- C3B and C4A read the same fabricated 15 daily bars across three UTC weeks with identical consumer-visible rows; H1 consumer pin allows swapping ONLY when contracts agree. Cross-provider and changed indicator identity are blocked; corrupted/missing head is rejected.
- Crash after chunk staging does NOT publish active pointer; one revised fake bar creates one dirty C4A weekly chunk; rehydrate in fresh independent SQLite stores and assert exact GLOBAL EMA20/ATR14 full_recompute parity. No real Drive source IO and no production release.

## Remaining and non-goals

- These are optional preferred typed construction paths; historical direct callback construction stays for compatibility and must be deprecated through a separate reviewed migration if/when all consumers use the typed facade.
- C4A selected-week read may legitimately return a subset; the uniform read_partition method intentionally returns FULL partition only. Write/update/migration methods remain separately versioned interfaces with different semantics.
- H2 does not certify VCBS production source, currently unverified native M5/H1, entitlement signatures, provider rights, external revocation freshness, live source delta, real stable host, vendor retention or actual trading.
- Full semantic contracts for detector/calibration, rights custody and official VN settlement are separate existing gate work; do NOT rewrite them merely for formatting.

Rollback: revert this PR through a scoped GitHub PR; no DB migration or persisted cache byte schema changes occur, so all old fixture snapshots stay readable under old code. Preserve H1/H2-A and the original C3C rollback.
