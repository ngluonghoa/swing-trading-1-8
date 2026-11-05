# Swing Trading 1.8

**Status: PRE-CODE SPECIFICATION → GĐ4/P0.0 FOUNDATION IN PROGRESS.** This repository is a starting scaffold, **not** a validated trading system.

- SHORT (3–10 trading sessions) and SWING (10–60 sessions)
- Strict eight-step decision pipeline and 16 B/S zone identifiers
- Fail-closed signals; no broker integration, live orders, or confirmed trade recommendations
- Backtest harness is established alongside shared domain contracts, but **no real historical backtest has been completed**

## Read first

1. [Master Handoff snapshot](docs/source-snapshots/00_MASTER_HANDOFF.txt): latest decision order, especially §27.20 (Python-first), §27.19 and §27.18.
2. [Master Specification](docs/source-snapshots/01_MASTER_SPEC_v1.0_DRAFT.txt): §24 and §24.14.
3. [Data Contract / Cache](docs/source-snapshots/05_GD3_DATA_CONTRACT_SMART_CACHE_ARCH.txt): §2, §17–18.
4. [Early Detection](docs/source-snapshots/06_GD3_EARLY_DETECTION_M15_M5_ARMED.txt): §14–16.
5. [Locked UI](docs/source-snapshots/02_REPORT_UI_v1.0_APPROVED_LOCKED.txt): preserve design UI-1.0.
6. [QA Gap Register](docs/source-snapshots/09_INDEPENDENT_QA_AUDIT_GAP_REGISTER.txt): §14.

The contents of `docs/source-snapshots/` are text snapshots of documents on Google Drive; they are **not** authoritative live synchronization. See [source index](docs/SOURCE_INDEX.md). Never confuse DOC_FIXED / design PASS with software PASS. Unrun tests are NOT_RUN.

## Developer setup

```bash
python3 -m pip install -e .
python3 -m unittest discover -s tests -v
```

Python ≥3.11; standard library only for the initial scaffold. GitHub Actions will execute these same tests on pushes/PRs. No dependency on MOCHI, M15001, SSI data, or Google Colab for baseline tests.

## Current blockers

SSI B01–B08, unapproved P01–P17 thresholds, clock and calibration, data licenses, executable detectors, cost/settlement/fill simulator, historical OOS evidence, performance benchmarks, renderer and release tests remain OPEN. The framework must not produce ACTION_ELIGIBLE decisions while these remain unresolved.

## GĐ4/P0.0 next steps (2026-11-06)

- [Current engineering status](docs/CURRENT_STATUS.md)
- [Architecture decision: MOCHI independence](docs/ADR_0001_MOCHI_INDEPENDENCE.md)
- [Execution priority: Python-first; Colab optional](docs/ADR_0002_PYTHON_FIRST.md)

### Optional tool (not part of the work plan)

The existing [Colab notebook](notebooks/p0_foundation_smoke.ipynb) and [runbook](docs/COLAB_QUICKSTART.md) are **on hold and optional**. They are retained for potential future experiments only, require no setup now, and do not participate in CI, required backtest workflow, or plugin runtime. No Colab connection or token has been configured.

MOCHI backup/synchronization is **deferred** until the machine is online. All standard GitHub CI tests are independent of MOCHI and Colab. ChatGPT Python is for on-demand analysis when inputs are accessible; GitHub Actions is the reproducible testing baseline. Neither is a persistent live runtime.
