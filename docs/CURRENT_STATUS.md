# CURRENT_STATUS — 2026-11-07

## Latest decisions

- **C3C real connected Google Drive fixture transport smoke merged main ([PR #100](https://github.com/ngluonghoa/swing-trading-1-8/pull/100), main `705916b29cd39349f745b04b966ea8667b86753c`, [independent postmerge CI 42393986166](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42393986166) SUCCESS 1217/1217 each Python 3.11 and 3.12, +30 tests):** a fabricated 237-byte text chunk and 742-byte 16-field JSON manifest were ACTUALLY uploaded/downloaded through connected Drive under existing private `01_IMMUTABLE_CHUNKS__STAGING` and `00_MANIFESTS_AND_INDEX__STAGING`, independently SHA256/parent/file-ID/size/MIME/owner-only verified. [C3C receipt verifier](P0_C3C_GOOGLE_DRIVE_CONNECTOR_SYNTHETIC_READBACK.md) PURE OFFLINE, fail-closed forged rights/hash/metadata negative tests. Source intermediary used temporary Google Docs text export (UTF-8 BOM+CRLF), cleaned up; actual staged fixture files retained. **NO C3B/C4A encoded candle chunk native binary transport, real provider data/vendor licensing, change cursor, KMS, off-host witness/atomic CAS, actual 5-min performance, real Backtest/OOS or trade**. Canonical Handoff §27.65 / Smart Cache §28; C3D native byte transport next, P0.29c/C2C still blocked, UI DESIGN_LOCKED, Forex untouched.

- **C4A+C4B two approved cache+Backtest reference milestones merged main (PR #97 and #98, postmerge main CI 1187/1187 PASS EACH Python 3.11/3.12):** Synthetic weekly time-window chunk grouping INSIDE each SSI/DNSE/VCBS provider/venue/symbol/TF/source-rights partition (21 tests, [C4A contract](P0_C4A_WEEKLY_SEGMENTED_CACHE.md)), only changed week produces new immutable fixture chunk; unchanged weeks reused. SELECTED window loading and FULL SQLite restore revalidates EMA20/ATR14 globally, NEVER reuses a locally seeded per-week EMA as a full-series checkpoint. VN [C4B execution fixture](P0_C4B_VN_BACKTEST_EXECUTION_FIXTURE.md) (+25 tests): explicit fake matched shares/lot/tick/price bands/buy/sell fees/tax and supplied settlement release session index, as-of first-known, long stop+TP both within one OHLC bar=AMBIGUOUS, no real broker fill or trading. PR #97 main `263781298592b51130bcd0dd592fb24d64d1d9e3`, PR #98 main `20ee4579a65e56efe7f0502411019f4e7b95bd60`; [postmerge CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42363426310). Canonical Handoff §27.64 / Smart Cache §27. BOTH synthetic-only: NO real Google Drive chunk upload, provider revision/source rights, real OOS/Backtest, reported trading profits or broker actions; C3C raw-fixture Drive IO still next, P0.29c/C2C blockers unchanged, UI v1.0 DESIGN_LOCKED.

- **C3B chunk+manifest per-partition synthetic Smart Cache merged main (PR #95, postmerge main CI 1141/1141 PASS EACH Python 3.11/3.12, +54):** user-approved [C3B partitioned storage contract](P0_C3B_PARTITION_CHUNK_MANIFEST_CACHE.md); `partition_chunk_cache.py` and 54 fake-only unit tests. Drive long-term cache target now uses **per-CacheIdentity immutable content-addressed chunk + versioned manifest**, NOT whole SQLite upload per 5-min check; local SQLite/RAM remains temporary. Three dedicated private Swing Trading staging subfolders (manifests, chunks, audit) created. Synthetic 5→20→1→20 first creates 5 + 15 chunks, then 0 for unchanged 1/20; one revised fake bar creates only one new manifest/chunk. In-memory staging only: NO real Google Drive chunk bytes uploaded, no real provider cache adapter, no actual network savings measured. PR main `16b83c98097acc0be0933622cec04b4ce7a2f100`, Handoff §27.63 and Smart Cache §26. Next C3C bounded harmless real Drive connector smoke; P0.29c rights/issuer revocation/off-host witness BLOCKED, C2C real on-session measures OPEN, UI v1.0 DESIGN_LOCKED.

- **C3A synthetic SQLite snapshot/restore foundation merged main (PR #93, postmerge CI 1087/1087 PASS EACH Python 3.11/3.12, +44):** [C3A storage note](P0_C3A_SYNTHETIC_CACHE_SNAPSHOT.md), `cache_snapshot_bundle.py` + 44 synthetic tests. WAL-aware no-overwrite offline SQLite snapshot, canonical metadata-only digest/generation/parent manifest, strict schema/bar checksum and EMA/ATR causal parity, pinned no-overwrite restore. Private [Swing Trading synthetic-only Google Drive staging folder](https://drive.google.com/drive/folders/1Wuaale6klzOH19204vCdjlNPfl-wubhp) created and verified nonpublic; no SQLite snapshot/quotes actually uploaded, no transport adapter or authorized real persistent cache. Canonical Handoff §27.62 and Smart Cache §25. P0.29c real vendor key/current revocation/licensed retention/independent off-host custody remains BLOCKED; next C3B synthetic-only Drive transfer readback, with real C2C open-session evidence separate. UI v1.0 locked.

- **C2C offline live-session telemetry readiness merged main (PR #91, postmerge main CI 1043/1043 PASS EACH Python 3.11/3.12, +55):** newly authored [C2C contract](P0_C2C_SESSION_TELEMETRY_READINESS.md) and `c2_session_probe_readiness.py` with 55 synthetic tests. Exact endpoint/provider/task/venue/scope/session-phase typed probes separate monotonic elapsed time, error/correction/provisional row counts, HTTP body versus NETWORK_WIRE_TOTAL bytes and JSON estimates. Aggregation returns same-scope descriptive median/p95 after >=5 nonempty successes; a separate 5 measured-wire sample minimum prevents invented network savings. Weekday/ATO/ATC/continuous coverage is only caller evidence, never authenticated official live session. No source/rights/SLA/router promotion; Saturday is NOT live-session proof. Canonical Master Handoff §27.61 and Smart Cache §24; actual authorized weekday capture remains OPEN, P0.29c rights/key/revocation/off-host witness remains BLOCKED. UI v1.0 remains DESIGN_LOCKED.

- **C2B fair-scope three-provider D1 QA merged main (PR #89, postmerge main CI 988/988 PASS each Python 3.11/3.12, +71):** new [C2B engineering note](P0_C2B_FAIR_SOURCE_QUALITY_BENCHMARK.md), `c2_fair_source_benchmark.py`, 71 synthetic unit tests. Same two-session targets 2026-11-05/06 across FPT/HOSE, SHS/HNX, VGI/UPCOM with nine transient read-only calls: 6/6 SSI RAW vs VCBS RAW OHLC numeric matches; only 2/6 SSI matched volume vs VCBS labelled matched volume, SHS/VGI still differ. DNSE converted close/volume numerically 6/6 but historical price basis and matched volume definition unverified. SSI date-coarse vs DNSE full-history vs VCBS bounded-window requests CANNOT give cross-provider equal-workload speed ranking; benchmark only reports **within identical endpoint+request scope** descriptive median/p95 after >=5 successes, with all source/rights/market-session authority flags FALSE. Transient price inputs yield only aggregated comparisons, NO quote values retained. C2B remains reference-only, no production source cache or trading. Canonical Handoff §27.60, Smart Cache §23. C2C live-session measurements are next but unimplemented, P0.29c external key/head/witness still BLOCKED. UI v1.0 and discarded Work branches unaffected.

- **GĐ4/C2A three-connected-MCP capability audit merged main (PR #87; main CI 917/917 PASS each Python 3.11/3.12, +63):** new [C2A source-contract note](P0_C2A_CONNECTED_MCP_CAPABILITY_AUDIT.md) and `c2_source_capability_audit.py`. Direct Saturday FPT read-only response shapes: SSI D1 detailed 2, SSI intraday whole day 226 OHLCV-style and latest 1, DNSE DAY 247, VCBS bounded D1 2 and VCBS minute 226 **price-only** points. Seven typed endpoint signatures: no verified changed-since revision cursor or exact intraday M5 delta. C1 minute planner maps SSI whole-session `FULL_SESSION`, all other connected surfaces `UNKNOWN`; no VCBS D1 date-window/M1 conflation. Transient bounded metadata-only schema validator rejects invalid OHLC, array misalignment, wrong basis/unit and unknown quote shape; no row values retained or emitted. **No provider licence/right, approved market source, real persistent cache, actionable signals, actual source bandwidth savings, production p95 or auto MCP adapter.** Canonical Master Handoff §27.59 and Data Contract §22. P0.29c external key/custody proof remains blocked; next C2B fair workload measurement. UI/CK2/Forex/Scanner/MOCHI unchanged and Work-era branches not reused.

- **GĐ4/P0.29b external custody onboarding / witnessed floor fixture merged main (PR #85; postmerge main CI 854/854 PASS each Python 3.11/3.12, +59):** new [P0.29b plan](P0_29B_EXTERNAL_CUSTODY_HOST_PLAN.md), `provider_custody_host_plan.py` and 59 synthetic tests. Six independent external evidence roles and nine protected-host controls are inspected as *caller claims only*; duplicate role/actor/evidence, expired or cross-provider input fails. SHA256-linked per-account/provider/key/sequence floor checkpoint fixture validates against a separately *claimed* witness, detects local replay/fork/truncation if witness remains unchanged; cannot detect attacker replacing both log and witness. **No external key ownership, live revocation trust, licensed OHLCV retention, actual protected monotonic storage, real cache/backtest/market indicators, production release or trading authority.** All approval flags hard FALSE. Canonical Handoff §27.58; P0.29c requires real external proof, C2 read-only provider capability QA may run independently. No reused ChatGPT Work branches; UI v1.0 unchanged.

- **GĐ4/P0.29a independently authored conditional custody-head verifier merged main (PR #83; main CI 795/795 PASS each Python 3.11/3.12, +51):** [P0.29a review](P0_29_CUSTODIED_RIGHTS_HEAD_PREVIEW.md) and new `provider_head_custody.py` add a separate Ed25519 signed head tied to exact source/account/event key fingerprint, <=5-minute local clock validity, claimed relative monotonic floor (reject lower seq, forked same seq, older issuance, wrong account), and dual-signed exactly-one-epoch custodian key rotation. Optional P0.28 full event prefix cryptographically bound to signed head and historical floor hash, preserving sticky revocation. **All independent vendor key origin, live revocation freshness, trusted floor across restarts, rights, raw/derived OHLCV cache, indicators, BT/OOS and trading flags remain HARD FALSE.** Offline crypto/synthetic only; no external vendor credentials, transport, 5-minute auto-scanner or operational licence. Canonical Drive Handoff §27.57; P0.29b external onboarding/host-bound custody still NEXT; C2 source data QA separate. No discarded Work P0.29–F1 branch code reused; UI v1.0 unchanged.

- **C1C task-aware Adaptive Source Router preview merged main (PR #81; main CI 744/744 PASS each Python 3.11/3.12, +44):** quality-first D1 DNSE > SSI > VCBS conditional *reference* priority and SSI-only native M1 input for derived M5/M15, blocking price-basis, VND-unit, freshness, calendar, incomplete/provisional, OHLC, volume-scope, adjustment and parity problems before considering speed. Dynamic feedback uses 60-min recent provider+task probes, minimum 5 comparable samples, median latency+failure penalty and 3-failure cooldown. [C1C contract](P0_C1C_ADAPTIVE_SOURCE_ROUTER_PREVIEW.md). Offline, caller-supplied diagnostics only; all returned routes explicitly nonactionable, no vendor rights, actual MCP router runtime, licensed live OHLCV storage, automated scans or production L1–L5. Canonical Handoff §27.56, Data Contract §21; original GĐ4/P0.29 still NEXT; six discarded Work branches not reused.

- **C1B VCBS registered as independent third synthetic-cache provider on main (PR #79; main CI 700/700 PASS each Python 3.11/3.12, +29):** direct read-only VCBS history D1 date range, intraday price-only and batch-quote surfaces checked; [VCBS capability and fail-closed guard](P0_C1B_VCBS_SOURCE_CAPABILITY.md) records raw/adjusted/price-unit/volume semantics, six endpoint capability scopes and independent SSI/DNSE/VCBS synthetic namespaces. No provider retention/right approval, no live VCBS OHLCV storage, no minute OHLCV delta, no actionable source certification or auto-fallback. [Canonical Handoff §27.55](source-snapshots/00_MASTER_HANDOFF.txt) and [Data Contract §20](source-snapshots/05_GD3_DATA_CONTRACT_SMART_CACHE_ARCH.txt). GĐ4/P0.29 rights provenance remains NEXT; no discarded Work branch reused.

- **C1 incremental Smart Cache foundation merged main (PR #77; main CI 671/671 PASS each Python 3.11/3.12):** read-only refresh planner distinguishes provider WINDOWED/FULL_SESSION/UNKNOWN; synthetic-only SQLite stores versioned per-source fixture closed bars and EMA20/Wilder ATR14 checkpoints, with partial-window revalidation, periodic correction reconciliation, append/revise/delete, restart, no OPEN contamination, provider isolation and full-vs-incremental exact equivalence in 54 new synthetic tests. [C1 scope and limitations](P0_C1_INCREMENTAL_SMART_CACHE_FOUNDATION.md). No live MCP adapter wiring, no real OHLCV rights/storage, no true SSI/DNSE delta guarantee, no production L1–L5 cache or scheduled 5-minute scans. [Canonical Data Contract](source-snapshots/05_GD3_DATA_CONTRACT_SMART_CACHE_ARCH.txt) §19 and native Master Handoff §27.54; original GĐ4/P0.29 vendor key/head trust remains NEXT. Discarded ChatGPT Work P0.29–F1 branches not reused.

- **VN R1–R7 rollback governance/fail-closed preflight merged on main (PR #75; main CI 617/617 PASS each Python 3.11/3.12):** independently authored from GĐ4/P0.28 checkpoint; 7-layer FullExecutionProfile/compatibility/SAFE_MODE design adapted to cash equities HOSE/HNX/UPCoM, T+2 pending versus settled-sellable, corporate actions, restricted/pledged shares and price band/tick; 28 synthetic negative/identity tests. [ADR-0003](ADR_0003_VN_RELEASE_ROLLBACK_GOVERNANCE.md) and [VN acceptance matrix](VN_ROLLBACK_ACCEPTANCE_MATRIX.md). **Read-only preflight only: NO approved LKG, no production rollback/pointer, no broker orders, no real backtest or trusted source rights**. Canonical Handoff advanced to §27.53, original next GĐ4/P0.29 remains OPEN; six revoked ChatGPT Work branches were not reused.

- **P0.28 merged on main (PR #67; final branch CI 589/589 PASS each Python 3.11/3.12):** pinned Ed25519 source-rights event prefix verifier (`provider_signed_event_chain.py`) checks canonical signed claim/hold events, exact externally supplied key/fingerprint/head sequence/tip, chain links, replay IDs/nonces, expiry and sticky revocation. Cryptographic proof is CONDITIONAL on unverified key/head input; no independent vendor signer or live stream, no actual source access/retention/backtest/trading. [P0.28 design](P0_28_PINNED_RIGHTS_EVENT_CHAIN.md). Canonical Google Drive Handoff now §27.52; GitHub source snapshot refreshed on docs branch, exact main comparison pending.

- **P0.27 merged main (PR #65; final source branch CI 554/554 PASS each Python 3.11/3.12):** added bounded, nonsecret per-product independent-review packet with three *claimed* review roles (provider entitlement, independent compliance, storage security), actor-token separation and no signature/identity verification. Expiry or any claimed provider revocation, terms-expiry notice or security suspension globally blocks packet (no reinstatement path); all rights permissions remain **hard False** even when packet status is `READY_FOR_EXTERNAL_REVIEW_ONLY`. [P0.27 review packet](P0_27_INDEPENDENT_RIGHTS_REVIEW_PACKET.md). Caller-supplied hold history is not authentic/tamper-evident. Canonical Google Drive Handoff §27.51; snapshot exact on docs branch, final main equality pending.

- **P0.26 merged on main (PR #63; final source branch CI 520/520 PASS each Python 3.11/3.12):** official SSI developer terms confirm registered, approved FastConnect account and rate/secret obligations, and newer V3 1-year intraday limit; **do not conflate V3 auth with FastConnect Data V2 IntradayOhlc**. DNSE signed OpenAPI still independent of DAY MCP. New `provider_rights_review.py` accepts opaque `EVID-` references and unverified per-account claims for six separate scopes (download, raw cache, derivative conversion/retention, research BT and OOS), refuses expired/cross-provider/self-declared rights and keeps all source authorizations hard False without an independently approved provider trust root. [P0.26 review gates](P0_26_PROVIDER_RIGHTS_REVIEW_GATE.md). Canonical Drive Handoff §27.50; GitHub full-text snapshot refreshed on docs branch, final main equality pending.

- **P0.25 source merged main (PR #61; final branch CI 500/500 PASS each Python 3.11/3.12):** verified official docs for separate SSI FastConnect `Market/IntradayOhlc` (integer `resollution` default 1 minute, not explicitly enumerated M5/M15) and DNSE OpenAPI `GET /price/ohlc` (explicit 1/5/15 resolutions, X-API-Key/X-Aux-Date/X-Signature), **neither present as a corresponding connected MCP action**. New offline `native_minute_bar_source_plan.py` catalog plus inert query sketches, every account-rights/source-time/coverage/backtest/trading property blocked. [P0.25 evidence](P0_25_NATIVE_MINUTE_SOURCE_GATE.md). Canonical Google Drive Handoff now §27.49; GitHub snapshot refreshed on docs branch and requires post-merge exact comparison.

- **P0.24 merged on main (PR #59; final branch CI 480/480 PASS each Python 3.11 and 3.12):** SSI SHS 14/10/2026 read-only intraday alternative endpoint returned 223 distinct time labels, 16 observed inter-label gaps >1 minute, max 92 minutes (potential lunch); full paginated endpoint again `DOWNSTREAM_UNAVAILABLE`. No inference of 223 native M1 bars or data loss. New ephemeral `ssi_intraday_label_diagnostics.py` distinguishes conditional DD/MM vs MM/DD and computes descriptive minute geometry only; all time semantics/data rights/BT readiness hard false. [P0.24 evidence](P0_24_SSI_INTRADAY_LABEL_SURFACE.md). Canonical Google Drive Handoff now §27.48; GitHub full-text snapshot synchronized on the docs branch, final main equality pending.

- **P0.23 merged on main (PR #57, final branch CI 465/465 PASS each Python 3.11/3.12):** executed real read-only SSI/DNSE probes for SHS (SSI detailed daily 2 rows, SSI alternative intraday 215 ticks, SSI full paginated endpoint DOWNSTREAM_UNAVAILABLE, DNSE price history 248 DAY rows); direct response was **NOT** persisted as market data. New in-memory `source_capability_evidence.py` emits provider/endpoint/status/row count only with all rights/first-known/price basis/M1-M5-M15/backtest flags hard closed. [P0.23 source evidence](P0_23_LIVE_SOURCE_CAPABILITY_EVIDENCE.md). Canonical Google Drive Handoff now §27.47; GitHub full-text snapshot synced on docs branch and pending final main comparison.

- **P0.22 merged on main (PR #55; final source branch CI 448/448 PASS each Python 3.11/3.12):** P0.21 signed offline archive verifier rejects WAL-mode header independently of sidecar presence; fixture-only one-shot host conformance harness reuses P0.16 SSI-first/DNSE-fallback D1 reference router with exact allowlisted arguments, canonical bounded static responses and credential-key denial. No hosted runtime/data licence. [P0.22 spec](P0_22_WAL_HOST_FIXTURE_CONTRACT.md). Canonical Google Drive Handoff now §27.46; GitHub full-text snapshot synchronized in docs PR, exact main check required.

- **P0.21 merged main (PR #53; final branch CI 434/434 PASS each Python 3.11/3.12):** opt-in Ed25519 signed offline P0.18 metadata archive verifier reads bytes using pinned POSIX FDs, checks SHA256 and SQLite integrity in isolated `:memory:` database, and rejects sidecars, quote-bearing cache, unsafe file modes and unsigned/tampered manifests. Does **not** make live path-based SQLite code safe for production. [P0.21 design](P0_21_OFFLINE_SIGNED_METADATA_ARCHIVE.md). Canonical Google Drive Handoff now §27.45; GitHub full-text point-in-time snapshot synchronized in documentation PR, final comparison on main required.

- **P0.20 merged main (PR #51, final branch CI 423/423 PASS per Python 3.11/3.12):** nofollow/read-only pinned SQLite FD inspection and detached Ed25519 verifier with externally supplied pinned public-key fingerprint, optional `cryptography` extra. This does NOT solve TOCTOU for separate SQLite path-based connections or deploy a signer/host. [P0.20 document](P0_20_PINNED_FD_ED25519_VERIFY.md). Google Drive Handoff now §27.44; GitHub point-in-time source snapshot synchronized on the documentation branch, pending main verification.

- **P0.19 merged main (PR #49; final branch CI 405/405 PASS per Python 3.11/3.12):** preflight of local POSIX SQLite directory/file/symlink/hardlink/sidecar permissions and detached HMAC-SHA256 manifest integrity check, with opt-in verify/restore/prefix wrappers. **NOT** independent public-key signature, live storage approval or deployed custodian. [P0.19 scope](P0_19_STORAGE_PREFLIGHT_CHECKPOINT_CUSTODY.md). Google Drive canonical §27.43, GitHub point-in-time snapshot refreshed in documentation PR.

- **P0.18 merged on main (PR #47, branch CI 387/387 PASS each Python 3.11/3.12):** metadata-only logical journal backup and independently pinnable whole-file+chain checkpoint, restore with SHA256 recheck and new-file-only publication, historical prefix validation; SSI/DNSE quote cache is never copied into backup. There is no running host, approved retention/licence, external trust custodian, production recovery or historical backtest. [P0.18 specification](P0_18_METADATA_ONLY_CHECKPOINT_RECOVERY.md). Canonical Google Drive Handoff now §27.42; GitHub snapshot synchronized on the documentation branch, final main equality to be checked.

- **P0.17 merged on main (PR #45; branch CI 376/376 PASS on Python 3.11/3.12):** local SQLite reference journal, append-only metadata SHA256 chain and consent-gated expiring provider-specific diagnostic quote cache. All storage/retention permissions are caller assertions only; no host deployment, approved data licence, independent custody, source certification or trading authority. See [P0.17 document](P0_17_REFERENCE_JOURNAL.md). Canonical Google Drive Handoff updated to §27.41; GitHub snapshot requires exact text verification after this documentation merge.


- Google Drive Master Handoff §27.52 is the latest execution update: P0.28 conditional pinned Ed25519 rights event-chain verifier, [source PR #67](https://github.com/ngluonghoa/swing-trading-1-8/pull/67) merged, [589/589 synthetic CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42257931052) PASS on each Python 3.11/3.12. §27.51 covers P0.27 review-only rights packet; §27.50 covers P0.26 six-scope claims; §27.49 covers native minute API discovery. The [full-text mirror](source-snapshots/00_MASTER_HANDOFF.txt) is point-in-time, not a production source of licensed market data. Verification does NOT authenticate provider signer/complete current revocation chain, activate retention or enable historical BT/OOS.
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

## GĐ4/P0.15 — SSI-first DNSE D1 read-only reference fallback (2026-11-06)

- Read-only MCP DNSE `price_get_history` returned 248 DAY OHLCV records per SHS/SSI/DIG/VGI (2025-11-07→2026-11-06). DNSE 09:00 Vietnam local D1 timestamp is a **session label, not close/first-known**. DNSE reported close in THOUSAND_VND vs SSI detailed daily VND; sampled 13 Oct close/volume matched on SHS/SSI/DIG/VGI. Historical SHS 11 Feb, 13 Apr, 1 Jul, 14 Aug and 1 Oct DNSE D1 volumes match SSI detailed daily, even though the **SSI historical intraday endpoint returns empty** on those dates. These are D1 observations, NOT intraday rescue. [P0.15 source and adjustment caveats](P0_15_DNSE_D1_FALLBACK_REFERENCE.md).
- New `dnse_d1_reference_fallback.py` implements deterministic SSI-first source selection with injected read-only provider ports. Missing/explicitly unavailable SSI D1 → DNSE daily reference candidate; successful SSI D1 → no DNSE call; mismatched primary receipt → block. Timeframe not D1 blocked **before any source call**. Same-day D1 blocked absent verified session cutoff. Retrieval after historical as-of blocked. DNSE arrays t/o/h/l/c/v strictly checked, VND×1000 normalized, price basis always UNKNOWN.
- `PRIMARY_SSI_REFERENCE_ONLY` / `FALLBACK_DNSE_REFERENCE_ONLY` always have source rights/calendar/first-known/indicator eligibility/backtest/action FALSE. No automatic live plugin wiring, true certified D1 fallback, Smart Cache provider namespace migration, real historical BT/OOS or brokerage actions. SSI B01–B08 OPEN and 24 B5 numeric slots still NONE.

## P0.15 merged main + canonical Handoff §27.39 — 2026-11-06

- [P0.15 PR #41](https://github.com/ngluonghoa/swing-trading-1-8/pull/41) squash merged `bf501dfb21223d93020ffab17e48f8eb4283e348`. [Main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42204138440) **341/341 PASS** synthetic unit/negative tests each on Python 3.11 and 3.12.
- DNSE `price_get_history` one-year DAY D1 for SHS/SSI/DIG/VGI; samples normalized to VND from thousand-VND and cross-referenced against SSI detailed daily close/volume across HOSE/HNX/UPCOM. DNSE D1 09:00 Vietnam local is a **session label, never bar-close**. Older SHS adjusted price differences mean basis parity UNKNOWN. See [P0.15 evidence and router](P0_15_DNSE_D1_FALLBACK_REFERENCE.md).
- New `dnse_d1_reference_fallback.py` provides callable-injected SSI-first, DNSE-on-unavailable D1 **reference-only** routing; no intraday substitution, no retroactive use before source fetch, no same-day D1 without independently verified close, no cross-provider merging. All indicator/backtest/action/certification flags false.
- **Production automatic live MCP adapter wiring not yet deployed**, no certified D1 fallback, full source licensing/calendar/adjustments or first-known history. SSI B01–B08, B5 P01–P17 and all 24 numeric slots OPEN/None; real historical BT/OOS NOT_RUN. Native Google Doc §27.39 canonical, GitHub snapshot verified point-in-time exact-match.

## GĐ4/P0.16 — Read-only injected SSI/DNSE transport bridge with isolated reference cache (2026-11-06)

- Rechecked real SSI marketdata_list_daily_stock_infor(SHS,13/10/2026) envelope status/data.stocks with exact-day OHLC 11,600/11,900/11,500/11,700 VND and total_match_volume=5,177,600; DNSE price_get_history(SHS) returned 248 aligned DAY o/h/l/c/v/t rows, 09:00 Vietnam-local session labels (not bar closing timestamps).
- New [P0.16 adapter contract](P0_16_MCP_ADAPTER_READONLY_BRIDGE.md): `ReadOnlyMcpD1Bridge` accepts authorized host-injected SSI/DNSE read-only transports, UTC receipt clock and separated volatile cache. It parses response envelopes, calls existing SSI-first router, falls back ONLY on SSI DOWNSTREAM_UNAVAILABLE or absent exact date; unknown/invalid source response fails closed. Records provider/date/endpoint/timestamp + SHA256 response digest; never invents provider-native first-known or source record IDs.
- `ProviderSeparatedReferenceCache` partitions quotes by provider and snapshot ID for DIAGNOSTICS; it does not automatically replace a failing source and is not production L1–L5 or durable storage. All selected quotes and BridgeRun remain REFERENCE_ONLY, not eligible for indicators, historical backtest or orders. The user-facing Plugin is NOT automatically wired to MCP from GitHub/CI.
- Synthetic negative tests include source error classification, date selection, malformed payloads, retrospective lookahead, explicit provider namespaces and no-forged-approval invariants. SSI B01–B08 OPEN, B5 numeric slots None and historical BT-01..16/OOS NOT_RUN; UI-1.0 locked, CK2/FX2/Scanner/MOCHI unchanged.

## P0.16 merged main + native Handoff §27.40 — 2026-11-06

- [PR #43](https://github.com/ngluonghoa/swing-trading-1-8/pull/43) squash merged `baa521bf78f53ca34fdabab11503b06648aa7746`. [Main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42207319126) **360/360 PASS** synthetic tests on each Python 3.11 and 3.12 (P0.15 baseline 341, +19).
- [P0.16 injected MCP adapter bridge](P0_16_MCP_ADAPTER_READONLY_BRIDGE.md): real read-only SSI detailed D1 and DNSE DAY response-shape checks; host-injected read-only provider callbacks, strict date/volume/unit, unknown adjustment basis, first-known fetch clock, explicit SSI DOWNSTREAM_UNAVAILABLE classification, no intraday fallback. Metadata-only response SHA256 receipts, separate SSI/DNSE namespaces in **volatile in-memory reference cache**, not persistent Smart Cache L1–L5 or a fallback to stale cache.
- **Not yet deployed as automatic Plugin MCP adapter/runtime**: GitHub Actions does not hold ChatGPT connector credentials; Python callables require approved host wiring. No independent source right/calendar/adjustment verification; source B01–B08 OPEN, 24 B5 numeric slots None, no BT/OOS or actionable signal. Native Google Doc §27.40 is canonical and full-text GitHub snapshot verified exact-match.

## GĐ4/P0.17 increment — 2026-11-06 (PR #45 merged; branch CI PASS)

- Implemented `reference_journal.py` and synthetic negative tests. Explicit run ID / provider, audit-clock rejection, immutable journal SHA256 linkage and stale-tip rollback; optional cache expiry/purge; default metadata-only persistence.
- **NOT_DEPLOYED/NOT_VERIFIED:** approved external persistent volume or data-retention licence, encryption/secure deletion, independent journal checkpoint and restore, authenticated continuous MCP host, production L1–L5, B5 executable, SSI B01–B08, BT/OOS and orders.

## GĐ4/P0.18 merged implementation — 2026-11-06 (PR #47, final branch CI PASS)

- Added `reference_journal_recovery.py` plus quote-free logical snapshot, `JournalCheckpoint`, separately pinned restore and prefix-guard tests. Shared SSI/DNSE cache is still **one SQLite database**; checkpoint export includes only metadata journal rows, and never quote data even in deleted pages/WAL of the exported file.
- Not production-ready: source quote retention and live SQLite/WAL sanitization, independent signed checkpoint custody, runtime/volume approval, disaster recovery exercises, native historical M1/M5/M15 source rights and actionable signal gates remain OPEN.

## GĐ4/P0.19 merged implementation — 2026-11-06 (PR #49; final branch CI PASS)

- Added `reference_storage_preflight.py`, `reference_checkpoint_mac.py` and synthetic tests. Local root+SQLite DB+sidecars permission scans, no symlinks/hardlinks/git trees and strict 0700/0600 modes; detached domain-separated HMAC over the entire checkpoint + key ID/seal time; opt-in authenticated metadata-only recovery.
- **NOT_DEPLOYED:** no independently attested separate custodian, asymmetric digital signature, production storage/ACL/encryption, source retention approval, live read-only MCP runtime, B5 calibration or real historical BT/OOS.

## GĐ4/P0.20 merged implementation — 2026-11-06 (PR #51, CI PASS)

- `reference_pinned_fd.py`: openat/dirfd, O_NOFOLLOW, inode/path identity and SQLite sidecar validation for one read-only inspection context. **NOT** a safe wrapper for regular `sqlite3.connect(path)` or immutable WAL snapshot.
- `reference_checkpoint_signature.py`: verifier-only Ed25519 public-key signature with domain separation, exact checkpoint, key/store identities and pinned public-key SHA256; opt-in restore and historical prefix wrappers.
- Retention licence, production host encryption/ACL, independent signer/key trust anchor, native SSI/DNSE historical intraday, B5 numeric slots and real BT/OOS are OPEN.

## GĐ4/P0.21 merged implementation — 2026-11-06 (PR #53, branch CI PASS)

- `reference_offline_verified_archive.py` and negative tests: Ed25519 detached trusted-signature gate, O_NOFOLLOW pinned FD + SHA256 fixed-size streaming, `sqlite3.deserialize` into read-only in-memory copy, verify P0.17 journal chain and zero cached quote rows. Explicitly OFFLINE METADATA ONLY; no source OHLCV copied or exposed.
- Open gates: approved hosted SQLite/VFS + ACL/encryption, actual independent trust anchor and source entitlement, native historical SSI/DNSE M1/M5/M15 and B5/BT/OOS. UI and other modules unchanged.

## GĐ4/P0.22 merged increment — 2026-11-06 (PR #55; final source CI PASS)

- Explicit SQLite header rollback-mode (0x01 0x01) gate for P0.21 **offline** signed metadata backup: reject WAL-mode (0x02 0x02) even if sidecars absent and separately signed.
- New fixture-only SSI/DNSE MCP conformance harness with one-shot, exact SSI/DNSE D1 endpoint arguments, no live callables/credentials, max 128 KiB canonical JSON, D1-only/no current-day substitution and reference-only receipts. Not an authenticated real MCP runtime.
- Live SQLite writer/reader still path-based, actual SSI B01–B08 and native historical M1/M5/M15 rights/coverage, B5/BT/OOS and trusted host/custodian remain OPEN.

## GĐ4/P0.23 merged source audit — 2026-11-06 (PR #57, final branch CI PASS)

- Evidence: `marketdata_list_daily_stock_infor` SHS 13/10/2026 returned 2 daily rows including prior session; `marketdata_list_intraday_stock_infor` same date returned 215 timestamp-labeled rows (not proven M1/M5/M15 complete); `marketdata_list_stock_infor` DOWNSTREAM_UNAVAILABLE on one attempt; DNSE `price_get_history` returned 248 **DAY** rows. Retrieved via connected MCP tools in chat, raw OHLCV NOT persisted to GitHub, Drive or Mac.
- Safety: source timestamps & adjustment semantics unresolved, explicit licence/retention not verified, SSI full pagination and native M1/M5/M15 coverage unproven. Synthetic code tests PASS 465/465 each Python 3.11 and 3.12; live data access does not elevate any signal, BT/OOS or production host.

## GĐ4/P0.24 SSI time-label diagnostics — 2026-11-06 (PR #59 merged, CI PASS)

- Direct connected SSI read-only SHS 14/10/2026 sample: 223 labelled rows, 223 distinct labels, descending from 14:45 to 09:00; conditional DD/MM interpretation shows 16 distances >1 minute, largest 92 min. HNX official continuous trading includes 11:30–13:00 lunch, so gaps are NOT evidence of lost minute bars. Full SSI sysToken endpoint still `DOWNSTREAM_UNAVAILABLE` on second read-only try.
- Code only scans provider-specific timestamps transiently and returns label counts/gap geometry, not raw OHLCV. P0.5 timestamp-order conflicts and first-known remain unverified; no native licensed historical M1/M5/M15 or full pagination, no B5 calibrated executable detector, no real BT/OOS, no SQLite live-production approval.

## GĐ4/P0.25 documented native-minute source discovery — 2026-11-06 (PR #61 merged, final CI PASS)

- Distinguish connected SSI intraday tick labels and DNSE DAY-only history from external public SSI FastConnect native minute OHLC and DNSE signed OpenAPI 1/5/15 OHLC. SSI public guide GET vs older vendor PDF POST and unenumerated integer resolution are unresolved; DNSE requires API key plus request signature. Do not infer account entitlement or legal retention from public docs.
- Implement 4-product fixed catalog, M1/M5/M15 documentation evidence, and no-I/O first-page sketch. Reject connected MCP substitutions and unsupported SSI 5/15 guess; validate explicit DNSE single-session UTC Unix range. No live provider call, API key collection, quote persistence, B5 execution or real BT/OOS.

## GĐ4/P0.26 source entitlement evidence intake — 2026-11-06 (PR #63 merged, CI PASS)

- Strict bounded metadata-only docket intake, provider-specific scope claims, expiry/future/duplicate/invalid review guards; no secrets/account number/agreement text, OHLCV, market API requests or production grants. Public documentation is NOT contractual rights; even a vendor-letter **claim** cannot enable cache, B5, BT/OOS or orders.
- Source-contract clarification: SSI V2 `fc-data` and SSI Developer FastConnect V3 are separate and cannot share assumed HTTP/auth/session semantics; current SSI/DNSE MCP methods still lack externally approved native M1/M5/M15. Host SQLite WAL/VFS, independent vendor entitlement reviewer, data calendar/first-known and backtest simulator remain OPEN.

## GĐ4/P0.27 rights packet and revocation triage — 2026-11-06 (PR #65 merged, CI PASS)

- `provider_review_packet.py` accepts only P0.26 typed unverified claims and opaque `ATST-/ACTR-/HOLD-` role/event references. Fail closed for missing six scopes, missing role or expiry; a held/revoked product remains blocked and requires external cache/backup purge audit; no permission to read, retain or backtest ever changes to True.
- Synthetic tests include role crossover, cross-product claims, revoked/expired/timestamp conflict, lack of signed authorization and no secret/account/price leak in the packet. No SSI/DNSE external native M1/M5/M15 connection, no storage entitlement, no live SQLite security approval, executable B5 or real BT/OOS.

## GĐ4/P0.28 signed source-rights prefix verification — 2026-11-06 (PR #67 merged, final CI PASS)

- New `provider_signed_event_chain.py`: strict version/domain separation and canonical signed Ed25519 event bytes for product-specific GRANT_CANDIDATE/REVOKE/SECURITY_SUSPEND, SHA-256 hash chain and externally claimed head pin. Reject changed/tampered signatures, truncated or stale claimed prefix, duplicate nonce/ID, future-known events, expired candidate; revoked/suspended hold cannot be cleared by a later candidate.
- No external provider trust root, authenticated current revocation head, operational SSI/DNSE credential or approved licence. Every read/cache/backtest/order authorization property stays False even if synthetic signature checks PASS. No signed licence is fabricated, no real OHLCV ingested or persisted, no production SQLite/VFS or B5 real BT/OOS.
