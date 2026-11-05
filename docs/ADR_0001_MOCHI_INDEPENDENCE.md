# ADR-0001 — MOCHI-independent operation and controlled Git sync

Status: APPROVED ARCHITECTURE GOAL; CLOUD RUNTIME NOT DEPLOYED (2026-11-06).

## Decision

- GitHub Private `ngluonghoa/swing-trading-1-8`: authoritative code, version history, CI.
- Google Drive: canonical handoff/specifications and approved data/evidence storage. Snapshot text in this repo is not automatic bi-directional sync.
- Execution priority is defined by [ADR-0002](ADR_0002_PYTHON_FIRST.md): ChatGPT Python for ad hoc work + GitHub Actions CI for repeatable tests. Google Colab is optional/on hold, never a mandatory dependency, CI gate, host, or persistent cache.
- MOCHI: optional working clone and secondary local document/code backup. **Defer** all MOCHI work until it is online and user requests it. No required runtime endpoint, credentials, tests or source dependencies may reside exclusively on MOCHI.
- A persistent cloud runtime/cache, if needed for scheduled/intraday plugin operation, will be selected and approved independently. There is **no** cloud production runtime at this time.

## Safe two-way Git development

1. MOCHI clone (only after availability confirmed): `/Users/mochi/git-clone/namtrai-works/swing-trading-1-8`.
2. New local changes: inspect status → branch → commit → push → CI/review.
3. New GitHub changes: fetch → inspect divergence → fast-forward pull only if clean.
4. Never automate `git push --force`, overwriting uncommitted files, or silent conflict resolution.
5. Document backup is **Drive → MOCHI** versioned one-way by design, with checksum and recovery drill. This does not imply mirroring destructive deletions.
6. No agent/CI job should treat MOCHI unavailability as an error for normal plugin operation.

## Acceptance gates (NOT_RUN)

- MOCHI fully powered off: code build and CI still work.
- CI and on-demand Python workflow require neither a Colab session nor a Colab token.
- Plugin live execution must work without MOCHI and without any Colab session when deployed.
- Cloud persistence, recovery, feed licensing, session clock, and security reviews pass before production designation.

**No brokerage integration, order placement, or automatic live signal execution is authorized.**
