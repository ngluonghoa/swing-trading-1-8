# Changelog — Swing Trading 1.8

Entries document engineering source changes only. They do not imply a live release or an approved trading system.

## Unreleased — H1 maintenance / contract hardening (2026-11-08)

- Versioned structural port descriptors, explicit source namespace and fail-closed compatibility checks; no live-data or trading permissions conferred.
- Immutable engineering build snapshots and diff previews for source/contract/docs/dependency fingerprints; no signed operational LKG.
- New consumer-driven regression coverage for provider substitution, causal replay, cache partition isolation, contract version mismatch and internal dependency cycles.
- CI checks on Python 3.11/3.12 plus a separate lint, dependency-consistency, contract and clean-wheel-install job.
- PR checklist and maintenance governance document; UI v1.0, C3B/C4A/C4B and the separate Forex repository unchanged.
- Package version deliberately remains 0.0.1; no release tag is created.

## Historic baseline — post-C4B rollback

- PR #102 reverted C3C PR #100 and documentation sync #101 to the exact post-C4B content of PR #99; Git history retained, no live licensed market data.
