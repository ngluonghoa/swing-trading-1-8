# CURRENT_STATUS — 2026-11-06

## Latest decisions

- Google Drive Master Handoff §27.31 is the latest execution update (P0.7 B5 phase evidence receipts: 147 engineering tests per Python 3.11/3.12 main CI PASS). §27.30 covers P0.6 M5/M15 replay; §27.29 covers B5 feature extraction without executable detector; §27.28 SSI P0.5 and §27.27 P0.4C. The [full GitHub Master Handoff text snapshot](source-snapshots/00_MASTER_HANDOFF.txt) has now been synchronized through §27.31 and verified by exact text comparison against the Google Drive export; see [snapshot status](source-snapshots/HANDOFF_LATEST_POINTER.md). The native Drive document remains the authority for future edits and formatting.
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
2. P0.6 deterministic replay/dedup/correction and synthetic M15/M5 tests are implemented; next validate approved real calendar/source semantics for M5/M15 and independently reconcile native/derived bars.
3. Resolve SSI B01–B08 and rights to historical data.
4. P0.7 B5 phase receipts are now structurally audited (not executable); approve R_C/R_E/R_F formulas, explicit B5 variant predicates, P01–P17 parameters and no-lookahead fixtures before implementing the first executable rule, followed by a fill/cost/settlement-aware simulator and qualified real historical backtest.
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

## GĐ4/P0.6 increment — 2026-11-06

- Added [deterministic M5/M15 as-known replay and exact retransmission guards](P0_6_M5_M15_REPLAY.md), including monotone UTC checkpoints, stable market-key ordering, explicit identical-duplicate counts and collision blocking. Source corrections remain invisible before their first-known time; divergent providers/revisions remain unresolved.
- [P0.6 PR #22](https://github.com/ngluonghoa/swing-trading-1-8/pull/22) merged to main `9a1f367df67ebb1090dfb9d64ad5bdf954c8682d`; [main GitHub Actions run](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42172733020) PASS **128/128** synthetic engineering tests on each Python 3.11 and 3.12.
- Added synthetic unit/negative tests for cross-timeframe M5/M15 snapshots, late verification, future corrections, same-identity divergent payloads, missing/unverified coverage, malformed inputs and no lookahead.
- **Engineering-only:** does not aggregate M1 into M5/M15, validate SSI B01–B08 or market calendars, enable B5 executable predicates/thresholds, grant trades, execute historical backtests or certify performance. UI v1.0, MOCHI and other trading systems unchanged.

## Handoff editorial reconciliation — 2026-11-06

- Corrected the canonical Google Drive §27.30 read-first instructions, replaced the outdated PRE-CODE status with current GĐ4/P0.6 engineering scope, and removed an unintended foreign-language token from §27.29.
- Marked earlier §27.28–§27.30 source-snapshot sync instructions as historically completed by PR #19/#21/#23, rather than active pending tasks. Historical engineering and data-quality claims are unchanged.
- The full GitHub Handoff snapshot was re-exported from the native Google Doc and checked character-for-character on the editorial branch. No trading-core, SSI source, market-data, UI, runtime, MOCHI or backtest code changes.

## GĐ4/P0.7 B5 phase receipt increment — 2026-11-06

- Added [B5 R_C/R_E/R_F phase evidence contracts](P0_7_B5_PHASE_EVIDENCE_CONTRACT.md): source-event ID and exchange-qualified receipts, explicit R_E variants, immutable phase ingredient inventory, versioned policy references and causal as-of rejection. No parameter thresholds are invented or approved.
- All outcomes remain BASE_UNVERIFIED / RECEIPTS_MISSING / RECEIPTS_UNVERIFIED / PRESENT_UNCALIBRATED, with `detector_approved=False` and `actionable=False` (even for complete synthetic receipts).
- Synthetic tests cover SHORT/SWING, both E variants, missing/duplicate receipts, mixed instrument/exchange/basis/calendar, future-known evidence, conflicting revisions, timestamp order and ATR/micro-high chronology.
- **Still OPEN:** SSI B01–B08, licensed historical M15/M5 and native bars, real causal predicate formulas, P01–P17 calibration, B5 detector execution, risk/settlement simulation, historical backtest BT-01..16 and OOS. UI-1.0, MOCHI and CK2/FX2/Scanner unchanged.

## P0.7 merged engineering evidence and canonical §27.31 — 2026-11-06

- [P0.7 PR #25](https://github.com/ngluonghoa/swing-trading-1-8/pull/25) merged into main commit `e3b49a35a8ddc07f0f450a2343b32451a543a721`. [Main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42176318156) PASS **147/147** synthetic unit/negative tests on Python 3.11 and Python 3.12.
- Native Google Drive Master Handoff advanced to §27.31; the complete GitHub text export is a point-in-time exact-match snapshot, not continuous two-way syncing.
- All SSI source rights/coverage B01–B08 remain OPEN; B5 has no calibrated R_C/R_E/R_F detector or actionable signal, and historical backtest/OOS remain NOT_RUN.
