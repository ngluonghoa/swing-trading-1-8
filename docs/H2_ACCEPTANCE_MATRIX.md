# H2 — Acceptance matrix and safe handoff (08/11/2026)

**Scope:** Swing Trading 1.8 engineering modernization of existing code through C4B. No changes to Forex Trading, CK2, Scanner, MOCHI or UI v1.0. **Not** a real trading/data-provider release.

## Source-of-truth and commit chain

- Restore baseline after C3C rollback: PR #102 / main c02cc76f079d163b81d17f2a926c215893044ca6; canonical Handoff §27.64 / Cache §27 at that checkpoint.
- H1 foundation: source PR #103 and docs PR #104; main 5d343cfc903b9c34f8e897835238dfafdc378a49, Handoff §27.65 / Cache §28.
- H2-A source graph audit: [PR #105](https://github.com/ngluonghoa/swing-trading-1-8/pull/105), main a6d4c1af16226976b75c545ef4719932523dab6c.
- H2-B older module retrofit: [PR #106](https://github.com/ngluonghoa/swing-trading-1-8/pull/106), main 799d7324e2dc074f76f2ea9dacd12c4570daa301.
- H2-C cache semantic parity: [PR #107](https://github.com/ngluonghoa/swing-trading-1-8/pull/107), main d1c25ff8d88e98c80138a3c0e58eeaa79ccf6825.
- H2-D whole-tree QA: [PR #108](https://github.com/ngluonghoa/swing-trading-1-8/pull/108), main 725f2833d1376039666848ef8c821ce1038a2773; [postmerge main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42403127427) SUCCESS. 1,305 unittest PASS **per** Python version (3.11, 3.12), not the two jobs summed. H2-E docs-only sync is this follow-on PR.

## Acceptance status

| Requirement | Engineering result | Verified limitation |
| --- | --- | --- |
| Audit every old Python module, ownership and imports | PASS: full AST inventory v2 of 63 source modules, 63 test files | Static introspection, NOT code-path coverage |
| Detect cycles and invalid domain dependencies | PASS: zero reported cycles/forbidden core imports | Other indirect runtime coupling still needs integration profiling |
| Reject withdrawn C3C | PASS: audit denies old C3C files; rollback baseline preserved | Git history contains retained old PRs for evidence only |
| Port contracts for existing source | PASS: typed SSI/DNSE D1 factory; per-provider endpoint and SemVer | Legacy callable constructor retained, real source/license not certified |
| Existing Backtest core injection | PASS: typed synthetic-only factory and causal negative tests | No detector calibration, real-fill backtest or OOS |
| Existing C3B and C4A replacement surface | PASS: common read-only fixture ABI; old serializers/schema unchanged | No real persistent cloud writer, CAS, witness or production migration |
| Cache semantic compatibility | PASS: source revision, first-known, pinned head, SHA, full EMA20/ATR14 parity; fail-closed on mismatch | Synthetic offline 15-bar fixtures, not vendor source assurance |
| Consumer-driven regression | PASS: +55 H2 tests versus H1, full 1,305 suite each Python 3.11/3.12 | No claim of 100% dynamic line/branch/mutation coverage |
| Version/release review | PARTIAL: SHA identity, PRs, changelog and docs mirrors | No signed release, tag, LKG, branch protection, package lock or live rollback |
| Full source quality CI | PASS for whole-tree correctness lint E9/F821/F822/F823, strict touched H1/H2 files lint, wheel check and dependency consistency | Not complete strict typing, supply chain/SBOM/security scanning |
| Canonical Handoff/docs parity | ACCEPT only after separate docs PR and exact main sync | Docs initially ahead of GitHub between native edit and PR merge |
| Data rights/real indicators | BLOCKED: P0.29c, C2C and market/calendar rights remain external | H2 does not grant rights, approve real cache, order or trading |

## What H2 did NOT silently change

No modification to C3B/C4A content-addressed blob semantics, sqlite schema, prior synthetic indicator calculations, C4B VN execution constraints, default source selection, UI-1.0, 16 zone IDs, strategy horizons, eight-step audit requirements, Forex Trading, CK2, Scanner, MOCHI, revoked C3C or trade-related accounts.

Only four **pre-existing** source modules were directly retrofitted in H2-B (d1_mcp_transport_bridge.py, backtest.py, partition_chunk_cache.py, segmented_cache.py). All other existing modules were audited and exercised by the broader test suite, not individually refactored. The user-approved standard is selective modernization with no speculative rewrites. Areas still incomplete must remain OPEN rather than labelled standardized-production.

## Rollback and next

- Revert H2-D, then H2-C, then H2-B, then H2-A through individual reviewed PRs if needed. Preserve Git history; never force reset main. No database migrations or licensed cache writes were introduced.
- Re-run CI and verify native Google Docs and GitHub snapshots after any accepted rollback.
- Continue with a NEW C3C synthetic connector file byte readback milestone, starting from the safely restored post-C4B lineage plus H1/H2 engineering tooling, not reviving old C3C PR #100/#101.
- Production release remains blocked by source rights, security, independent current issuer/revocation evidence, real source parity, operational LKG, real backtest/OOS and settlement governance.
