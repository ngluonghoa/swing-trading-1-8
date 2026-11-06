# GĐ4/P0.26 — Provider-specific rights evidence intake, independent review gate and API-version separation

**Date:** 2026-11-06 · **ENGINEERING-ONLY, NO MARKET DATA LICENSE APPROVAL, NO NEW CONNECTION.**

## What public provider documentation actually establishes

- SSI FastConnect Developer Portal terms require an SSI account, FastConnect registration and approval, agreement to service conditions, safe custody of API keys/secrets, and rate-limit compliance. The newer Developer Portal describes a **FastConnect V3** token/API family and an **intraday 1-year** data limit. Neither establishes that this user/account is enrolled, that this specific V3 API grants ongoing caching or backtesting rights, or that V3 authentication can be substituted for the **separately documented old FastConnect Data V2** `fc-data.ssi.com.vn/api/v2/Market/IntradayOhlc` with consumerID/consumerSecret, `resollution` and legacy pagination. **Never mix V2 and V3 authentication/method semantics without explicit vendor confirmation.**
- DNSE OpenAPI documentation describes `GET /price/ohlc` with M1/M5/M15 resolution values and **X-API-Key, X-Aux-Date, X-Signature** request authentication. This is an *external* OpenAPI product, not the currently connected DNSE `price_get_history` MCP (DAY-only). Documentation does not grant account access, raw data retention, redistribution, derived candle retention or research backtest rights.
- Successful calls to the connected SSI/DNSE MCP in P0.23–24 are **diagnostic observations** and do not prove entitlement to FastConnect Data V2, FastConnect V3, or DNSE signed OpenAPI. We have not called either external OHLC API, created credentials, requested market subscriptions, or stored prices in this milestone.

Primary public references: [SSI terms and environment](https://developers.ssi.com.vn/docs/getting-started/terms-and-environments), [SSI FastConnect V3 overview](https://developers.ssi.com.vn/docs/getting-started/overview), [SSI Data V2 IntradayOhlc](https://guide.ssi.com.vn/ssi-products/fastconnect-data/api-specs), [DNSE OHLC endpoint](https://developers.dnse.com.vn/docs/dnse/get-ohlc-history/).

## Required review scopes — independent per product and account

Each provider/product needs **separate** documentary evidence of: (1) permission to read historical bars; (2) storage of raw OHLCV; (3) transforming M1 into derived candles; (4) retention of derived candles; (5) quantitative historical backtest; (6) out-of-sample evaluation. Any verified grant also needs version, provider product/symbol/exchange scope, historical range and earliest date, retention limits, expiry and revocation process, identity of the approved business account, and terms for deletion, backups, transfer and logs. Do not assume one permission implies the other five.

The original signed contract or provider confirmation must be reviewed independently by authorized people or a separately trusted compliance/custody system. Public API pages, account entitlement **claims**, login success, copied vendor letters or a user-asserted checkbox are **not sufficient**; the self-attested sources cannot be promoted to a permanent permission.

### Code: `src/swing_trading/provider_rights_review.py`

- `RightsScope` enumerates six independent rights.
- `UnverifiedRightsClaim` accepts only a strictly limited opaque `EVID-XXXXXXXX` review docket ID (no account number, URLs, token, contract body), exact `BarProduct`, typed evidence kind, UTC recorded/claimed expiry times, unique scope claims and bounded retention-days claim. `PUBLIC_PRODUCT_DOCUMENTATION` cannot claim account-specific rights.
- `review_unverified_source_claims(product, evidence_tuple, reviewed_at_utc)` rejects cross-product reuse, duplicate IDs, future-dated claims and oversized intake. It separates **claimed but unverified** scopes, missing scope claims, expired claims and specific unresolved external evidence gates. All returned `ProviderRightsReview` controls remain hard-coded **False** for authorization, raw/derived retention, source-native M1/M5/M15 qualification, backtest, production and trading.
- `require_authorized_source(review)` always fails closed: P0.26 has no external vendor trust-root/review authority wired. A fully filled-in claim cannot become a production approval. Neither claims nor reports include source price content or actual credentials.

Negative synthetic tests include spoofed approval, evidence expiry/revocation precursor, duplicate and cross-provider evidence, public-doc rights escalation, invalid dates, untrusted IDs, scope overlap and false full rights assertions.

## Outstanding evidence and subsequent work

**BLOCKED:**
1. Confirm SSI FastConnect Data V2 vs V3 entitlement and endpoint/method/resolution mapping with SSI, or DNSE signed OpenAPI access and source rights with DNSE, **without placing secrets in source control or Handoff**.
2. Independently validate provider approval for all six scopes and historical coverage/first-known/revisions, exchange session/corporate actions, exact SSI/DNSE pagination, time labels, zero-volume/no-trade and native M1/M5/M15 behavior.
3. Specify an independent authoritative entitlement verifier and revocation-aware renewal process before **any permission gate may become true**. This code is a *requirements and evidence intake layer*, not a legal verifier or signing-service implementation.
4. Review a hardened host SQLite/VFS/WAL, encryption/ACL/retention/erasure, independent checkpoint custody. Until then SSI/DNSE quote persistence is OFF and signed P0.18 backups remain metadata-only. B5 24 numerical threshold slots, executable detector, fill/fees/slippage/tax/T+2 and real historical BT/OOS remain NOT_RUN.

**UI-1.0 DESIGN_LOCKED**; CK2, FX2, Scanner, MOCHI untouched. No broker orders or actionable signal.
