# CURRENT_STATUS — 2026-11-06

## Latest decisions

- Google Drive Master Handoff §27.38 is the latest execution update (P0.14 historical SSI intraday-empty/daily-positive evidence and candidate B5 SHORT/SWING train/validation/holdout temporal leakage audit: 316 engineering tests each Python 3.11/3.12 main CI PASS). §27.37 covers P0.13 multi-venue diagnostics/24 empty B5 calibration slots, §27.36 P0.12 SHS parity/date layout, §27.35 P0.11 RVOL_TOD20/2026 closures and §27.34 P0.10 ATR14 replay. The [full GitHub Master Handoff text snapshot](source-snapshots/00_MASTER_HANDOFF.txt) has now been synchronized through §27.38 and verified by exact text comparison against the Google Drive export; see [snapshot status](source-snapshots/HANDOFF_LATEST_POINTER.md). The native Drive document remains the authority for future edits and formatting.
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

## GĐ4/P0.8 — B5 symbolic formulas and causal raw geometry (2026-11-06)

- [P0.8 formula draft](P0_8_B5_FORMULA_DRAFT.md): separate unapproved SHORT/SWING numeric slots; signed ATR-normalized R_C/R_E/R_F geometry; E_RECLAIM and E_FAILED_BREAK variants; explicitly demands prior independent M15 closed failed-break evidence for the latter and a known-before-followup micro-high anchor for R_F.
- Strict source/clock prerequisites still come from P0.7; strengthened P0.7 to require **all RF support/micro/volume bars** close after retest. Raw geometry never outputs B5 DETECTED, Entry/SL/TP or P&L, and never declares risk-approval.
- SSI MCP read-only B06 spot checks for SHS 01/09/2026 and 13/10/2026 attempted 2026-11-06; both failed with connector `DOWNSTREAM_UNAVAILABLE`. This proves neither historic absence nor coverage recovery; leave B01–B08 OPEN and avoid using SSI source data for B5.
- Synthetic no-lookahead/unit tests extended; `B5/SHORT/FORMULA_DRAFT_0_1` and `B5/SWING/FORMULA_DRAFT_0_1` are separate, all thresholds None / unapproved. No source entitlements, simulator, backtest/OOS, UI, MOCHI or other project changes.

## P0.8 merged main and canonical Handoff §27.32 — 2026-11-06

- [P0.8 PR #27](https://github.com/ngluonghoa/swing-trading-1-8/pull/27) merged `4e5f50844f96a0dc2bf05eb19c63c06fe1cab2f7` into main. [CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42178103421) **163/163 PASS** synthetic engineering tests each on Python 3.11 and 3.12.
- Native Google Drive Master Handoff advanced to §27.32; GitHub full-text snapshot synchronized exactly as a point-in-time export.
- No executable B5 predicate or approved risk/threshold; SSI B01–B08 remain OPEN and B06 read-only calls failed DOWNSTREAM_UNAVAILABLE; real historical BT/OOS remain NOT_RUN.

## GĐ4/P0.9 causal ATR14 / RVOL_TF20 engineering — 2026-11-06

- Added [P0.9 source-guarded indicator primitives](P0_9_CAUSAL_ATR_RVOL.md): `calculate_wilder_atr14()` with 15 D1 bar / 14 true-range warmup, Wilder smoothing and separate prior-knowledge cutoff; `calculate_rvol_tf20()` using 20 comparable closed, verified same-timeframe history bars excluding the target.
- Each input snapshot must be a single causally visible v1.2 revision with complete coverage, verified quality, consistent instrument/provider/price-basis/calendar/aggregation/adjustment and explicit time knowledge. RVOL comparators require explicit matching session class and versioned comparison policy; no automatic provider selection or backfill.
- All return values are **COMPUTED_UNCALIBRATED** or **BLOCKED**; no source-certified signal, approved threshold or actionable trading state. **RVOL_TOD is not implemented** without verified cumulative same-slot historic intraday and official schedule.
- SSI B01–B08, independently licensed/complete source records, ATR14 provider parity, live sessions, real historical backtest/OOS and B5 executable predicates all remain OPEN/NOT_RUN. No other system/UI/MOCHI modifications.

## P0.9 merged main and canonical Handoff §27.33 — 2026-11-06

- [P0.9 PR #29](https://github.com/ngluonghoa/swing-trading-1-8/pull/29) merged into main commit `0500727721ce9ec3d9ee9113cf88343ce2764f9e`. [Main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42182737356) **190/190** synthetic engineering tests PASS on Python 3.11 and 3.12.
- Native Google Drive Master Handoff now §27.33. GitHub snapshot is a point-in-time exact text export; not live bidirectional sync.
- ATR14 is raw Wilder math on input D1 closed bars with separate first-known/verified pre-retest cutoff; RVOL_TF20 is raw same-TF comparable volume (NOT same-slot RVOL_TOD). Neither certifies real source completeness, authorization, P01–P17 or actionable B5 decisions.
- Source blockers SSI B01–B08 OPEN, RVOL_TOD NOT_IMPLEMENTED, historical BT/OOS NOT_RUN.


## GĐ4/P0.10 — D1 expected sessions and ATR14 replay parity (2026-11-06)

- Added [P0.10 session-inventory and ATR14 correction reconciliation](P0_10_D1_SESSION_ATR_REPLAY.md): compare D1 closed v1.2 bars to exact externally supplied `session_period_id`/start/end slots; separate `MATCH_UNCERTIFIED` from missing/extra/bad sessions. Inventories are not independently certified official market calendars.
- Reconcile batch ATR14 against checkpoint+incremental replay (append, late source revision, pre-seed revision requiring full reseed, post-seed corrections). Requires old/new independent causal as-of clock, first-dirty bar, no truncation, unresolved source conflict, changed adjustment/basis or missed sessions. Decimal equality is exact, not tolerance-based.
- New synthetic unit/negative tests verify causal correction first-known checks, missing/extra expected sessions, duplication, old checkpoint quality and replay idempotency. **No live SSI completeness/parity, executable B5, calibrated thresholds, RVOL_TOD, simulator, historical BT/OOS or UI changes.** SSI B01–B08 still OPEN.


## P0.10 main merge and native Handoff §27.34 — 2026-11-06

- [P0.10 PR #31](https://github.com/ngluonghoa/swing-trading-1-8/pull/31) squash-merged `e6ab560fdba1a26ad2774c20823446a5eef5a28b` into main. [Main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42184622891) **214/214 PASS** synthetic unit/negative tests on Python 3.11 and 3.12.
- Native Drive canonical Master Handoff advanced to §27.34; the GitHub snapshot is an exact point-in-time export verified after the docs merge, **not** a live two-way sync.
- [D1 session inventory and ATR14 replay](P0_10_D1_SESSION_ATR_REPLAY.md) detects missing/extra/overlapping expected sessions and tests full batch vs checkpoint/first-dirty correction replay with exact Decimal equality. The expected trading-session manifest itself is externally unverified, so outputs are always `MATCH_UNCERTIFIED`/`PARITY_UNCERTIFIED` or blocked.
- B01–B08 SSI and official market calendar/source permissions still OPEN; no B5 executable detector, qualified RVOL_TOD, real historical backtest/OOS or production trading authority.

## GĐ4/P0.11 — Same-slot cumulative RVOL_TOD20 and official notice closure anchors (2026-11-06)

- [P0.11 contract](P0_11_RVOL_TOD_CLOSURE_ANCHORS.md) now requires exactly **20 distinct prior market sessions** at the SAME Vietnam-local HH:MM, same intraday timeframe/segment/elapsed matched minutes and versioned cumulative matched-volume definition. The target itself is excluded and history must be source-known/verified before the target M1/M5/M15 slot starts.
- Candidate RVOL_TOD is strictly distinct from RVOL_TF: compares cumulative matched-volume through identical exchange-local trading slots, not 20 previous candles, bar-only volume or full D1 volumes. Missing/late conflicting source revisions, wrong auction/continuous classes, incorrect source event linkage or zero denominator fail closed.
- Primary exchange HOSE/HNX 2026 holiday notices give sparse **known nontrading date exclusions** including amended 02/01/2026 and Saturday make-up dates 10/01 and 22/08. These notices are not a full exchange calendar; noncollision yields an explicitly UNCERTIFIED status. Do not infer UPCOM covered as independently verified.
- Source cumulative counts and trading slots remain supplied evidence claims; no SSI intraday record reconstruction, licensed 20-session historical proof or native/derived M1 parity. B01–B08 SSI remain OPEN; B5 P01–P17 and historical BT/OOS NOT_RUN; UI v1.0 DESIGN_LOCKED.


## P0.11 merged main and canonical Handoff §27.35 — 2026-11-06

- [P0.11 PR #33](https://github.com/ngluonghoa/swing-trading-1-8/pull/33) squash merged `2e81c5fa174477287b7a454bb138e4ee3693beb8` into main. [Main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42187628379) **244/244 PASS** synthetic engineering tests on Python 3.11 and 3.12.
- [P0.11 RVOL_TOD20 and official notice anchor details](P0_11_RVOL_TOD_CLOSURE_ANCHORS.md): 20 prior distinct local-date sessions, same slot/TF/segment/elapsed trading minutes/cumulative matched-volume definition and policy; no same-session or late-known source revision substitution. HOSE/HNX published 2026 closure notices are narrow non-trading anchors, **not a certified complete trading calendar**.
- Google Drive native Master Handoff advanced to §27.35, full text snapshot verified as a point-in-time exact export; no auto sync or production data certification. SSI B01–B08 remain OPEN. No B5 actionable detector, approved P01–P17, real historical backtest/OOS or broker execution.

## GĐ4/P0.12 — Read-only SSI intraday vs daily matched-volume diagnostic — 2026-11-06

- Partial recheck of SSI B06: `marketdata_list_stock_infor` full/paged intraday still `DOWNSTREAM_UNAVAILABLE`, **but** `marketdata_list_intraday_stock_infor` successfully returned SHS sample 12/10 (233 rows, total 4,050,300), 13/10 (215 rows, total 5,177,600), and 14/10 (223 rows, total 10,160,800). The detailed daily `total_match_volume` agreed on all three dates. [Evidence and limitations](P0_12_SSI_INTRADAY_DAILY_PARITY.md).
- The connector's documented MM/dd/YYYY timestamp format conflicts with returned date strings such as `13/10/2026 14:45:00`; date-layout, first-known clock, source licence and actual complete minute coverage remain UNVERIFIED. SHS 01/09 (published exchange closure) returned an empty successful intraday response; this does **not** indicate source loss or confirmed no-trade coverage.
- New `ssi_volume_parity.py` parses only a declared date layout, strictly compares matched intraday summed volume vs **daily total_match_volume** for same instrument/venue/date and blocks ambiguous/malformed stamps, bad volumes, duplicate timestamps, future samples, and missing records. MATCH_UNCERTIFIED explicitly **does not** certify first-known native M1/M5, cumulative RVOL-TOD, calendar completeness, corporate-action basis or live trading.
- SSI B01–B08 remain OPEN; B06 has **partial endpoint-level evidence** only. No executable B5, licensed 20-session history, real historical BT/OOS, order execution or UI changes.


## P0.12 merged main + canonical Handoff §27.36 — 2026-11-06

- [P0.12 PR #35](https://github.com/ngluonghoa/swing-trading-1-8/pull/35) squash merged `554d2915f7f26172a34e64d3aed67c8ae9986fd7`. [Main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42192360436) **263/263 PASS** synthetic unit/negative tests each on Python 3.11 and 3.12.
- Partial real SSI read-only B06 evidence: historical SHS 12/13/14 Oct intraday nonpaged 233/215/223 records with summed volumes 4,050,300/5,177,600/10,160,800 equal same-day detailed SSI `total_match_volume`; full/paged `marketdata_list_stock_infor` still DOWNSTREAM_UNAVAILABLE.
- Documented date-format discrepancy: source text advertises `MM/dd/yyyy`, while returned `13/10/2026` cannot be month/day. Engine requires explicit layout and returns MATCH_UNCERTIFIED only, with all market coverage/cumulative/auth/clock/trading certifications false.
- Native Google Drive Handoff §27.36 updated in place; GitHub full-text point-in-time snapshot sync verified. No B5 executable, approved thresholds, 20 licensed contiguous historical sessions, real BT/OOS, UI changes or orders.

## GĐ4/P0.13 — SSI multi-venue evidence and B5 calibration grid draft (2026-11-06)

- Read-only SSI `marketdata_list_intraday_stock_infor` vs `marketdata_list_daily_stock_infor`: new historical 13/14 Oct pairs **SSI/HOSE** 226 rows 11,764,500 / 226 rows 13,466,000; **DIG/HOSE** 222 rows 3,897,600 / 217 rows 3,714,200; **VGI/UPCOM** 142 rows 99,200 / 149 rows 118,500; plus **SHS/HNX 15 Oct** 233 rows 16,614,500. All seven sums equal same-day `total_match_volume`. Together with P0.12 SHS/HNX 12–14 Oct, **10/10 total matches across three venues**, still unverified calendar/minute coverage/rights/first-known timestamps. Full/paged source remains previously DOWNSTREAM_UNAVAILABLE and this phase does not reclassify B01–B08. [P0.13 detailed table and caveats](P0_13_SSI_MULTIVENUE_B5_GRID.md).
- New typed `ssi_multivenue_review.py` recalculates each P0.12 parity receipt and flags duplicate symbol/venue/date, bad source or absent venues; `ALL_VENUES_OBSERVED_UNCERTIFIED` **only means a sampled group exists per venue**. Provider independent, source entitlement, complete minute coverage, timestamp semantics and RVOL-TOD suitability all remain false.
- New `b5_calibration_draft.py` preregisters **24 empty slots** (SHORT/SWING × E_RECLAIM/E_FAILED_BREAK × six W/T/E/S/M/V dimensions), with **four separate unexecuted validation protocols**, frozen metric IDs and source/license/calendar/holdout/cost/risk/OOS gates. All candidate values `None`; no thresholds, optimized performance, calibrated B5, P01–P17 approval, live trading or backtest.
- UI-1.0 DESIGN_LOCKED; CK2/FX2/Scanner and MOCHI unchanged. No broker actions.

## P0.13 merged main and canonical Handoff §27.37 — 2026-11-06

- [P0.13 PR #37](https://github.com/ngluonghoa/swing-trading-1-8/pull/37) squash merged `4d42bf0e00ffcea46ae7290100ac93baa98bbb30`. [Main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42195009545) **286/286 PASS** synthetic unit/negative tests on each Python 3.11 and 3.12.
- SSI read-only historical intraday vs detailed daily volume **10/10 sample totals match** across HOSE (SSI, DIG), HNX (SHS), UPCOM (VGI). This is same-SSI cross-endpoint diagnostic only; no independent provider, calendar, licence, complete minute/20-session native history or first-known evidence. See [P0.13](P0_13_SSI_MULTIVENUE_B5_GRID.md).
- B5 SHORT/SWING × E_RECLAIM/E_FAILED_BREAK × W/T/E/S/M/V: **24 EMPTY slots** and 4 separate nonexecuted review protocols. No numeric candidate grids, P01–P17 approved thresholds, historical backtest/OOS, B5 executable or trade authority.
- Native Google Drive Handoff §27.37 and point-in-time GitHub full-text export exact-match after docs merge. UI v1.0 remains locked, CK2/FX2/Scanner/MOCHI unchanged.

## GĐ4/P0.14 — Read-only SSI historical gap diagnostic and B5 temporal split audit (2026-11-06)

- SSI SHS/HNX read-only endpoint comparison: `marketdata_list_intraday_stock_infor` returned 234 intraday rows on 02/11, sum **13,095,000** matching detailed daily matched volume. On 11/02, 13/04, 01/07, 14/08 and 01/10, that endpoint returned **0 rows** even though the same dates had positive detailed daily matched volumes **7,871,600 / 24,550,600 / 7,136,100 / 20,060,800 / 9,839,500** respectively. See [evidence/table](P0_14_TEMPORAL_SPLIT_SSI_HISTORY.md). No inference about actual SSI archive retention, full-paged raw endpoint state, source rights or historical data deletion; B01–B08 still OPEN.
- Official [SSI MCP resource docs](https://mcp.ssi.com.vn/docs/tai-nguyen/) specify request `toDate=DD/MM/YYYY`, but the intraday **response-field** format/clock policy remains unverified given prior conflicting tool schema vs returned day-first dates. 730-day query cap is not a guarantee of intraday retention.
- `ssi_historical_availability.py` detects **INTRADAY_EMPTY_DAILY_TRADES_UNCERTIFIED** and refuses empty=zero/no-trading assumptions; nonempty matched diagnostic is also UNCERTIFIED. `b5_temporal_split_audit.py` checks chronological TRAIN/VALIDATION/HOLDOUT session ranges, user-supplied embargo, first-known signal/label clocks, cross-fold label overlap/purge, unique events and distinct B5 strategy/variant. It **blocks** leakage; it does not auto-purge events, freeze holdout, approve a label policy or calculate profitability.
- New synthetic negative tests; no source-licensed full history, approved numeric B5 parameters, executable detector, BT-01..16/OOS or broker orders. UI-1.0 DESIGN_LOCKED; CK2/FX2/Scanner/MOCHI untouched.

## P0.14 merged main and canonical Handoff §27.38 — 2026-11-06

- [P0.14 PR #39](https://github.com/ngluonghoa/swing-trading-1-8/pull/39) squash merged commit `7c6b1ec4423773c1aa16e95bca2749daa08573dc`. [Main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42198383542) **316/316 PASS** synthetic tests each Python 3.11 and 3.12.
- Read-only SSI SHS/HNX historical intraday secondary endpoint: 02/11 (234 rows, sum 13,095,000) matched detailed daily volume; 11/02, 13/04, 01/07, 14/08, 01/10 had `ok` but 0 intraday rows while daily reported positive matched trades. The [P0.14 evidence](P0_14_TEMPORAL_SPLIT_SSI_HISTORY.md) says **unresolved endpoint coverage gap**, not inferred SSI licence/retention/deletion; B01–B08 OPEN.
- `b5_temporal_split_audit.py` blocks cross-fold label leakage or unsupported embargo/as-of in independently specified synthetic SHORT/SWING TRAIN/VALIDATION/HOLDOUT candidate plans; no actual purge, frozen holdout, licensed real sessions, numeric B5 thresholds or historical OOS. `ssi_historical_availability.py` refuses empty-as-zero.
- Native Drive Master Handoff §27.38 point-in-time snapshot on GitHub verified exact-match after merge. UI v1.0 DESIGN_LOCKED, CK2/FX2/Scanner/MOCHI and broker orders untouched.
