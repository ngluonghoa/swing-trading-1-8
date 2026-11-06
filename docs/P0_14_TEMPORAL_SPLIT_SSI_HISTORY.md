# GĐ4/P0.14 — SSI historical availability gaps and B5 temporal split leakage audit

Date: **06/11/2026** (Asia/Ho_Chi_Minh). Scope: **READ-ONLY SSI OBSERVATIONS + SYNTHETIC SPLIT AUDIT; NO HISTORICAL BACKTEST / NO TRADING**.
Authority: native Master Handoff §27.37; 01 MASTER_SPEC §24.14.3–.5 (BT-10/BT-11, chronological OOS, purge/embargo, untouched holdout), 05 DATA CONTRACT §§2/17–18, P0.12–P0.13 SSI diagnostics and B5 calibration grid.
Code: `src/swing_trading/ssi_historical_availability.py`, `src/swing_trading/b5_temporal_split_audit.py`.
Tests: `tests/test_ssi_historical_availability.py`, `tests/test_b5_temporal_split_audit.py`.

## A. SSI historical intraday versus daily: real read-only checks

SSI public MCP documentation [Resource/time-range caps](https://mcp.ssi.com.vn/docs/tai-nguyen/) explicitly says **request `toDate` is DD/MM/YYYY** with at most 730 days of allowed query history; that **does NOT promise 730 days of intraday retention or full returns**. SSI tool `marketdata_list_intraday_stock_infor` advertises response `trading_date` as MM/dd/yyyy, whereas prior observable `13/10/2026`, `14/10/2026` and new `16/10/2026` strings are unambiguously day-first. Formal **response-field timestamp layout/version** remains unresolved; do not silently convert ambiguous `02/11` or `11/02` without qualifying source semantics.

On 06/11/2026, read-only SHS/HNX queries used the **non-paged** `marketdata_list_intraday_stock_infor(symbol=SHS, range=1d, toDate)` and detailed daily `marketdata_list_daily_stock_infor(...,pageSize=4 or 5,pageIndex=1)`. The daily row was selected for the exact requested `trading_date`.

| Requested date (DD/MM/YYYY) | Intraday status/rows | Intraday sum | Daily `total_match_volume` | Classification |
| --- | --- | ---: | ---: | --- |
| 02/11/2026 | `ok`, 234 | 13,095,000 | 13,095,000 | EQUAL, SOURCE UNCERTIFIED |
| 11/02/2026 | `ok`, 0 | **N/A** | 7,871,600 | INTRADAY EMPTY, DAILY TRADES EXIST |
| 13/04/2026 | `ok`, 0 | **N/A** | 24,550,600 | INTRADAY EMPTY, DAILY TRADES EXIST |
| 01/07/2026 | `ok`, 0 | **N/A** | 7,136,100 | INTRADAY EMPTY, DAILY TRADES EXIST |
| 14/08/2026 | `ok`, 0 | **N/A** | 20,060,800 | INTRADAY EMPTY, DAILY TRADES EXIST |
| 01/10/2026 | `ok`, 0 | **N/A** | 9,839,500 | INTRADAY EMPTY, DAILY TRADES EXIST |

Additional SHS/HNX `16/10/2026` intraday retrieved `ok`, 233 rows and sum 11,621,600; **no detailed daily cross-check was requested for that day**, so it is not counted as a matching daily comparison.

**Key fact:** SSI detailed DAILY recorded matched trading volume on five historical dates on which the **tested intraday endpoint returned zero rows**. Thus `empty intraday != no trades` and `empty != verified zero volume`. These rows are not a proven data deletion, precise retention-window boundary, error from all SSI endpoints, breach of licensing or proof of unavailable archival exports; this is an unresolved **endpoint-specific historical retrieval/coverage gap**. The full/paged raw-price `marketdata_list_stock_infor` was previously observed `DOWNSTREAM_UNAVAILABLE` in P0.12, **not retested here**. P0.12/13's 10/10 matched sample totals remain valid for their *specified accessible dates*, not a guarantee for other days.

### P0.14 typed availability classifier

`review_ssi_historical_day()` uses the P0.12 typed intraday/daily receipts and a real as-of UTC. For nonempty ticks it reruns P0.12 timestamp/identity/volume parity; for empty ticks with **daily `total_match_volume>0`** it returns `INTRADAY_EMPTY_DAILY_TRADES_UNCERTIFIED` (intraday_total=NULL, never 0). If both are empty/0 it blocks rather than concluding a valid closed exchange day. It rejects source observations fetched after the audit clock and mismatched symbol/venue/date. It never emits a source approval or claims the retention cutoff.

Possible states: `NONEMPTY_MATCHED_UNCERTIFIED`, `INTRADAY_EMPTY_DAILY_TRADES_UNCERTIFIED`, `BLOCKED`. All evidence certification, complete native M1, provider timestamp, licence, retention and actionable flags **False**. No conversion to fully source-qualified v1.2 bars or B5 detector inputs.

## B. Separate B5 SHORT/SWING temporal split and leakage audit

The canonical Backtest design already requires chronology, **purging/embargo for overlapping labels**, independent train/validation/untouched holdout and strict `first_known_time`. P0.13 preregistered a 24-slot B5 parameter grid, **all numeric cells still None**. P0.14 adds an **audit-only candidate temporal split**; it does not freeze actual date windows, approve a holding horizon, fit thresholds, run a simulator or open holdout performance.

`B5SplitCandidate` specifies exactly one Strategy SHORT or SWING and explicit B5/E_RECLAIM or B5/E_FAILED_BREAK, source manifest `D1SessionInventory`, source snapshot ID, label policy version, three half-open integer session-index ranges in chronological TRAIN/VALIDATION/HOLDOUT order, a caller-supplied `embargo_sessions` and a caller-supplied `max_observed_label_span_sessions`. **These are experiment-design inputs, not approved trading thresholds.** No default train/validation/holdout ratios or calculated weekdays-as-official-sessions are imposed. The manifest itself remains `independently_certified=False`.

`B5LabelFootprint` carries a unique event ID, explicit strategy/variant, signal decision session, label-end session, `first_known_time_utc` for signal features, `label_first_known_utc` for after-event outcome and source/label-policy revisions. This is *only* a time footprint—no trade return or holdout metric is exposed.

`audit_b5_temporal_split(plan, footprints, as_of_utc)`:

- Verifies fold order, half-open bounds, **required explicit embargo gap** between scoring windows, source-manifest first-known time and valid UTC.
- Checks stable event IDs, temporal ordering and correct strategy, B5 variant, label policy, source session IDs and recorded horizon; refuses any event scored inside embargo gaps or outside a scoring fold.
- Requires signal feature first-known no later than its decision session close; label first-known cannot precede the label horizon's close, and neither feature nor label may be discovered after the audit clock.
- **Audits label overlaps at train→validation and validation→holdout boundaries**. If a train label extends into validation, or a validation label into holdout, it **blocks** and names the violating event. It does **not** silently delete/purge the event; the experiment author must change the data selection/plan and rerun audits. The holdout label cannot extend past its own declared window.
- Requires observed events in each fold for a candidate structural pass. Exact test counts and policy requirements are **synthetic engineering** only; insufficient source/sample evidence remains OPEN.

A passing outcome is **`STRUCTURALLY_SEPARATED_UNCERTIFIED`**, NEVER SOURCE_VERIFIED, HOLDOUT_FROZEN or HISTORICAL_BACKTEST_RUN. The review reports only counts and violation reasons, with `trading_calendar_certified=False`, `source_licence_verified=False`, `holdout_unsealed=False`, `threshold_approved=False`, `historical_backtest_run=False`, `actionable=False`. A synthetic split can be structurally valid while the actual trading calendar, label-policy horizons, market universe, survivorship exclusions or rights remain unverified.

No numeric split or embargo from these tests may be extrapolated to a production approved SHORT 3–10 or SWING 10–60-day label policy. Real purge/embargo values and train/validation/OOS boundaries require an independently approved, versioned experiment design.

## C. Acceptance and unresolved gates

P0.14 adds **30 synthetic tests**: historical empty-vs-positive-day case classification, nonempty parity, absent daily and clocks; split fold ordering, insufficient embargo, train/validation label leakage, holdout boundary, wrong strategy/variant/label-policy, retroactive signal features, labels known before horizon or after audit clock, duplicate/out-of-order IDs, and no-approval invariants.

This is not BT-10 or BT-11's official passed backtest acceptance: actual dated/approved splits, source-certified first-known history, target label construction, holdout sealing and executable detectors have not been run. Overall SSI B01–B08 remain OPEN; P0.14 adds real negative evidence for the historical intraday availability gate without claiming a specific root cause.

### Next

1. Request independent provider confirmation of SSI **response** timestamp layout and effective historical intraday coverage/retention and licensed bulk/raw feed, and verify an official session calendar for HOSE/HNX/UPCOM.
2. Extend read-only date/symbol coverage carefully with provider-specific native first-known/revision/event IDs and session/auction semantics, avoid silently treating empty dates as no-trade days.
3. Agree on explicit separate SHORT/SWING label definitions, actual session-calendar-aware horizon, universe, freeze dates, purge/embargo rules and candidate ranges. Until approved, P0.13's numeric parameter slots remain **None**.
4. Only after qualified source + executable tested B5 detector + realistic fill/slippage/fees/tax/T+2 simulator may actual historical BT-01..16, walk-forward/OOS and performance claims begin.

No changes to UI-1.0, CK 2.0, FX 2.0, Scanner, MOCHI or brokerage orders.
