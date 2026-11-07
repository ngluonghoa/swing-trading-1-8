# H2-D — Whole-repository static checks and honest test mapping

Scope: Swing Trading 1.8 legacy engineering, not provider authorization, research performance, trading or live migration.

## New full-legacy gate

GitHub Actions now runs Ruff correctness checks E9/F821/F822/F823 over EVERY source module, EVERY test and EVERY engineering script, in addition to targeted strict E4/E7/E9/F lint on changed H1/H2 code, dependency check, wheel build/install, all unit tests on Python 3.11 and 3.12, and the whole-package architecture audit.

The suite remains deliberately conservative: it does NOT claim full mypy/pyright, full-project F401/style compliance, vulnerability-free dependencies, tamper-proof CI signing, approved operational release, guaranteed complete market data or real profitability.

## Test coverage audit semantics v2

scripts/h2_architecture_audit.py now maps each source module to test files that explicitly import it (import/from statements parsed by AST), not to filenames matching test_module.py. Some legacy core modules are exercised from foundation/backtest/reference tests under other names. The machine-readable inventory reports BOTH named_test_file_exists and statically_imported_by_tests/direct_test_files to avoid confusing naming with evidence.

Even a direct import is not proof of branch/method coverage, as a test may not execute the relevant code path. The only authentic pass receipt is an executed CI test run; future instrumented branch coverage, mutation tests, integration source-authority tests and real N/N−1 restore are separate optional acceptance gates.

## Protected compatibility principles

- Core dependency graph must remain acyclic; no domain direct source/SQLite/cloud imports.
- Never reintroduce old C3C source/fixtures or alter unrelated FX/CK projects.
- Refactored SSI/DNSE bridge, causal replay and cache cross-read ports have consumer-driven before/after regression tests; semantic cache swaps fail on changed first-known/revision even when numeric prices match.
- Any future provider/algorithm or cache change requires explicit scope, version, source identity, QA and backout receipt before PR approval.

## Remaining gaps / no overclaim

Full branch coverage percentage, full-repo type checking, updated dependency lock/true reproducible signed RC, protected GitHub main ruleset, real SS/DNSE/VCBS licensed data, current revocation head, cloud CAS writer, broker inventory and production release/rollback remain unverified or not implemented. The engineering hardening cannot override these source-rights and runtime gates.
