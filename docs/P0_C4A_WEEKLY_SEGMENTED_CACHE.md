# GĐ4/C4A — Synthetic weekly immutable chunks (Cache optimisation follow-up)

User approval 07/11/2026: strengthen both independent trading projects with reusable standards, preserving each market's correct data semantics. This milestone implements **within-partition sub-chunks**, not only symbol/TF chunking, as a bounded offline fixture demonstration.

## Why this exists

C3B materializes one whole synthetic partition each time its bars change. That avoids uploads for other symbols but would still rewrite all history inside a changed symbol/TF. C4A groups **closed synthetic fixture rows into UTC-Monday seven-day storage windows**, and creates immutable content-addressed fixture chunks only for windows whose bytes changed. This is a storage bucket rule, **not a HOSE/HNX/UPCOM session, limit-up/down or authoritative calendar**. Existing full `CacheIdentity` namespace still distinguishes SSI/DNSE/VCBS, instrument/exchange, timeframe, session, RAW/adjusted, corporate-action, calendar, indicator/schema and rights-policy versions. It uses existing `encode_fixture_chunk` and `decode_fixture_chunk` for checksum and simulated indicator per-window validation.

Code: `src/swing_trading/segmented_cache.py`. Tests: `tests/test_segmented_cache.py`. No existing C1/C3A/C3B path is removed or silently migrated; C4A is a new opt-in research module. C3A whole SQLite disaster recovery remains independent, while the approved persistent design uses chunk+manifest. Local SQLite is still transient compute; Drive folder layout remains SYNTHETIC_ONLY.

## Safety and correctness

- Immutable per-week chunk names `st18-w-<Monday UTC>-<SHA256>.fixture.json`, root index per full CacheIdentity with generation/parent manifest SHA256 and sorted unique per-week references. An unchanged week references its prior chunk; an updated week creates only one new chunk; the old chunk remains for rollback evidence.
- Strict canonical checksum/identity/row count/temporal windows. Any missing/corrupt ref, stale expected head, pointer mismatch, future-known or provisional row fails closed. A completely missing historic window cannot be treated as a deletion without an independently authorized complete-scope receipt.
- **Critical:** local EMA/ATR checkpoints encoded within each independently sealed chunk begin at a *window-local* seed, and cannot be substituted for global recursive EMA/ATR. Full SQLite restore replays all bars and checks **global** EMA20/ATR14 parity. Dirty old windows require global indicator invalidation from the first changed bar onward; checkpoint carry-across and immutable L2 seeded window segments are future work.
- Window-level metadata does NOT prove source authenticity, licensing, fresh source watermark, distributed Drive atomicity, external rollback witness or real five-minute bandwidth. The in-memory head comparison and caller pin do not defeat attacker-controlled local state.
- Fixture operations only; ZERO real Drive/source calls, ZERO live price rows or releases. C2A/C2B showed no authenticated changed-since cursor across the current SSI/DNSE/VCBS MCP surfaces. A future production bounded-range adapter may still have to fetch a session/full history to discover older corrections.
- Complete workload acceptance: no-op recheck creates zero chunks; new week creates only that week; old-week revision re-creates only that old-week chunk; selected-week load reads only selected fixture refs; full local SQLite recovery recomputes globally valid checkpoints, no corruption/truncation accepted.
- GĐ4 P0.29c real rights/issuer revocation/independent off-host monotonic witness and C2C authorized live-session benchmarks remain BLOCKED. No real data entitlement, encryption KMS, cloud transport, orders, or trading claims.

## Next controlled work

Cross-project Backtest standard with separate VN settlement/price-band/matched-volume model and FX BID/ASK/spread/swap model. Build as-of replay fixtures and conservative ambiguous-fill handling; both currently lack an audited trade/P&L execution simulator. Afterwards consider C3C real harmless synthetic Google Drive smoke, then secure external-key storage; no production releases until source licensing and OOS validation.
