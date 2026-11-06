# SSI / DNSE rights confirmation — private review checklist v0.1

**Prepared for P0.30, 2026-11-07. NOT_SENT / NO_APPROVAL_RECEIVED.**

This is a question/evidence worksheet for an existing authorized private review or a later explicitly authorized provider enquiry. It does not contact either provider, register a service, request credentials or grant rights. Public descriptions can identify products; applicability to the actual account and the intended uses still needs independent review.

## Product selection — keep separate

| Candidate | Product-specific confirmation required | Current result |
| --- | --- | --- |
| SSI FastConnect Data V2 | Is this exact service/account enrolled for `Market/IntradayOhlc`? Confirm supported minute values, method/version and legacy pagination; do not copy V3 authentication | NOT_PROVIDED |
| SSI FastConnect V3 | Identify the actual approved Market Data product/API/terms version and native OHLC endpoint; independently document enrolment. This is not enrolment of the existing V2 enum | NOT_PROVIDED |
| DNSE signed OpenAPI | Confirm the actual LightSpeed/OpenAPI account/service enrolment for `/price/ohlc`, explicit API version and configured date-header/signing profile | NOT_PROVIDED |
| Connected SSI/DNSE MCP | Confirm rights for this connected surface independently; existing calls do not establish a separate API product's rights | NOT_PROVIDED |

Keep the project's existing SSI-first/DNSE-reference routing policy. This worksheet neither chooses a new live provider nor turns DNSE DAY history into native minute data.

## Six independent uses

For the intended private Swing Trading research, obtain the applicable term/approval for **each** row. Record allowed/denied/conditional, scope/limits, effective/expiry date and a privately verified clause/evidence reference. A published API capability or ability to log in does not answer these questions. Existing applicable terms plus verified enrolment may provide the answer; ask for vendor clarification where they do not.

| Scope | Question for the private reviewer/provider | Answer |
| --- | --- | --- |
| READ_HISTORICAL | May this account retrieve the required historical native M1/M5/M15 by symbol/exchange/date? What is the available window/limit? | NOT_PROVIDED |
| RETAIN_RAW_OHLCV | May raw bars be retained locally or in the proposed separate cloud host? For how long and under what access/backup/region restrictions? | NOT_PROVIDED |
| GENERATE_DERIVED_BARS | May retrieved bars be transformed/aggregated into the required derived timeframes/features for this project? | NOT_PROVIDED |
| RETAIN_DERIVED_BARS | May those derived bars/features be retained, and what source expiry/revocation restrictions propagate to them? | NOT_PROVIDED |
| RESEARCH_BACKTEST | May this account use the historical source in private quantitative backtests, with what limits? | NOT_PROVIDED |
| OUT_OF_SAMPLE_EVALUATION | Does the same permission cover independent OOS/walk-forward evaluation and retention of its permitted derived outputs? | NOT_PROVIDED |

No redistribution, public publication, commercial use, automated execution or brokerage orders are requested or enabled by this project worksheet. If the intended use changes, its rights require a separate review.

## Provenance, revocation and source quality

| Area | Required answer/evidence | Current result |
| --- | --- | --- |
| Issuer and applicable agreement | Verify provider identity and account/service binding privately; applicable terms/version and authorized approver/reviewer | MISSING |
| Suspension/revocation | Authoritative contact/status channel, effective time, expected notification delay and outage handling. Is there an actual machine-readable complete ordered rights-change feed? If so, supply its official protocol/public-key enrolment documentation, not a secret | MISSING |
| Credential lifecycle | What changes when the API key is regenerated/cancelled? Does data retention/usage permission continue or stop, and what must happen to retained raw/derived data/backups? | MISSING |
| Signature authority | If statements are signed, who owns the public key and what exactly does the signature attest? Distinguish broker-issued statements from an independently reviewed internal custody receipt | MISSING |
| Storage/deletion | Retention end, backups, transfer/host changes and evidence needed for purge/erasure; avoid assuming ordinary file deletion is verified erasure | MISSING |
| Source-time semantics | Bar-open/bar-close labels, publication/first-known time, revisions/corrections and as-of availability | MISSING |
| Native historical completeness | Supported M1/M5/M15, pagination/continuation, missing-vs-zero trades, sessions/auctions/calendar and historical coverage | MISSING |
| Price/volume basis | Units, matched/cumulative volume, raw/adjusted prices, corporate actions and revision/version policy | MISSING |

## Safe review outcome

The account owner can first indicate whether an applicable rights confirmation/terms acceptance already exists for SSI or DNSE. Do **not** paste API keys/secrets, tokens, OTPs or account numbers into chat/GitHub/Handoff. Original contracts/account evidence are reviewed only in an authorized private location. After independent review, store only approved opaque evidence references, product/version, reviewed scope/limits, reviewer roles, dates and unresolved conditions in the project.

A completed worksheet is still evidence intake, not self-authorization. No permission turns True, no API/host is activated and no retention/backtest starts without the remaining independently approved authority, source-quality and operational gates. An unclear or missing answer stays BLOCKED.
