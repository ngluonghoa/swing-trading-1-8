# Swing Trading 1.8

**GĐ4/P0.4 ENGINEERING FOUNDATION — NOT a validated trading system.**

The system design specifies two separate strategies — SHORT (3–10 trading sessions) and SWING (10–60) — with a strict eight-step audit pipeline and 16 B/S zones. The engineering implementation is still partial: none of the 16 zones may issue an actionable signal until source quality, calibrated executable predicates, and reporting/release gates are verified. The approved visual UI-1.0 remains DESIGN_LOCKED.

## Source of truth

- **Python code, repeatable unit tests and CI:** this private GitHub repository.
- **Project design and latest Handoff:** [Google Drive Master Handoff](https://docs.google.com/document/d/1TBGth5NXh-pPYRemsFIKeNjm1_VPhrFAWMsslALq9FI/edit), latest section §27.25; [full GitHub Handoff text snapshot](docs/source-snapshots/00_MASTER_HANDOFF.txt) was verified against the source, with [snapshot status](docs/source-snapshots/HANDOFF_LATEST_POINTER.md).
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
