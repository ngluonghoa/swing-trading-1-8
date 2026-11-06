# GĐ4/P0.3 — Controlled legacy staging, quarantine and quality audit

Status: engineering implementation, synthetic fixtures only (2026-11-06).
Canonical reference: Google Drive 05 DATA CONTRACT §§2–4 and 17–18.
The legacy market-data classes are NOT yet replaced in runtime consumers.

## Implemented

- `legacy_migration.py` accepts explicit per-record `LegacyMigrationEnvelope`: project, source snapshot, stream, origin, adjustment and ingestion revision tags, and a supplied per-record normalized SHA-256 digest. It NEVER invents a normalization digest, approved source identity, provider license or adjustment revision.
- All staged legacy candles are **downgraded** to `QualityState.UNVERIFIED`, `CoverageState.UNKNOWN`, `calendar_cutoff_verified=False`, `verified_at_utc=None`, all `SourceEvidence` verification flags False and blocking `LEGACY_EVIDENCE_UNVERIFIED` flag, regardless of legacy `Quality.VERIFIED`. OPEN remains OPEN; CLOSED remains CLOSED but is not evidence of quality.
- Zero recorded volume stays zero; unknown volume stays unknown. Missing source minutes are not silently padded. Raw digest, revision identity, decimal OHLC, original source record identity and retrieval/first-known times are preserved. Unproven source-event IDs are left empty.
- Unknown lifecycle, absent mappings/digest, duplicate same-source/same-revision observations, duplicate receipt references, incorrect record types and revisions not yet available at audit `as_of_utc` are **quarantined**. Every row has exactly one outcome. Duplicate identities are quarantined as a group rather than choosing the first one.
- `QuarantinedRow.original` keeps an **in-memory reference** to the original input object, plus source digest and reason code, for inspection. This is not a durable storage/restore system; do NOT log, push or export sensitive raw payloads to GitHub.
- `quality_audit.py` adds immutable `QualityFinding`, severity INFO/WARN/BLOCK, explicit resolution states with external references, append-only `QualityFindingRegistry`, and version-shaped `DatasetManifestV12` with coverage, duplicates, out-of-order, price basis, calendar, adjustments, quality findings and provenance.
- `structural_prerequisites` for manifest are **necessary only** and do not prove data rights or authorize trading. Historical BLOCK findings (even with a waiver label) stay blocking until a separate, actually verified approval/release process exists.
- Unit/negative fixtures cover legacy downgrade, quarantine, duplicates, future corrections, source conflicts, data typing, append-only registry, manifest controls and waiver bypass prevention.

## Limitations and release blockers

- No real SSI REST/MCP/stream adapter, endpoint timestamp parsing, entitlement evidence, corporate-action mapping or authoritative calendar is implemented.
- Normalized digest, context revisions and any `verified=True` source flags must be justified by externally reviewed evidence; this migration refuses to fabricate them.
- Persistent append-only raw storage, artifact checksums/roundtrip restore, source version resolution, provider-native parity, D1/W1 weekly cutoff, dedup beyond staged batch and 5-layer cache remain NOT_IMPLEMENTED.
- No canonical dataset manifest is automatically certified from legacy fixtures. No signal detector or historical backtest is marked accepted. SSI B01–B08, P01–P17 rules, the 8-step audit pipeline and full UI renderer remain OPEN.
- The pre-existing `market_data.CanonicalCandle.eligible_for_confirmed_signals()` helper is a legacy necessary-condition fixture, NOT a live trading gate. Existing consumers do not switch to P0.3 without a reviewed migration.

## Next controlled steps

1. Design and test a durable append-only provenance/quarantine store with atomic commit, restore and source-record checksums before enabling real adapters.
2. Introduce separately reviewed, versioned endpoint parsers and calendar evidence for SSI B01–B08, preserving original data and ambiguous timestamps.
3. Develop reviewed quality-gate/waiver policy per feature and timeframe; ensure full 8-step release audit and evidence.
4. Only after validated data, an executable detector, approved thresholds and a cost/settlement simulator may real historical backtest/OOS begin.

Architecture: GitHub code + GitHub Actions repeatable CI + ChatGPT Python for on-demand work. MOCHI backup deferred. No Colab, no changes to UI v1.0 or CK/FX/Scanner.
