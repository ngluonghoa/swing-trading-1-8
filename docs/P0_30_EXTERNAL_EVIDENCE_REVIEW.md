# GĐ4/P0.30 — External evidence review and custody decision

**Reviewed:** 2026-11-07, Asia/Ho_Chi_Minh.
**Outcome:** PUBLIC_DOCUMENTATION_REVIEWED; account rights, actual key ownership, independent custodian and live integration **BLOCKED / NOT_VERIFIED**.

This milestone reviews available evidence and specifies the remaining operational boundary. Executable source/tests stay at P0.29. There is no new licence verifier, self-approval layer, signer, storage implementation or provider connection.

## Starting-state receipt and search scope

- Main `cdcfe84fa0603c119c28c708587fc3fe9a3d4659`, after merged PRs #69/#70, no newer/open PR at intake. Its GitHub Actions run `42266675035` and both Python 3.11/3.12 jobs succeeded; the existing suite has 667 synthetic tests.
- Fresh full original Drive Handoff §27.53 matched main: 322,689 characters / 362,718 UTF-8 bytes, SHA-256 `30fb1aef40a1fc67a103241655c7ab5aaba1fa7c15a5c4bca0d3753f854be207`.
- The supplied project folder returned its ten design/audit documents. A separate accessible-Drive filename search for SSI, DNSE, custodian, provenance and entitlement found the existing SSI source audit. Neither search produced an account-bound rights dossier or actual custodian enrolment/recovery evidence. This is a bounded search result, **not a statement about every document the user may hold elsewhere**. No unrelated trading project or private account portal was opened.

## What the primary sources establish

Only official provider documentation was used for the provider facts below. These are public product/authentication observations, not account-specific approval. Pages were reviewed on the date above; originals were not copied into the repository, and no example prices/credentials were retained.

| Surface | Established by the reviewed documentation | Operational conclusion |
| --- | --- | --- |
| SSI FastConnect Data V2 | [V2 API specs](https://guide.ssi.com.vn/ssi-products/fastconnect-data/api-specs) describe `Market/AccessToken` with consumer credentials and a separate `Market/IntradayOhlc`; its integer `resollution` defaults to one minute | Preserve the existing V2 product identity. V3 token semantics and M5/M15 values cannot be substituted into this V2 contract |
| SSI FastConnect V3 | [Overview](https://developers.ssi.com.vn/docs/getting-started/overview) and [auth-token](https://developers.ssi.com.vn/docs/api-reference/auth-token) describe API key/secret token acquisition; OTP adds trading capability. The overview lists minute OHLC intervals. [Technical integration FAQ](https://developers.ssi.com.vn/docs/faq/technical-integration) describes RSA/SHA256 request signatures for order mutations | Token/request signing is a different authority and payload from a provider-rights event/head signature. Do not enrol any of those credentials as a P0.29 root |
| SSI service/terms | [Terms/environment](https://developers.ssi.com.vn/docs/getting-started/terms-and-environments) describes service conditions, account/API suspension and a recent-year intraday window. [Service FAQ](https://developers.ssi.com.vn/docs/faq/service-overview) describes online activation without the former manual-email process | Applicable service version/enrolment must be confirmed for the actual account. Public process descriptions do not establish this user's enrolment, retention scopes or a complete revocation feed |
| DNSE signed OpenAPI | [Authentication](https://developers.dnse.com.vn/docs/guide/intro/authentication/) describes HMAC-SHA256 over request metadata with a new nonce/time. [OHLC endpoint](https://developers.dnse.com.vn/docs/dnse/get-ohlc-history/) documents `GET /price/ohlc`, minute resolutions and `X-Aux-Date`; the general guide allows a configured date-header name | HMAC authenticates a request using the account secret; it is not a publicly verifiable vendor licence signature. Pin the actual product/API version, date-header mapping and signing profile before a future approved integration |
| DNSE key lifecycle | [FAQ](https://developers.dnse.com.vn/docs/guide/faq/) distinguishes regenerating credentials from cancelling the API service | Credential lifecycle is not proof of data-retention entitlement or an externally witnessed ordered history of rights revocations |
| Connected SSI/DNSE MCP | Prior project evidence documents SSI tick-labelled intraday observations and DNSE DAY history, as separate surfaces | No live market MCP was called in P0.30. Existing connections do not establish enrolment/retention rights for the separate native OHLC APIs |

**Bounded finding:** the reviewed pages establish no vendor-issued Ed25519 rights-event/key-registry schema or authenticated challenge-bound licensing-head service compatible with P0.28/P0.29. This does not prove such a private vendor offering is unavailable. Its existence, issuer and protocol need concrete evidence before integration.

**Date-header finding:** `Date` in the DNSE general guide and `X-Aux-Date` in the OHLC page are **not diagnosed as a vendor bug**: the guide expressly allows a configured header name. Their exact version/profile mapping remains unverified for this project. No request was sent to guess it. DNSE's request anti-replay timing and the project's P0.29 head TTL are separate policies.

## Authority distinction required by ADR-0003

P0.28/P0.29's Ed25519 records are a **project-defined proposed custody format**. They are not an observed SSI/DNSE feed. A future independent reviewer could attest review of applicable terms plus independently verified account/service enrolment, with a vendor clarification where rights are ambiguous. Such an internal signature would prove only that reviewer's attestation under its approved policy; it must not be labelled a vendor-issued grant or proof that the latest vendor revocation has been observed.

Do not require a broker to implement our invented format as if it were an existing API. Equally, do not relabel an API key, JWT, request HMAC/RSA signature, successful read, self-declared actor or filled checklist as permission to retain/backtest. No permission property changes in this milestone.

## Concrete evidence gaps and ownership

| Gate | Evidence needed | Current result | Who must supply/verify it |
| --- | --- | --- | --- |
| Account/product binding | Actual applicable service enrolment plus exact provider/product/API/terms version; original identifying material reviewed privately | MISSING_IN_REVIEWED_SOURCES | Account owner and independently authorized reviewer |
| Six rights scopes | Historical read, raw retention, derivation, derived retention, research backtest and OOS, including any limits/denials | NOT_VERIFIED | Applicable vendor terms/approval and authorized review |
| Retention lifecycle | Duration, expiry, revocation contact/channel, backups, deletion and suspension handling | NOT_VERIFIED | Vendor clarification where terms do not resolve it |
| Root/key provenance | Who owns the public key, what statements it is authorized to sign, authenticated out-of-band fingerprint/enrolment and recovery policy | NO_ACTUAL_ROOT_ENROLLED | Approved independent authority; not the engine/request caller |
| Revocation completeness | Actual source of rights changes, source watermark/known-through time, ordering/completeness, outage and freshness policy | NO_AUTHENTICATED_SOURCE | Vendor or approved review authority with explicitly limited guarantees |
| Independent retained floor | Separate control, durable CAS, witnessed high-water state, crash/restore/rollback evidence | DESIGN_ONLY | Approved host/custodian operators and independent reviewer |
| Host/deployment | Concrete platform, owners, storage/keys, cost/region and access review | NOT_SELECTED / NOT_APPROVED | User decision after a reviewable proposal and evidence |

The [provider confirmation checklist](PROVIDER_RIGHTS_CONFIRMATION_CHECKLIST.md) is ready for a private evidence review or a separately authorized provider enquiry. It has not been sent. No API secret, OTP, account number, original agreement or price series belongs in GitHub/Handoff.

## Custody design and verification boundary

The [CAS/recovery specification](RIGHTS_CUSTODY_CAS_RECOVERY_SPEC.md) defines primary/witness commit order, lost-ack reconciliation and restore rules. It separates ordinary atomic updates from detection of restoring an entire stale database. All listed operational failure drills are **SPECIFIED / NOT_RUN**. No database/cloud vendor, external witness or host has been chosen; it is a reviewable protocol proposal, not an implementation or approved architecture deployment.

The existing 667 unit/security tests remain engineering evidence. Their number does not increase for this documentation/evidence review. [Review PR #71](https://github.com/ngluonghoa/swing-trading-1-8/pull/71) merged as `7ca9a6cdd8a772285e8e0a35197eafd08119ca46` after [exact-head PR CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42268625183). That run and [post-merge main CI](https://github.com/ngluonghoa/swing-trading-1-8/actions/runs/42268829682) were independently checked, including logs: **667/667 on EACH Python 3.11/3.12**. They do not test the proposed external coordinator/witness, legal rights, real key ownership, provider latest-head freshness or operational recovery.

## Next step and stop condition

**GĐ4/P0.31 — external dossier review, blocked pending actual input.** The immediate missing input is an existing applicable account/service rights confirmation for SSI or DNSE, or an explicit decision to seek clarification using the prepared questions. No message to a provider is authorized by this document. Only after that review can an actual authority/custodian/host proposal be assessed. Another synthetic root/checkbox/test layer does not resolve the missing input.

Keep all source/retention/runtime/production gates closed. SSI B01–B08, historical native M1/M5/M15 quality/first-known/revisions/calendar/adjustments, executable calibrated B5 and realistic simulator/BT/OOS remain separate open items. UI-1.0, CK2, FX2, Scanner and MOCHI are unchanged. No market-data call, OHLCV persistence, signal or order is performed.

## Canonical Handoff receipt

Original native Drive Handoff updated in place to §27.54. Three current front-matter paragraphs refreshed; the other 942 original paragraphs and their order were checked unchanged. Full export: **330411 Unicode characters / 371125 UTF-8 bytes**, BOM/CRLF preserved, SHA-256 `af85fcfa4e16d7c48c177f61522db9ae2ee937f8a8c4e91ab5aa5549bb7bc1b2`. The separate Handoff documentation PR requires CI and fresh Drive-vs-main equality at closure; its PR records the observed result.
