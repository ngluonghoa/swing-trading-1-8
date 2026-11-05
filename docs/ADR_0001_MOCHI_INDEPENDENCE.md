# ADR-0001 — MOCHI-independent operation and controlled Git synchronization

**Status: APPROVED ARCHITECTURE GOAL; hosted runtime NOT DEPLOYED (2026-11-06).**

## Decision

- GitHub Private `ngluonghoa/swing-trading-1-8`: authoritative code, history, testable commits and CI.
- Google Drive: canonical project Handoff, design specifications and approved data/evidence. Code snapshots in GitHub are not bi-directional automatic document sync.
- [ADR-0002](ADR_0002_PYTHON_FIRST.md) controls test execution: ChatGPT Python for permitted ad hoc experiments and GitHub Actions for repeatable CI. Neither is an always-on hosted runtime.
- MOCHI: an optional working clone and a secondary local document/code backup. **Defer** any MOCHI change until online and explicitly requested. The normal engine, CI, cloud runtime and source access must never depend exclusively on MOCHI.
- If persistent intraday/scheduled processing is required, select and approve separate cloud hosting/storage/recovery. There is **no** production cloud runtime today.

## Safe two-way Git workflow when MOCHI is online

1. Clone only the authorized directory: `/Users/mochi/git-clone/namtrai-works/swing-trading-1-8`.
2. Local changes: inspect status → branch → commit → push → CI/review.
3. Remote changes: fetch → check divergence and local changes → fast-forward pull when clean.
4. Never silently force-push or overwrite uncommitted changes; stop on conflicts and request a reviewed resolution.
5. Back up Drive documents to MOCHI one-way with versioning, checksums and a restore test. A backup job must not mirror accidental deletions.
6. MOCHI being powered off must not prevent normal plugin analysis or GitHub code testing.

## Operational acceptance (NOT_RUN)

- GitHub CI works while MOCHI is powered down.
- Live plugin execution must work without MOCHI after its own hosting, credentials, data and storage have passed independent acceptance.
- Source feed licensing and market session clock, persistent cache, rollback/recovery and monitoring must pass before production designation.

No brokerage execution, live actionable signal or order automation is authorized.
