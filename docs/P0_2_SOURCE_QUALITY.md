# GĐ4/P0.2 — Source lineage and three-axis candle-quality contract

Status: **ENGINEERING FIXTURE TESTS ONLY**, 2026-11-06. Canonical specification: original Google Drive 05 Data Contract §2–4, §17–18. Do not interpret CI PASS as real market-source validation.

## Added

- `src/swing_trading/source_quality.py`: immutable `ProviderObservationKeyV12` (project, MarketBarKey, provider, NATIVE/DERIVED/IMPORT origin, source stream); `ObservationRevisionV12` (observation identity, source revision/payload digest, adjustment revision, ingestion revision, first-known UTC, retrieved UTC).
- `CanonicalCandleV12`: separate `LifecycleState` (OPEN/CLOSED), `CoverageState` (COMPLETE/SESSION_PARTIAL/RANGE_PARTIAL/SPARSE_UNVERIFIED/UNKNOWN/INVALID), and `QualityState` (VERIFIED/WARN/UNVERIFIED/BLOCKED). It carries OHLC Decimal, volume integer or unknown, minute counts, event IDs, raw and normalized digests, source evidence, quality flags and calendar cutoff.
- Strict checks for revision/observation-to-market-key linkage, UTC timestamps, Decimal/volume integrity, digest syntax, verified source entitlements and timestamp semantics.
- Conservative `confirmation_prerequisites`: only a **necessary** check; requires independent source/coverage/basis/cutoff evidence, closed candle, verified quality, known revision by the decision time, and no unresolved quality flags. Zero volume is not the same as missing volume; unknown/sparse coverage does not count as complete.
- `resolve_as_known`: future data revisions remain invisible before first-known time; no visible revision gives NO_VISIBLE_REVISION (not NO_TRADE); more than one visible source/revision returns SOURCE_OR_REVISION_CONFLICT, never silently choosing a provider or revision. Even a single selected revision is not an actionable signal.
- Synthetic negative tests: source mismatch, conflicting revisions, lookahead, unverified permission, missing volume, OPEN/WARN/SPARSE, corrupt hashes, inconsistent resolution status.

## Migration and limits

Older `market_data.py` partial classes and their test fixtures are retained **only for backward compatibility**. They are NOT v1.2 production schema, and the legacy `eligible_for_confirmed_signals()` helper is NOT a trade/action gate. Full migration of consumers to the new contract requires a separately tested change.

`SourceEvidence` verification flags are externally supplied claims; **fixture flags are not authoritative evidence of SSI data rights, exchange schedule accuracy, corporate-action adjustments, or native source equivalence.** The code does not verify those systems on its own. There is no approved multi-provider source-resolution policy, full calendar, D1/W1 cutoff, 8-stage engine, real detector, trade simulator, historical backtest or OOS validation.

## Next

1. Build a controlled legacy-to-v1.2 normalizer/migration, quality finding registry and dataset manifest; preserve input raw records and rejected rows.
2. Verify SSI B01–B08, endpoint timestamps and source entitlements against allowed historical data before allowing VERIFIED claims from production adapters.
3. Finish actual calendar/auction policy, source reconciliation, incremental cache and replay data snapshots.
4. Only then implement the first reviewed detector and fill/cost/settlement simulator for the first real backtest.

MOCHI and external notebook services are not dependencies. UI-1.0, CK 2.0, FX 2.0 and Scanner remain untouched.
