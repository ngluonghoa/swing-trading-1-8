# Changelog — Swing Trading 1.8

Entries document engineering source changes only. They do not imply a live release or an approved trading system.

## Unreleased — H3-A deep legacy assessment (2026-11-08)

- AST-based reproducible review/matrix on all 63 existing Python modules: ~31 KEEP and 32 IMPROVE heuristics; 0 automated REPLACE/REMOVE; no live source or deployment claims.
- CI enforces updated matrix, captures JSON and Markdown review evidence, retains all H2 regression/source-boundary/wheel checks.
- Manual assessment: pinned-FD missing-file exceptions have intentional fail-closed semantics and must not be deleted mechanically; incremental cache transactional/update complexity is a prioritized change candidate, only with golden tests and strict rollback.

## Unreleased — H2 legacy modernization (2026-11-08)

- H2-A: CI scans all existing Python source modules, imports, dependencies and test-map audit artifact; protects withdrawn C3C and legacy core boundaries.
- H2-B: retrofitted the actual SSI/DNSE D1 reference bridge, legacy BacktestHarness, C3B and C4A cache read ports with versioned explicit contracts and before/after parity tests.
- H2-C: compared pinned fake cache histories across legacy backends, rejecting changed source revision, first-known timestamp and global indicator checkpoint; never authorizes a live data migration.
- H2-D: static test import coverage mapping replaces misleading same-named test assumption; all source/test/script files now pass whole-tree correctness lint, while modified modules run stricter F lint.
- No market strategy, UI, SQLite wire/schema, Forex Trading, approved production release, vendor entitlement or signed LKG changes. The package version remains 0.0.1.

## Unreleased — H1 maintenance / contract hardening (2026-11-08)

- Versioned structural port descriptors, explicit source namespace and fail-closed compatibility checks; no live-data or trading permissions conferred.
- Immutable engineering build snapshots and diff previews for source/contract/docs/dependency fingerprints; no signed operational LKG.
- New consumer-driven regression coverage for provider substitution, add/replace/remove with consumer pins, atomic incompatible-swap rollback, no dynamic-attribute side effects, causal replay, cache partition isolation, contract version mismatch and internal dependency cycles.
- CI checks on Python 3.11/3.12 plus a separate lint, dependency-consistency, contract and clean-wheel-install job.
- PR checklist and maintenance governance document; UI v1.0, C3B/C4A/C4B and the separate Forex repository unchanged.
- Package version deliberately remains 0.0.1; no release tag is created.

## Historic baseline — post-C4B rollback

- PR #102 reverted C3C PR #100 and documentation sync #101 to the exact post-C4B content of PR #99; Git history retained, no live licensed market data.
