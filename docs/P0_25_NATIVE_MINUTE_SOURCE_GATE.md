# GĐ4/P0.25 — Native minute-bar API discovery and non-executable source plans

**Date:** 2026-11-06 (Asia/Ho_Chi_Minh). **Status:** engineering-only discovery + synthetic CI. No additional price data downloaded, no credential collected, and no account-level market-data rights established.

## Verified official public documentation versus connected MCP capabilities

| Source surface | Officially documented resolution | In connected MCP tool catalog? | Authorization and limitations |
|---|---|---|---|
| Connected **SSI MCP** `marketdata_list_intraday_stock_infor` | Returns intraday `ticks` with clock labels; **not contractually established as native M1/M5/M15 OHLC** | YES, called read-only in P0.23/P0.24 | 215 SHS labels on 13/10 and 223 on 14/10 are diagnostic observations; timestamp convention/first-known/complete session and retention remain unverified |
| Connected **DNSE MCP** `price_get_history` | **DAY-only** (1-year snapshot) according to current MCP description | YES, called read-only in P0.23 | 248 DAY bars for SHS observed, not M1/M5/M15 |
| Separate **SSI FastConnect Data** `Market/IntradayOhlc` | Public guide shows an integer spelled **`resollution`** (sic), **default 1 minute**; DOES NOT enumerate explicit legal integer values 5 and 15 | **NO** matching live connector action found in current connected SSI MCP catalog | Public guide uses `GET`, while older vendor PDF describes `POST` — requires provider/version confirmation before integrating. Public AccessToken uses consumerID + consumerSecret. Pagination `pageIndex` documented 1–10, up to `pageSize=1000`; absence of full historical availability or complete data must NOT be silently overridden |
| Separate **DNSE OpenAPI** `GET /price/ohlc` | Official OpenAPI explicitly lists **`resolution=1,3,5,15,30,1H,1D,1W`**; `type=STOCK`, Unix `from`/`to` | **NO** matching action in current connected DNSE MCP catalog | Requires **X-API-Key, X-Aux-Date, X-Signature** for authenticated requests. This app connectivity and an API subscription/license are not evidenced |

Official docs inspected: [SSI FastConnect API spec](https://guide.ssi.com.vn/ssi-products/fastconnect-data/api-specs), [older FastConnect data spec PDF](https://ftp2.ssi.com.vn/Customers/GDDT/Document/SSI_FastConnectData_Specs.pdf), [SSI market data FAQ](https://developers.ssi.com.vn/docs/faq/market-data), [DNSE OpenAPI historical OHLC](https://developers.dnse.com.vn/docs/dnse/get-ohlc-history/), [DNSE Lightspeed Market Data terms](https://hdsd.dnse.com.vn/die-u-khoa-n-di-ch-vu-dnse/dieu-khoan-san-pham-dich-vu/dieu-khoan-san-pham-lightspeed-api).

**Important non-equivalences:** A public API product being documented does not mean the current connected MCP exposes it, that an account is entitled to use it, or that data may be cached and used for long-term historical backtests. SSI's documentation warns that minute history is limited to a recent period; DNSE API historical range and account-specific limits also require verification. Successful authentication by itself would not prove historical first-known timestamps, versioned revisions, price basis, fee assumptions, or complete session coverage.

## New conservative native bar source contract

New `src/swing_trading/native_minute_bar_source_plan.py` (no HTTP, no MCP, no I/O):

- `BarProduct` and `describe_bar_product`: fixed four-surface identity/provider catalog; exposes documented API URLs and **names of required authorization fields only**, not actual secret values.
- `resolution_evidence(product, timeframe)`: strict M1/M5/M15 mapping. Connected SSI ticks and DNSE DAY are `NOT_NATIVE_MINUTE_BARS`. DNSE OpenAPI explicitly lists all M1/M5/M15; SSI FastConnect only documents M1 as the default and an unenumerated integer resolution parameter for M5/M15, so those remain unconfirmed.
- `candidate_native_bar_sources(timeframe)`: returns four immutable source candidates with unresolved provider retention, account entitlement, independently authenticated timestamp semantics/first-known/revisions, adjustment policy, calendar/pagination, approved runtime storage, and executable B5/simulator blockers. All readiness and actionability properties are hardcoded **False**.
- `sketch_first_page_query(...)`: emits a bounded, **inert** first-page query parameter sketch: SSI date `dd/mm/yyyy`, first page `pageIndex=1`, `pageSize=1000`, publicly spelled `resollution=1`, with unresolved GET-vs-POST method; DNSE uses explicit single-Vietnam-session UTC start/end, Unix `from`/`to`, exact `resolution=1/5/15`, stock type. Never assembles signatures/headers, calls a host, caches OHLCV, or reports itself as ready to send. Rejects requests to interpret connected MCP tick/DAY endpoints as native minute bars, invalid or ambiguous windows, impossible SSI M5/M15 parameter assumptions, and unsafe symbols.
- Tests `tests/test_native_minute_bar_source_plan.py` validate catalog identity, source/product separation, source-native resolution evidence, exact inert parameter schemas, UTC/session boundaries, unsafe symbols, no forged rights/ready-to-send flags, and all historical BT/OOS gates staying closed.

The signed checkpoint/metadata-only ReferenceJournal and provider-separated SSI/DNSE cache design remain unchanged. No connection to FastConnect or DNSE OpenAPI was made, and no new broker account/authorization request is issued.

## Explicit OPEN / NEXT GĐ4/P0.26

1. **Source permission & retention:** obtain real account/provider approval for SSI FastConnect and/or DNSE OpenAPI Market Data, explicitly documenting historical download, caching, derived bars, offline backtest/OOS and retention expiry. Validate which account plan actually exposes each API, rather than inferring from public docs.
2. **Endpoint implementation reality:** confirm version/method conflicts for SSI `IntradayOhlc`, request signing flow for DNSE, per-account row/window limits, complete pagination and retry semantics; do not collect or store credentials until secure host approved.
3. **Market clocks and data:** validate source-native 1-minute start/end/last-event label conventions, first-known receipt/publication and revisions, auctions/lunch/no-trade/zero volume, corporate-action adjustment basis, and HNX/HOSE exchange calendar. Check M5/M15 native vs explicitly qualified 1m aggregation, never invent missing bars.
4. **Infrastructure/strategy:** approve hardened SQLite WAL/VFS/ACL/encrypted storage, independent signer/trust anchor, host read-only MCP bindings and opt-in source retention; B5 24 calibration parameters, one executable detector, realistic fill/slippage/fees/tax/T+2 simulator before **real historical BT/OOS**.

**UI-1.0 DESIGN_LOCKED**; CK2/FX2/Scanner/MOCHI unchanged; no trading orders, no production market-data cache and no actionable BUY/SELL.
