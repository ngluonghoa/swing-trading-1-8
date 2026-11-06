# GĐ4/P0.12 — Read-only SSI intraday ↔ daily matched-volume parity

Date: 2026-11-06. **PARTIAL REAL-SOURCE DIAGNOSTIC + SYNTHETIC ENGINEERING TESTS. NOT SOURCE-CERTIFIED / NONACTIONABLE.**
Authority: native Master Handoff §27.35, 05 Data Contract §§2/17–18, official exchange closure anchors from P0.11.
Implementation: `src/swing_trading/ssi_volume_parity.py`; `tests/test_ssi_volume_parity.py`.

## Read-only SSI connector audit on 06/11/2026

Two SSI intraday endpoints were checked for SHS, HNX; they behaved **differently**.

| Endpoint / date | Connector result | Relevant evidence |
| --- | --- | --- |
| `marketdata_list_stock_infor` 13/10/2026 | ERROR `DOWNSTREAM_UNAVAILABLE` | At provider UTC `2026-11-06T08:57:58.5220621+00:00`; full/paged raw-price intraday stream is STILL NOT available in the checked call |
| `marketdata_list_intraday_stock_infor` 13/10/2026 | `ok` | 215 rows; all rows reported local date 13/10/2026, unique timestamp strings; earliest 09:00, latest 14:45; sum of reported volumes **5,177,600** |
| `marketdata_list_intraday_stock_infor` 12/10/2026 | `ok` | 233 rows; earliest 09:00, latest 14:45; sum **4,050,300** |
| `marketdata_list_intraday_stock_infor` 14/10/2026 | `ok` | 223 rows; earliest 09:00, latest 14:45; sum **10,160,800** |
| `marketdata_list_intraday_stock_infor` 01/09/2026 | `ok`, empty `ticks` | 01/09 was a published 2026 exchange closure; an empty successful response alone is neither source outage nor proof of completeness |
| `marketdata_list_daily_stock_infor` 12/13/14 Oct 2026 | `ok` | Daily `total_match_volume` 4,050,300 / 5,177,600 / 10,160,800 respectively; same-day `volume` also matched those totals in sample |
| `marketdata_list_stock_daily_data` 13 Oct 2026 | `ok` | Compact daily SHS OHLCV supports 13 October total 5,177,600 |

**Parity on three isolated SHS dates:**

| Date | Count of intraday rows | Sum of `ticks[].volume` | Daily `total_match_volume` | Read-only comparison |
| --- | ---: | ---: | ---: | --- |
| 12/10/2026 | 233 | 4,050,300 | 4,050,300 | EQUAL, UNCERTIFIED |
| 13/10/2026 | 215 | 5,177,600 | 5,177,600 | EQUAL, UNCERTIFIED |
| 14/10/2026 | 223 | 10,160,800 | 10,160,800 | EQUAL, UNCERTIFIED |

The `ticks[].trading_date` strings contained examples `13/10/2026 14:45:00` and `13/10/2026 09:00:00`, which cannot be interpreted as `MM/dd/yyyy` because `13` is not a month. **The connector's advertised format says `MM/dd/yyyy HH:mm:ss`, which conflicts with the observed `13/10/2026` example.** For the read-only diagnostics we treat these strings as *apparent* DD/MM/YYYY in Asia/Ho_Chi_Minh and preserve the discrepancy as an unresolved source date-layout blocker. The calendar and timestamp semantics have NOT been independently certified. For `12/10/2026`, a US-format month/day parsing would mean 10 Dec rather than 12 Oct, so guessing would be unsafe without independent expected date evidence.

The intraday rows did **not** supply independent source-event IDs, true first-known times for each historical bar, a complete official minute-slot list, or proven auction/lunch coverage. Equal sums could arise because both SSI endpoints use a shared upstream dataset. This is **not** a verified independent audit or proof of complete native M1 historical data, valid RVOL_TOD source volume, full 20-session continuity or permitted retrospective backtest usage. No historical raw bulk pagination was available in the checked full-feed endpoint.

## New typed offline diagnostics contract

`SsiIntradaySample` and `SsiDailyMatchedReceipt` bind explicit symbol, exchange, date, endpoint identifier, fetch clock and source snapshot id to normalized integer volumes. The intraday sample requires a declared **`SsiTimestampLayout`** (`DAY_MONTH_YEAR`, `MONTH_DAY_YEAR`, or `UNKNOWN`) rather than guessing `12/10`; `UNKNOWN` fails closed. The layout designation is a caller claim, not source certification.

`audit_ssi_intraday_daily_volume` compares the sum of minute-volume rows with **daily `total_match_volume`** for the exact same exchange/date/symbol. It rejects:

- Empty `ticks` (cannot silently treat as a verified zero-volume trading day), absent daily matched-volume total, inconsistent exchange/symbol/date, duplicate local timestamp, malformed/date-inconsistent timestamp or a future market or fetch time.
- A daily total mismatch; source volume is an integer and `0` is valid, but missing volume is **not** zero. Float, bool and locale-delimited volume strings are rejected by `normalize_ssi_volume`.
- Incorrect SSI endpoint identifiers; the failed full/paged `marketdata_list_stock_infor` endpoint must NOT be silently substituted for the working non-paged `marketdata_list_intraday_stock_infor` endpoint.

Outputs: `BLOCKED` or `MATCH_UNCERTIFIED`, with row count, sum, daily match total and first/last UTC observation times. Always `timestamp_semantics_certified=False`, `minute_coverage_certified=False`, `cumulative_volume_certified=False`, `market_source_certified=False`, `actionable=False`.

This code **does not** populate v1.2 fully qualified CanonicalCandles from the SSI payload; no source UUIDs, revision lineage, calendar checks or licensing are invented. It cannot transition P0.11 `calculate_rvol_tod20` into a real calibrated B5 input merely because aggregate volumes match.

## Acceptance and next source audit

New synthetic unit/negative tests exercise exact equality/mismatch, 0 versus missing/empty rows, ambiguous clock parsing, future samples, symbol/date/venue mismatch, duplicate minutes, source endpoint substitution, invalid volume coercions, and nonapproval guarantees. Synthetic tests are separate from the three read-only SSI cross-endpoint summaries.

**B01–B08 remain OPEN**. The P0.12 result is a partial improvement of the B06 source-access diagnosis: one historical intraday endpoint works for three SHS dates; the full/paged endpoint still fails. Source entitlement, complete M1/tick series, provider/native M5/M15 parity, date-first policy, full official sessions, trade-value/cumulative auction definitions, corporate adjustments, 20 comparable historical sessions, real BT-01..16/OOS and executable B5 are **unverified**.

Next: check more independent symbol/venue/date samples and the precise provider's date-layout specification, obtain raw source identifiers and licensed retention evidence, compare reconstructed intraday M1→M5/M15 and cumulative-volume values with provider-native series using official versioned session slots. Only then submit B5 SHORT/SWING formula parameter candidates for review, followed by executable detector and simulator under approved gates. No changes to UI-1.0, CK2, FX2, Scanner, MOCHI or brokerage orders.
