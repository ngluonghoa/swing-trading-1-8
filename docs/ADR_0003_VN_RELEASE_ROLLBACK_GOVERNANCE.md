# ADR-0003 — Vietnam cash-equity release profiles, R1–R7 rollback and safe recovery

**Date:** 2026-11-07. **Decision:** ADOPTED_DESIGN_POLICY; PARTIAL_OFFLINE_PREFLIGHT_IMPLEMENTED; NO operational release/rollback. **Scope:** Swing Trading 1.8 only. **Baseline:** GitHub `main` commit `0e9d1e97ea0bf3e652af6c9eb8d4fcbe6df48892` (GĐ4/P0.28, canonical Drive Handoff §27.52). New work MUST NOT merge or reuse the discarded ChatGPT Work P0.29–F1 branches. GĐ4/P0.29 source-rights provenance remains a separate open workstream.

## 1. Purpose and safety boundary

Match Forex Trading 1.0's *governance standard* (seven rollback layers, immutable whole-system profiles, approval-gated last-known-good, compatibility matrix, runbook and negative acceptance tests), but **not** its currency-market assumptions or broker execution. This decision is written independently for **Vietnamese cash equities** and does not import Forex source or the discarded Swing P0.29–F1 work. It does not mean all mechanisms are implemented.

Existing design invariants: SHORT means a 3–10 trading-session **holding horizon**, **not** the ability to short-sell; SWING is a 10–60-session horizon. Keep B1–B8/S1–S8, eight audit steps, four buy and sell states, UI v1.0 `DESIGN_LOCKED`, and the SSI-first/DNSE-reference-only restriction. Never deploy or place broker orders without separate approval. This ADR does not change CK 2.0, FX 2.0, Scanner or MOCHI.

**Source of truth:** Google Drive Master Spec/Handoff; GitHub `main` source/CI. A GH code rollback must not silently rewrite Drive document revision history. `docs/source-snapshots/` are point-in-time mirrors that require explicit exact comparisons after syncing.

## 2. Full Execution Profile: change identity, not proof of authority

A candidate/release is specified by immutable typed IDs and SHA/fingerprints for:

1. **R1 code:** exact Git SHA, dependency lock/build identity and reproducibility environment.
2. **R2 rules/parameters:** SHORT or SWING horizon, detector catalog/predicates (B1–B8/S1–S8), indicator version, calibrated parameter-set hashes, risk policy and applicability.
3. **R3 licensed market input:** SSI or DNSE separate namespace, actual API product/entitlement/version, source revision and as-of first-known timestamp, raw/adjusted price basis, corporate action/relisting lineage and calendar evidence. Never combine SSI/DNSE bars into one indistinguishable history.
4. **R4 persistence:** raw/derived event schema, journal and checkpoint versions, provider-specific cache keys and provenance, dependency graph and invalidation recipe, approved legal retention/deletion rules.
5. **R5 reporting:** versioned output DTO/report renderer while retaining the **unchanged locked UI v1.0 design**. UI rollback cannot rewrite signals or risk outputs.
6. **R6 Vietnam settlement, account/risk and execution simulator:** venue/session/order constraints; independently verified account holdings, broker sellable/free balance versus T+2 pending/pledged/restricted; fill and liquidity/limit-up/down assumptions, costs/fees/tax/slippage, cash/settlement schedule and time-in-force/order-event semantics. Underlying system is advisory-only until independently authorized.
7. **R7 research, audit, release/docs:** experiment ID, frozen train/validation/untouched OOS, seed and assumptions, eight-step audit version, tagged release identity, Handoff/doc revision and operator/approval receipts.

An individual `FullExecutionProfile` fingerprint identifies a **claimed** exact configuration; it does not confer data rights, certify a vendor, sign a release, establish LKG or grant broker trading authority. Approved LKG requires a separate externally reviewable, immutable signed/controlled release manifest, successful compatible restore evidence, source rights, real historical BT/OOS and operator approval. **Current LKG: NONE.** Never turn a Git SHA or self-entered boolean into an LKG.

## 3. R1–R7 rollback matrix (cash equities)

| Layer | Scope and required safeguard | Real-system status |
| --- | --- | --- |
| **R1 CODE** | Revert to previously approved reproducible code/dependencies via PR; do not force-push or silently rewrite `main`. Confirm contracts/data-reader compatibility. | Git history/PR/CI exist; LKG release mechanism NOT_IMPLEMENTED. |
| **R2 RULE/PARAM** | Restore only compatible SHORT/SWING predicates, indicator manifest/parameter hashes and feature flags; invalidate affected indicator and signal cache. Confirm no final OOS tuning. | Fingerprint/diff/read-only preview coded; atomic activation NOT_IMPLEMENTED. |
| **R3 SOURCE/DATA** | Restore independently entitled SSI/DNSE adapter, as-of revision and approved adjustment basis; preserve append-only corrections, raw first-known provenance and trading-calendar mapping. Missing rights => `UNVERIFIED`, no replay/order. | Source licence and operational rollback BLOCKED. |
| **R4 SCHEMA/CACHE** | N/N−1 expand/migrate/contract compatibility; read-only preflight; rebuild derived cache, preserve raw/versioned lineage only where licensed; never overwrite corrupt history to look correct. | Existing synthetic SQLite/journal metadata backup/restore prototypes; production cache restore NOT_DEPLOYED. |
| **R5 UI/REPORT** | Restore compatible renderer/report DTO without modifying locked UI v1.0 or canonical signal outputs. | Design + offline report contract difference only; renderer NOT_IMPLEMENTED. |
| **R6 VN ACCOUNT/POSITION** | Freeze new actionable intents; reconcile broker-confirmed free-to-sell, pending T+2, unsettled cash, restrictions, corporate actions, outstanding orders and protective instructions. Software cannot undo fills or dividends. DO NOT infer short-selling from SHORT horizon. | Caller-supplied preview checks only; NO broker order/position adapter or operational rollback. |
| **R7 DOCUMENT/RELEASE** | Retain incident and bad candidate for audit; version pointers/Handoff/Spec, signed release receipt and immutable experiment evidence; revert active pointer only with verified approvals. | Git/Drive history available; release pointer/custodian NOT_DEPLOYED. |

Layer scope is explicit. A request to roll back only R2 is blocked if source or schema changed without declared compatible handling; R5 never silently rolls back R2. If rights, LKG, backup integrity, app N−1/DB N compatibility, broker inventory or venue/session facts cannot be independently verified, **fail closed to SAFE_MODE** (analysis-only; no actionable BUY/SELL and no orders). A technical failure does not authorize panic cancellation of valid broker protection.

## 4. Vietnam-specific market invariants

- **Venue:** HOSE, HNX, UPCoM have different price bands, reference-price bases, auction/continuous/negotiated sessions, order types, lot and tick rules; exceptional listing, resume-from-suspension and ex-rights days have different bands. Store **versioned venue + instrument + trading-session + corporate-action rule snapshots** and validate the proposed order price. **Never hardcode normal ±7%/±10%/±15% as universally valid.** Market clock is `Asia/Ho_Chi_Minh`, but receipt/first-known timestamps are immutable UTC.
- **T+2:** source/broker confirmation of credited, freely sellable securities determines whether a hypothetical sell is executable, not the calculation that two business days elapsed; settlement holidays, late credit and broker state may differ. `pending_t2_qty`, pledged/restricted shares, partially filled orders and corporate actions are separate buckets. Do not silently add pending shares to sellable or equate sale proceeds with settled spendable cash.
- **Exposure:** the initial release scope is cash equities. A SELL zone can be an analytical exit/warning without a sellable holding; SHORT is a time horizon, never a short-sale or derivatives order. No borrowing/margin or broker trading without explicit extension, approval and audited adapter.
- **Liquidity/fills:** distinguish intraday LO/ATO/ATC/UPCoM matching constraints, ceiling/floor lock, order-book volume, odd lots, partial fills, slippage, trade/sell tax and brokerage fees. Historical OHLC-only bars do NOT establish an executable fill or availability at a limit price. Use legally licensed first-known bid/ask/order-book data if required by the future simulator; otherwise label fills ambiguous/unverified.
- **Ex-rights:** cash/stock dividends, splits, rights issues, relisting, symbol transfer and adjusted/unadjusted price records must remain versioned. Never conflate adjusted signals with tradeable raw historical prices.
- **Data:** SSI primary, DNSE independent reference/fallback **for approved D1 reference only** until real rights and venue parity are independently qualified. An unauthorised cache must not be “restored” from backup, and metadata-only journal snapshots must not revive OHLCV bytes.

External indicative references (not automatic authority for a specific session/account): [SSI cash equity rules](https://www.ssi.com.vn/khach-hang-ca-nhan/quy-dinh-giao-dich/quy-dinh-giao-dich-co-phieu), [FPTS settlement](https://www.fpts.com.vn/customer-service/securities-trading/securities-trading-settlement/), [VNDIRECT HOSE sessions](https://support.vndirect.com.vn/hc/en-us/articles/360002192174-Trading-regulations-at-HSX-Ho-Chi-Minh-Stock-Exchange). Exchange/VSDC source version, account broker evidence, current special rulings and effective dates must still be checked for **each** real release.

## 5. Compatibility matrix, performance gate and LKG

Record checks over `(code/build, rules/parameters, source rights/adjustments, calendar, corporate actions, venue rules, settlement/T+2, cost/fill, schema/cache, audit/renderer, broker-position protocol, document/release pointer)` with states `COMPATIBLE / MIGRATE_AND_REBUILD / HOLD_UNVERIFIED / INCOMPATIBLE`. Every profile delta must be assigned to one or more R1–R7 layers; missing scope is a hard hold. A migration is not marked safe by an arbitrary user-supplied boolean; produce immutable test/evidence IDs and independent signoff.

**Release gate:** `DESIGN_APPROVED -> CODE_IMPLEMENTED -> CI_PASS -> SOURCE_RIGHTS_VERIFIED -> CAUSAL_DATA_QUALIFIED -> REAL_HISTORICAL_BACKTEST -> UNTOUCHED_OOS/WALK_FORWARD -> (APPROVED SHADOW/PAPER) -> RELEASE_APPROVED -> ACTIVATED`. Guardrails and acceptable degradation bounds must be approved **before** evaluation. Paired old/new experiments pin same investable universe, instrument status, venue regime, as-known data/adjustment clock, T+2 settlement, costs/taxes/slippage, liquidity and stop execution. Compare after-cost expectancy, drawdown, false/early alerts, opportunity missed, turnover, cash/position locks, partial/unfilled orders and scenario uncertainty. A synthetic CI pass is **not** market backtest or approval.

Profiles retain `ACTIVE_PROFILE_ID`, `CANDIDATE_PROFILE_ID`, and `LAST_KNOWN_GOOD_PROFILE_ID` only once a real approved release-control system exists. **All three runtime pointers are currently NOT_DEPLOYED.** Never populate LKG from a branch name alone. A worse candidate stays inactive. Once activated in an approved future runtime, violations trigger controlled rollback or SAFE_MODE; never silently tune a final untouched holdout.

## 6. Seven-step recovery runbook

1. **RB-01 Observe and freeze:** record incident timestamp, affected symbol/venue/horizon, active/candidate fingerprints, failure and data-quality state. Freeze candidate promotion and any *future* new-order intents; retain protective broker instructions.
2. **RB-02 Verify LKG:** query a separately protected, independently approved and immutable **full profile**, its release signature/checkpoint and restore evidence. Missing => `ROLLBACK_BLOCKED_NO_APPROVED_LKG`, SAFE_MODE.
3. **RB-03 Preflight:** verify rights/licence, source revision/freshness, N/N−1 schema/cache and backups, venue calendar/exceptional price bands, symbol state, split/rights, broker-confirmed settled sellable quantity, outstanding orders and costs. Missing/unsafe => SAFE_MODE.
4. **RB-04 Execute approved scope:** after explicit operator authorization, restore only approved R1–R7 layers/whole profile using authenticated release-control infrastructure. Never force-reset `main`; no re-play of trade orders or blind close/cancel.
5. **RB-05 Rebuild & regress:** invalidate affected indicator/signal cache; run first-known causality, provider isolation, M5/M15/D1/W1, T+2/corporate-action, ceiling/floor, partial/ambiguous-fill, 16 zone and eight-audit smoke/negative tests.
6. **RB-06 Verify restored state:** read live release selector/config, journal/source revisions and separate broker/position/order state independently; compare observed manifest/hash and health/strategy metrics. Only mark PASS after actual evidence.
7. **RB-07 Archive and reconcile:** preserve failing version, root cause, after-cost comparison, rollback receipt, authorization, source-rights effects and Handoff/doc revisions. Do not erase bad experiments.

## 7. Implementation receipt and exclusions

This ADR introduces an **offline preflight slice only** in `src/swing_trading/vn_release_rollback.py`: immutable profile SHA256 identity, 7-layer delta detection, requested-scope diagnostics, indicator/cache invalidation flag and conservative venue/account/T+2/price/adjustment rejection. `RollbackPreflight` is deliberately always `SAFE_MODE_ONLY`, with `can_activate=False` and `can_place_orders=False`. The user/caller-supplied `broker_settlement_confirmation` and `exceptional_rule_reviewed` are NOT independently attested; they only allow structural validation, not approval. Tests are synthetic fixtures in `tests/test_vn_release_rollback.py`, **not** FX-style release/restore/live tests.

**Not delivered:** LKG signer/registry, protected active-pointer switch, reliable broker balance/positions, database/cache migration, active quote retention, independent price-band/calendar evidence, funded trading, approved licensed historical replay, real backtest/OOS, operational runbook rehearsal, RPO/RTO or full seven-layer executable rollback. Subsequent small PRs must separately close each gate with negative tests and full source-quality authorization. Do not alter the GĐ4/P0.29 independent source-rights trust-head milestone, even if this parallel governance track is delivered first.
