# Swing Trading 1.8

**GĐ4/P0.14 SSI HISTORY AVAILABILITY / B5 TEMPORAL SPLIT AUDIT — NOT a validated trading system.**

The system design specifies two separate strategies — SHORT (3–10 trading sessions) and SWING (10–60) — with a strict eight-step audit pipeline and 16 B/S zones. The engineering implementation is still partial: none of the 16 zones may issue an actionable signal until source quality, calibrated executable predicates, and reporting/release gates are verified. The approved visual UI-1.0 remains DESIGN_LOCKED.

## Source of truth

- **Python code, repeatable unit tests and CI:** this private GitHub repository.
- **Project design and latest Handoff:** [Google Drive Master Handoff](https://docs.google.com/document/d/1TBGth5NXh-pPYRemsFIKeNjm1_VPhrFAWMsslALq9FI/edit), latest section §27.38; [full GitHub Handoff text snapshot](docs/source-snapshots/00_MASTER_HANDOFF.txt) was verified against the source, with [snapshot status](docs/source-snapshots/HANDOFF_LATEST_POINTER.md).
- **Source snapshots:** [docs/source-snapshots](docs/source-snapshots/00_MASTER_HANDOFF.txt) are point-in-time text exports. They are not automatically synchronized and do not replace the original documents.
- **Approved market data and experiment evidence:** Google Drive where access, licensing, retention and source quality are explicitly verified.
- **MOCHI:** secondary code clone and document backup, deferred while the device is offline. The plugin must remain independent of MOCHI.

Other design sources: [Master Specification](docs/source-snapshots/01_MASTER_SPEC_v1.0_DRAFT.txt) §24, [Data Contract](docs/source-snapshots/05_GD3_DATA_CONTRACT_SMART_CACHE_ARCH.txt) §2/§18, [Early Detection](docs/source-snapshots/06_GD3_EARLY_DETECTION_M15_M5_ARMED.txt), [UI-1.0 locked](docs/source-snapshots/02_REPORT_UI_v1.0_APPROVED_LOCKED.txt), [QA Register](docs/source-snapshots/09_INDEPENDENT_QA_AUDIT_GAP_REGISTER.txt) §14.

## Runtime and testing policy

Use **ChatGPT Python** for permitted on-demand analysis, fixtures and calculations. The Python session is temporary, resource-limited and has no direct Internet access; it is not a persistent service. Use **GitHub Actions** for reproducible automated tests against committed source on Python 3.11/3.12. Neither environment is a continuously running plugin backend. A future scheduled/live runtime and durable cache require a separate approved architecture.

No additional hosted execution service, extra access token or powered-on MOCHI is needed for baseline code tests or current engineering work.

## Local setup

```bash
python3 -m pip install -e .
python3 -m unittest discover -s tests -v
```

## Current work and blockers

Read [CURRENT_STATUS](docs/CURRENT_STATUS.md), [ADR-0001](docs/ADR_0001_MOCHI_INDEPENDENCE.md) and [ADR-0002](docs/ADR_0002_PYTHON_FIRST.md) before new code.

SSI B01–B08 source verification, licensed history, exchange calendar/time semantics, calibrated detectors, full L1–L5 cache, eight-step engine/report binding, realistic fill/fees/settlement model, BT-01..BT-16 acceptance, independent OOS and a hosted runtime are **OPEN**. Synthetic tests do not constitute real historical backtesting, proof of profitability or authorization to place orders.
See [P0.2 source quality engineering contracts](docs/P0_2_SOURCE_QUALITY.md) for implementation evidence and limitations. The current model is not integrated with an approved SSI feed or real historical backtest.

P0.3 adds [controlled legacy-data staging and in-memory quarantine](docs/P0_3_LEGACY_MIGRATION_QUARANTINE.md). This does not migrate production consumers or certify SSI; raw evidence persistence and the historical backtest remain open.

P0.4 adds a [local SQLite evidence-store and checked recovery prototype](docs/P0_4_LOCAL_EVIDENCE_STORE.md). No live persistent volume or raw SSI adapter has been deployed.

P0.4B adds an [explicit original-byte lineage bridge to the local evidence store](docs/P0_4B_RAW_SOURCE_BRIDGE.md). No SSI adapter, persistent production storage or real historical backtest is deployed.

P0.4C adds [independently pinned backup checkpoints, history-prefix verification and strict restore guards](docs/P0_4C_INDEPENDENT_CHECKPOINTS.md). Independent custody and real production storage are **NOT deployed**. Real SSI source validation, detector execution and historical backtest remain OPEN.

P0.5 adds [SSI MCP read-only source triage and fail-closed date/clock/parity contracts](docs/P0_5_SSI_SOURCE_TRIAGE.md); B01–B08 remain OPEN. No licensed replay-ready history, executable detector, historical backtest or deployment has been accepted.

The [B5 causal feature pack](docs/B5_CAUSAL_FEATURE_PACK.md) prepares evidence for the first detector, but has **no executable B5 phase predicates, approved thresholds or actionable signals**. Shared domain features are not a historical backtest or a validated detector.

P0.6 adds [deterministic M5/M15 as-known replay, exact retransmission deduplication and revision-collision guards](docs/P0_6_M5_M15_REPLAY.md). This is synthetic source-domain verification only, not native candle reconciliation or a first historical backtest.

P0.6 was merged in [PR #22](https://github.com/ngluonghoa/swing-trading-1-8/pull/22); the [main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42172733020) passed 128 synthetic tests each on Python 3.11/3.12. Canonical Handoff is §27.30; all SSI B01–B08 and real historic Backtest/OOS remain OPEN/NOT_RUN.

P0.7 adds a [B5 R_C/R_E/R_F phase-evidence receipt inventory](docs/P0_7_B5_PHASE_EVIDENCE_CONTRACT.md), but it is **not a calibrated or executable B5 detector**. A synthetically complete receipt manifest does not authorize a signal or backtest.

The [P0.7 phase contract](docs/P0_7_B5_PHASE_EVIDENCE_CONTRACT.md) was merged via [PR #25](https://github.com/ngluonghoa/swing-trading-1-8/pull/25); [main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42176318156) PASS 147/147 synthetic tests on each Python version. At the P0.7 milestone the Handoff was §27.31 (now superseded by §27.32). The phase receipts are not an executable, calibrated or backtested B5 signal.

P0.8 adds [B5 symbolic SHORT/SWING formulas and causal raw ATR-normalized geometry](docs/P0_8_B5_FORMULA_DRAFT.md). This is a draft feature calculation, not a validated detector, calibrated threshold, market-source entitlement or real historical backtest.


[P0.8 PR #27](https://github.com/ngluonghoa/swing-trading-1-8/pull/27) merged, [main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42178103421) **163/163 PASS** per Python 3.11/3.12; canonical Handoff at that time was §27.32 (now §27.33). The formulas remain draft, thresholds unset and B5 nonactionable; SSI read-only B06 rechecks failed downstream availability and B01–B08 remain OPEN.


GĐ4/P0.9 adds [causal Wilder ATR14 and RVOL_TF20 engineering primitives](docs/P0_9_CAUSAL_ATR_RVOL.md) on qualified v1.2 input snapshots. These are uncalibrated numerical outputs only, not live SSI validation, RVOL_TOD, trade predicates, broker calls or historical backtest results.


P0.9 merged via [PR #29](https://github.com/ngluonghoa/swing-trading-1-8/pull/29); [main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42182737356) **190/190** synthetic tests PASS on Python 3.11 and 3.12. Latest canonical Handoff is §27.33. **RVOL_TOD is not implemented; ATR/RVOL outputs do not qualify data or trading signals.**


GĐ4/P0.10 implements a [D1 expected-session manifest audit and ATR14 append/correction replay parity contract](docs/P0_10_D1_SESSION_ATR_REPLAY.md). It verifies exact match against **supplied** expected sessions and batch/incremental `Decimal` parity only; it does not independently certify official market dates, SSI licensing, source coverage or actionable B5 signals.

P0.10 [PR #31](https://github.com/ngluonghoa/swing-trading-1-8/pull/31) merged and passed [214/214 main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42184622891) on Python 3.11 and 3.12. Canonical Master Handoff is now §27.34. Its D1 session inventory is externally unverified; ATR parity is deterministic synthetic software validation, not independent SSI/source/market proof.

GĐ4/P0.11 adds [source-linked RVOL_TOD20 same-exchange-local-slot cumulative-volume arithmetic and official 2026 HOSE/HNX closure-notice collision checks](docs/P0_11_RVOL_TOD_CLOSURE_ANCHORS.md). These are **synthetic, nonactionable engineering validations**, not a complete independently verified calendar, licensed SSI cumulative intraday history or approved detection threshold.


P0.11 merged via [PR #33](https://github.com/ngluonghoa/swing-trading-1-8/pull/33); [main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42187628379) **244/244 PASS** synthetic unit/negative tests on Python 3.11 and 3.12. Canonical Master Handoff now §27.35. Same-slot cumulative RVOL_TOD20 remains source/market unverified and nonactionable; only listed HOSE/HNX 2026 closure anchors have primary-source notices, not a full trading calendar.

GĐ4/P0.12 introduces [read-only SSI intraday/daily matched-volume reconciliation](docs/P0_12_SSI_INTRADAY_DAILY_PARITY.md) with declared date layout and non-approval guards. Three historical SHS sessions (12–14 Oct 2026) returned 233/215/223 intraday rows and exact daily matched-volume totals, but only on the *non-paged* SSI endpoint; `marketdata_list_stock_infor` still returned `DOWNSTREAM_UNAVAILABLE`. This is observational diagnostic parity **not** source rights, full minute coverage, 20-session RVOL-TOD certification, calibrated B5 or historical backtest.


P0.12 [PR #35](https://github.com/ngluonghoa/swing-trading-1-8/pull/35) merged with [main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42192360436) **263/263 PASS** synthetic tests on Python 3.11 and 3.12. Canonical Handoff is now §27.36. The three-date SHS volume parity is read-only source observation, *not* source entitlement or complete native M1/20-session coverage; SSI date-layout ambiguity and full/paged endpoint failure remain OPEN.

GĐ4/P0.13 adds [cross-venue SSI parity review and a 24-cell B5 calibration grid draft](docs/P0_13_SSI_MULTIVENUE_B5_GRID.md). Seven new read-only historical symbol-date samples (SSI/DIG on HOSE, VGI on UPCOM, SHS on HNX) bring the observed summary to **10/10 matched intraday-vs-daily volume samples** across three venues. These are same-provider diagnostics, not independent session coverage. SHORT and SWING × both B5 E variants × six axes have **no numeric candidate values or approval**, and cannot emit signals or run a historical backtest.

P0.13 [PR #37](https://github.com/ngluonghoa/swing-trading-1-8/pull/37) merged; [main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42195009545) **286/286 synthetic tests PASS** on Python 3.11 and 3.12. Canonical native Handoff latest §27.37. All B5 grid numeric values remain unset; SSI 10/10 same-provider sample volume matches do not approve RVOL-TOD, execution or backtesting.

GĐ4/P0.14 adds a [synthetic B5 SHORT/SWING temporal split/label purge/embargo audit and real SSI historical empty-vs-positive-daily diagnostic](docs/P0_14_TEMPORAL_SPLIT_SSI_HISTORY.md). SSI SHS/HNX intraday 02 Nov 2026 (234 rows; 13,095,000 volume) matched the detailed daily total, while 11 Feb, 13 Apr, 01 Jul, 14 Aug and 01 Oct returned **empty historical intraday despite daily matched trades**. This is a narrow endpoint-availability blocker, not proof of SSI retention duration or data deletion. All source/candidate/holdout/trade approvals remain FALSE; the P0.13 24 B5 numeric parameter cells remain None and no actual OOS/backtest was performed.

P0.14 [PR #39](https://github.com/ngluonghoa/swing-trading-1-8/pull/39) merged and [main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42198383542) **316/316 synthetic tests PASS** each Python 3.11 and 3.12. Latest canonical Handoff is §27.38. Historical SHS/HNX secondary intraday access has empty dates despite positive daily trades; candidate B5 split isolation is structurally audited only with externally unverified session data. No approved B5 numeric parameters, official BT/OOS, provider entitlement, trading signals or orders.
