# CURRENT_STATUS — 2026-11-06

## Latest decisions

- Google Drive Master Handoff §27.29 is the latest execution update (B5 causal feature pack with no approved detector, 117 engineering tests per Python 3.11/3.12 main CI PASS). §27.28 covers SSI P0.5, §27.27 covers P0.4C. The [full GitHub Master Handoff text snapshot](source-snapshots/00_MASTER_HANDOFF.txt) has now been synchronized through §27.29 and verified by exact text comparison against the Google Drive export; see [snapshot status](source-snapshots/HANDOFF_LATEST_POINTER.md). The native Drive document remains the authority for future edits and formatting.
- GitHub is the only authoritative **code** repository. GitHub Actions CI is the repeatable test environment; ChatGPT Python handles on-demand local calculations when inputs can be provided.
- The ChatGPT Python environment is ephemeral and has no direct network access. GitHub Actions is not a 24/7 server. A persistent production/plugin runtime and cache must be independently approved and verified.
- Unused auxiliary execution utilities and their token instructions have been removed from the current repository tree; they are not required, connected or part of the test/release workflow. Historical Git commits are not rewritten.
- Google Drive original documents remain the authoritative **specs/Handoff**. GitHub `docs/source-snapshots/` is an explicit, non-automatic text snapshot.
- MOCHI remains offline and its clone/document-backup work is deferred; the engineering core must not depend on it.

## Implemented

- P0.0 partial market-bar/legacy candle fixtures; P0.2 [versioned observation/revision identity and three-axis lifecycle/coverage/quality contracts](P0_2_SOURCE_QUALITY.md), including conservative source-conflict resolution. Legacy consumers are not yet migrated.
- Synthetic deterministic replay and first-known-time guard; not-yet-implemented 16 B/S detector slots fail closed as UNVERIFIED.
- Python 3.11/3.12 GitHub Actions unit/negative tests with no external credentials.

## OPEN / NOT_RUN

SSI B01–B08 source parity/entitlement, approved P01–P17 thresholds and executable rules, verified market sessions and clock, source corrections, full L1–L5 Smart Cache, eight-step decision/risk gates and locked UI renderer, proper fill/fees/slippage/tax/settlement simulator, real historical BT-01..BT-16, OOS/walk-forward, durable runtime/storage, release monitoring/rollback.

**Engineering CI PASS is not market-data validation, live readiness, historical backtest or trading performance.**

## Next actions

1. Continue SSI B01–B08 source triage: independently verify endpoint date/clock semantics, provider data rights, source parity, historical coverage and official market schedules. See [P0.5 evidence](P0_5_SSI_SOURCE_TRIAGE.md).
2. Add deterministic replay/dedup/correction and M15/M5 tests to verified fixtures.
3. Resolve SSI B01–B08 and rights to historical data.
4. Review and implement the first executable rule, then a cost/fill/settlement-aware simulator and qualified real historical backtest.
5. Backup code and versioned documents to MOCHI only when online; do not treat this as prerequisite for tasks 1–4.

## GĐ4/P0.1 increment — 2026-11-06

- [Versioned session-boundary contracts](P0_1_SESSION_BOUNDARIES.md) implemented with synthetic negative tests for lunch-gap isolation, auctions, version mismatches and explicit timestamp semantics.
- Official market calendars, SSI source timestamp semantics, B01–B08 and three-axis quality remain UNVERIFIED. This is **structural validation only**, not an actionable trading gate or a real historical backtest.

## GĐ4/P0.2 increment — 2026-11-06

- New immutable provider observation/revision lineage, separate quality axes, and strict as-of resolution without silently choosing a provider or correction.
- Synthetic negative tests: unresolved conflicts, future-known revisions, unknown/sparse coverage, missing volumes, quality and provenance guards.
- Source flags in fixture code are not SSI entitlement verification. Migration of the legacy market-data classes and independent source-resolution policy remain OPEN; no real historical backtest or detector execution.

## GĐ4/P0.3 increment — 2026-11-06

- [Controlled legacy-to-v1.2 staging and quality audit](P0_3_LEGACY_MIGRATION_QUARANTINE.md): source identity, normalization digest, adjustment and ingestion revisions must be explicitly supplied per row; they are never invented. Every staged row remains UNVERIFIED/UNKNOWN regardless of legacy quality.
- Unsafe inputs are quarantined (unknown lifecycle, incomplete provenance, duplicate observation/revision or row-reference, unavailable revision, missing normalization digest) with immutable findings and in-memory original object references. No storage service or live SSI feed was connected.
- Added typed DatasetManifestV12 and an immutable QualityFindingRegistry with blocking checks; no automatic findings cleanup, no waiver-based release without verified approval.
- **OPEN**: real adapter proof, endpoint timestamps, permanent quarantine/raw ledger, dataset source entitlements and B01–B08, migration of existing runtime consumers, official calendar/corporate actions, executable detectors, historical backtest and OOS.

## GĐ4/P0.4 increment — 2026-11-06

- [Local SQLite evidence store and checked restore](P0_4_LOCAL_EVIDENCE_STORE.md) added with SHA-256-linked receipts, atomic batch rollback and synthetic backup/restore tests. 70 engineering tests PASS per Python version.
- NOT_DEPLOYED: no persistent production volume, encryption/ACL/offsite backup, SSI source ingestion, P0.3 raw byte bridge or provider validation. Historical backtest remains NOT_RUN.

## GĐ4/P0.4B increment — 2026-11-06

- Added [explicit legacy-row ↔ original raw bytes bridge](P0_4B_RAW_SOURCE_BRIDGE.md): caller supplies row/source/snapshot identity and raw SHA-256; never serializes Python objects or fabricates raw bytes.
- Preflight rejects missing, duplicate, reordered or mismatched source evidence. Preserves P0.3 `STAGED_UNVERIFIED` / `QUARANTINED` decisions, then atomically archives each batch to P0.4 SQLite with checksum and chain auditing. Synthetic backup/restore and as-of/lookahead tests added.
- **NOT_VERIFIED:** association between upstream bytes and source business content, actual SSI provider provenance, real persistent deployment, storage security/offsite recovery, data licenses and source timestamp parity. No historical backtest/OOS or live signals.

## GĐ4/P0.4C increment — 2026-11-06

- Added [independently pinned SQLite evidence checkpoints and restore/prefix verification](P0_4C_INDEPENDENT_CHECKPOINTS.md), with whole-backup SHA-256, count/tip cross-checks, single-snapshot history prefix inspection, strict metadata schema and synthetic negative tests.
- **Checkpoint generation is NOT an approval**. A separately authorized custodian and safe storage for the pinned checksum/chain tip are still required; no signing service, production host, real persistent volume, encryption, off-site backup or restoration drill was deployed.
- Future Backtest/Signal Engine still depends on a verified SSI source, calendar/timestamp semantics, one real executable detector and a cost/settlement/fill simulator. SSI B01–B08 remain OPEN; actual backtest/OOS remain NOT_RUN.

## GĐ4/P0.5 increment — 2026-11-06

- [SSI MCP B01–B08 source triage](P0_5_SSI_SOURCE_TRIAGE.md) performed with narrowly scoped read-only samples. SHS/VGI 04/11 D1 opens disagree with first 09:00 intraday observation; old SHS intraday windows returned empty while mid-Oct/early-Nov queries returned records. Historic M5/M15 availability remains NOT_VERIFIED.
- Unambiguous intraday `13/10/2026` output conflicts with current MCP tool description `MM/dd/yyyy`; connector presentation semantics vs direct provider native fields still requires independent reconciliation.
- Added strict versioned timestamp date-order and clock-label contracts, unknown-coverage classification, D1/M1 open and volume parity, missing-minute classification and RAW/ADJUSTED separation with offline negative tests.
- **All B01–B08 remain OPEN.** No raw SSI tick archives, credentials, persistent production volume, executable trading signals or actual historical backtests were created.

## GĐ4 / first detector preparation — B5 causal features — 2026-11-06

- Added [B5 retest-after-breakout causal feature extraction](B5_CAUSAL_FEATURE_PACK.md) using source-qualified v1.2 bar snapshots and replay as-of, with SHORT/SWING isolation, pivot event and source revision references, no-lookahead, price-basis and calendar guards.
- Tested synthetic positive/negative/missing/conflict paths. Output is **EXTRACTED_UNCALIBRATED / UNVERIFIED**, with no executable R_C/R_E/R_F, no detector decision, trading action or actual backtest.
- P01–P17 calibration, SSI B01–B08, approved source timestamps, native data lineage, first realistic fill/fees/settlement simulator and licensed multi-period history remain OPEN. UI v1.0, MOCHI, CK2/FX2/Scanner unchanged.
