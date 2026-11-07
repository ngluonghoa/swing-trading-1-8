# VN cash-equity rollback acceptance matrix (R1–R7)

**State:** `DESIGN_AND_OFFLINE_PREFLIGHT_PARTIAL`. None of the full operational acceptance tests have run; no LKG or order authority exists. Synthetic test evidence is explicitly separate.

| ID | Required future acceptance (independent evidence) | Status |
| --- | --- | --- |
| VN-RB-01 | Restore exact signed/hash-pinned CODE plus dependency locks through approved release-control, not force-push main | NOT_RUN |
| VN-RB-02 | R2 rollback restores detector/indicator/parameter versions together; invalidates only affected cache and preserves signal causality | OFFLINE_PREVIEW_ONLY |
| VN-RB-03 | Provider rights expiry/revocation or SSI→DNSE revision change forces source requalification and no unlicensed cache/data resurrection | OFFLINE_PREVIEW_ONLY |
| VN-RB-04 | N/N−1 DB/event schema migration plus independently pinned backup restore and corruption/host failure | NOT_RUN |
| VN-RB-05 | R5 report renderer rollback leaves locked UI v1.0 and canonical B/S decisions unchanged | OFFLINE_PREVIEW_ONLY |
| VN-RB-06 | Broker inventory with 500 pending T+2 and only 50 sellable forbids proposed sell of 100 | SYNTHETIC_PREVIEW_PASS |
| VN-RB-07 | Broker unconfirmed settlement or symbol mismatch blocks any implied sellability | SYNTHETIC_PREVIEW_PASS |
| VN-RB-08 | Cash/stock dividends and shares-on-hold are reconciled before simulation of exit and sell availability | SYNTHETIC_PREVIEW_PASS |
| VN-RB-09 | HOSE/HNX/UPCoM per-session floor/ceiling and tick, including special-band and ex-rights sessions, verified against official source | OFFLINE_PREVIEW_ONLY |
| VN-RB-10 | No rollback converts SHORT horizon to short sale, CFDs or derivatives without separate explicit authorization | SYNTHETIC_PREVIEW_PASS |
| VN-RB-11 | Real fill model handles auction orders, floor/ceiling locks, nonfill, partial execution, fees, tax, T+2 cash/stock | NOT_RUN |
| VN-RB-12 | Restored profile is compared against independently approved LKG and complete profile hash with owner signoff | NOT_RUN |
| VN-RB-13 | Unknown trusted custodian, mismatched source/provenance, or incompatible layer change => SAFE_MODE, no order | OFFLINE_PREVIEW_ONLY |
| VN-RB-14 | Negative after-cost OOS and walk-forward performance blocks candidate promotion using preregistered guardrails | NOT_RUN |
| VN-RB-15 | Incident receipt preserves bad candidate, Handoff revision, source rights, rollback evidence and no fabricated PASS | NOT_RUN |
| VN-RB-16 | Rehearse complete R1–R7 recovery on approved durable host and assert actual restored system health without touching broker | NOT_RUN |

The `SYNTHETIC_PREVIEW_PASS` label means unit tests exercised only supplied artificial records, not independent broker/VSDC/exchange proof. `OFFLINE_PREVIEW_ONLY` means some invariants were coded but complete recovery was not. Formal acceptance remains `NOT_RUN` until end-to-end evidence is captured for each requirement.

## Change and evidence contract

For each next PR require: `REQ-VN-RB`/test IDs, base and branch SHAs, failure/negative fixture, impact by R layer, compatibility summary, source-rights review, reviewed code diff, Python 3.11/3.12 PR CI logs, optional merge/main CI, Drive Handoff note, and actual runbook result. Do not assert a reviewer other than the committer unless independently verified. Never merge work from the six discarded ChatGPT Work branches.
