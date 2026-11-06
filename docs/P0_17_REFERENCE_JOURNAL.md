# GĐ4/P0.17 — Local reference journal and opt-in provider-separated diagnostic cache

Date: 06/11/2026. Status: **ENGINEERING PROTOTYPE ONLY**. No service deployed, no approved storage volume, no licence/retention verification, no real-market historical backtest.

## Scope

Code: `src/swing_trading/reference_journal.py`; tests: `tests/test_reference_journal.py`.
Builds on the P0.15/P0.16 read-only SSI-first D1 reference adapters. Ingests a typed `BridgeRun` and its `D1ReferenceRequest` **after** the authorized host has obtained data. It does not call MCP, import credentials or schedule jobs.

- Local SQLite `ReferenceJournal`, caller-created at an explicit path **outside the repository**. Transactional `WAL` / `synchronous=FULL`, append-only metadata-journal triggers, SHA256-linked canonical receipt bodies and explicit optimistic `expected_tip`. Verify checks SQLite integrity, foreign keys, schema, chain and remaining cache provenance.
- Metadata journal records run identity, symbol/venue/date, declared as-of, route state, provider identities, endpoint, receipt state, actual UTC retrieval time and P0.16 ingestion SHA256 digest. It **does not persist raw MCP payloads or credentials**, nor infer provider-native revision/first-known IDs.
- By default, **no price/volume quote is persisted**. Cache insertion requires a separately supplied `ReferenceRetentionAuthorization` with explicit policy ID, both licence and secure-volume approval flags true, and expiry within 30 days of the source receipt. These flags are **caller assertions, not an independent authorization or evidence of legal entitlement**. Do not set them true until externally reviewed and approved.
- Optional `cache` table stores a per-run, provider-namespaced, minimal normalized diagnostic D1 quote. Exact run ID **and** provider must be specified to read it; no generic latest-quote lookup and **no use as an SSI/DNSE fallback**. The journal records its content digest, policy and expiry to detect cache corruption. Expired reference cache entries may be purged; journal metadata remains immutable. SQLite `secure_delete`, secure erasure of WAL/backups/SSD, encrypted storage and deletion of derived copies are **not independently validated**.
- Both append and read reject caller-as-of timestamps earlier than observed retrieval. Source receipt identity/date and selected quote must agree. Every returned `DiagnosticReference` is `PriceBasis.UNKNOWN` with `eligible_for_indicators=False`, `eligible_for_backtest=False` and `actionable=False`.
- A hash chain without externally pinned custody cannot withstand a privileged rewrite of the database plus its own hash chain. The P0.4C independent checkpoint contract is **not automatically integrated with this new journal**. A real backup/signature/restore process remains to be designed and validated for the journal.

## Tests and audit interpretation

Run `python -m unittest discover -s tests -v` under Python 3.11 and 3.12. P0.17 fixture tests cover metadata-only default, SSI/DNSE isolation, explicit retention and expiry, policy refusal, stale head/duplicate rollback, future receipt rejection, malformed cross-symbol receipt, blocked route, mutation trigger, tampered cache, and pruning without journal loss.

**Synthetic pass ≠ provider source approval, historical first-known proof, external custody, licensed data, accepted cache deployment or real trade backtest.** This scope introduces no quantitative B5 thresholds, no broker access and no GUI changes.

## Deployment gates still OPEN

1. Authorize and harden a persistent external directory (ACL, encryption, restricted users, monitored quotas, backup and restore). Do not put `.sqlite`, WAL or live-market payloads into GitHub/Google Drive without verified rights and encryption controls.
2. Review SSI/DNSE terms, reference quote retention, corporate-action adjustments and source-clock/first-known semantics; keep `ReferenceRetentionAuthorization` absent until approved.
3. Add independent journal checkpoint custody, verified backup restore and expiry/erasure controls for quotes and all copies. Test on the **actual selected host**, not merely GitHub Actions fixtures.
4. Design and approve the authenticated host MCP bridge. It must still inject authorized, read-only connectors; the Python package is not a running user-facing Plugin.
5. Resolve historical SSI intraday source gaps, native M1/M5/M15 and official market calendar, calibrate B5 SHORT/SWING and full cost/fill/settlement simulator before any historical BT/OOS or trading outputs.

UI-1.0 DESIGN_LOCKED. MOCHI deferred. CK 2.0, FX 2.0 and Scanner untouched. No orders or live signals.
