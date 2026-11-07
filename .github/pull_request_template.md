## Scope and intent

- [ ] Exact module(s) and requirements/ADR references specified
- [ ] Source baseline SHA and target branch checked immediately before merge
- [ ] No changes to Forex/CK2/Scanner/MOCHI or locked Swing UI-1.0
- [ ] If a provider/storage/detector is added, replaced or removed: versioned port ID, scope, ABI, data semantics and affected cache dependencies reviewed

## Evidence and compatibility

- [ ] Consumer-driven positive, negative, wrong-provider, corrupt/unknown-version cases added or verified
- [ ] Semantic parity, first-known/as-of, adjustment/calendar/source correction policy checked where applicable
- [ ] Python 3.11/3.12 full suite and engineering-contracts/wheel CI links recorded
- [ ] Security, entitlement, data retention and external trust limits explicitly stated; synthetic-only tests never described as production
- [ ] R1–R7 impact and N/N−1 migration/restore plan documented, or clearly NOT_IMPLEMENTED
- [ ] No fabricated source grants, operational LKG, real trades, backtest ROI or automated production release claim

## Review / merge / handoff

- [ ] Code diff reviewed and CI success verified for exact PR head
- [ ] Only required files changed; no unwanted C3C restore
- [ ] Google Drive Master Handoff / Data Contract updated AFTER source merge if needed
- [ ] GitHub snapshots synced and exact text parity verified
- [ ] Postmerge main CI and rollback/backout plan reviewed

This checklist is a review aid, not technical branch protection. The private repository currently has no enforced protected-main rule.
