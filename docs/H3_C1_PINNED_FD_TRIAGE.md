# H3-C1 — Pinned-FD high-risk manual triage and exception-boundary freeze (08/11/2026)

**Scope:** from `main` 1af7cb8b15431a5cd3e52cb6c775d431d0da9674, isolated offline engineering regression work. This is the **first H3-C slice**, not approval of all 63 modules, a production host, a Google Drive adapter, or source rights. H3-A/H3-B, H1/H2, and §27.67/Smart Cache §30 remain the canonical prior checkpoints.

## Actual manual findings — `reference_pinned_fd.py`

- The static H3 matrix flags this module as `IMPROVE` due to branch score 23 and `SILENT_EXCEPT`. The two `except FileNotFoundError: pass` sites in `PinnedReferenceInspection.verify_path_names` are **intentional narrow absence checks** for the three previously absent SQLite sidecar filenames and the `.git` marker. Removing them without changing semantics would reject a healthy private SQLite fixture. They are not blanket error suppression.
- Unexpected `PermissionError`/`EIO` on an absent-sidecar probe or repository-marker probe propagates and prevents a successful validation. Unavailability of an already pinned DB/dir/file is wrapped as `UnsafeReferenceStorage`. An unexpected failure to open a sidecar during initial pinning is also wrapped fail-closed. These are now explicitly guarded by new deterministic negative tests rather than asserted from heuristic code review alone.
- Sidecars appearing as **symlinks** for each of `-wal`, `-shm`, `-journal`, new `.git` marker after pin, and closed descriptor lifetime are frozen with regression tests. A successful local inspection always has `production_authorized=False`.
- `verify_path_names()` detects pathname/inode swaps, **not** all subsequent mode/UID/hardlink changes after initial `_owner_mode()`; `sqlite3.connect(path)` may independently reopen the DB/sidecars. These remain explicit host/runtime/TOCTOU gaps for subsequent security review. No code permission check was weakened or capability promoted.

**Provisional manual disposition:** KEEP the narrow `FileNotFoundError` semantics; mark pinned-FD component **MANUAL_TRIAGED_WITH_OPEN_HOST_RISKS**, not fully accepted for production. Do not refactor the verified exception branches merely to improve a heuristic score. A later H3-C2 may evaluate revalidation of owner/mode/link count, FD lifetime and concurrency; freeze new behavior first and maintain source/fixture parity.

## Parallel risk inventory (not refactored or signed off)

- `b5_phase_contract.py`: high branch/method complexity; receipt/source-revision/first-known causal ordering, R_C/R_E/R_F and STRICT hard-false detector approval must be preserved. Existing `tests/test_b5_phase_contract.py` has synthetic conflict/timeframe/holdout guards. Review and freeze more golden output before any helper extraction.
- `b5_temporal_split_audit.py`: TRAIN/VALIDATION/HOLDOUT embargo and label leakage checks are synthetic-only; test fixture's calendar is not authoritative. No approval of OOS, label policy, or trade readiness.
- `provider_review_packet.py` and signed-head/revocation modules: caller-claimed roles and source-rights remain **untrusted**. All read/cache/backtest/production authorizations hard FALSE. Refactor only after consumer graph, negative cases and rollback review.

## Evidence, acceptance and rollback

- New `tests/test_h3_pinned_fd_guard_regression.py` adds **9** unittest methods; coverage includes EACCES/EIO, symlink appearance, marker creation, FD closure and permission denial at open. Current existing P0.20 tests remain and must pass.
- CI matrix on Python 3.11/3.12 must pass the entire engineering suite, full tree correctness lint, strict lint for this new test, H3 exact generated matrix, package build and wheel isolation. **Do not claim PASS before Actions evidence.** This PR intentionally leaves all 63 source modules unmodified; generated 31 KEEP / 32 IMPROVE classification remains provisional and unchanged.
- Revert this isolated PR to remove only regression tests, the H3-C1 record and corresponding lint inclusion. No SQLite changes, cache bytes/schema/EMA/ATR math, source connector, license, synthetic staging restoration or UI modification.
- C3C remains postponed while H3-C/D/E module-level review and real external source-rights gates remain OPEN. No changes to Forex, CK2, Scanner, MOCHI or any credentials.
