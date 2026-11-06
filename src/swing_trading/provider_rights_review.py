"""GĐ4/P0.26 — non-sensitive provider entitlement evidence intake (NOT approval).

Accepts opaque evidence references and *claims*, never credentials, account IDs,
raw market data or agreements. Unverified claims, public docs and even positive
account claims cannot enable download, retention, B5, BT/OOS or trading.

Actual provider grant verification needs an independently reviewed contract,
account entitlement and host approval, all outside this module.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re

from .native_minute_bar_source_plan import BarProduct, describe_bar_product
from .replay import require_utc


class EvidenceKind(str, Enum):
    PUBLIC_PRODUCT_DOCUMENTATION = "PUBLIC_PRODUCT_DOCUMENTATION"
    ACCOUNT_ENTITLEMENT_CLAIM = "ACCOUNT_ENTITLEMENT_CLAIM"
    VENDOR_RIGHTS_LETTER_CLAIM = "VENDOR_RIGHTS_LETTER_CLAIM"


class RightsScope(str, Enum):
    READ_HISTORICAL = "READ_HISTORICAL"
    RETAIN_RAW_OHLCV = "RETAIN_RAW_OHLCV"
    GENERATE_DERIVED_BARS = "GENERATE_DERIVED_BARS"
    RETAIN_DERIVED_BARS = "RETAIN_DERIVED_BARS"
    RESEARCH_BACKTEST = "RESEARCH_BACKTEST"
    OUT_OF_SAMPLE_EVALUATION = "OUT_OF_SAMPLE_EVALUATION"


# Prevent personal data, credentials, URLs and unbounded input in a Handoff.
# This is an untrusted reference to an *external* review docket only.
_REF = re.compile(r"^EVID-[A-Z0-9]{8,32}$")
_REV = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,63}$")
_REQUIRED = tuple(RightsScope)


@dataclass(frozen=True)
class UnverifiedRightsClaim:
    product: BarProduct
    evidence_id: str
    kind: EvidenceKind
    recorded_at_utc: datetime
    scope_claims: tuple[RightsScope, ...]
    contract_version_claim: str
    maximum_retention_days_claim: int | None
    claimed_expiry_utc: datetime | None

    def __post_init__(self):
        describe_bar_product(self.product)
        if not isinstance(self.evidence_id, str) or not _REF.fullmatch(self.evidence_id):
            raise ValueError("Use only an opaque EVID- docket ID; no agreement or secrets")
        if not isinstance(self.kind, EvidenceKind):
            raise TypeError("Typed evidence kind required")
        require_utc(self.recorded_at_utc)
        if not isinstance(self.scope_claims, tuple) or any(
            not isinstance(s, RightsScope) for s in self.scope_claims
        ) or len(set(self.scope_claims)) != len(self.scope_claims):
            raise ValueError("Distinct typed scope claims required")
        if not isinstance(self.contract_version_claim, str) or not _REV.fullmatch(
            self.contract_version_claim
        ):
            raise ValueError("Opaque version identifier required; no document body")
        if (self.maximum_retention_days_claim is not None
                and (type(self.maximum_retention_days_claim) is not int
                     or not 0 <= self.maximum_retention_days_claim <= 3650)):
            raise ValueError("Retained-days claim must be bounded, not authorization")
        if self.claimed_expiry_utc is not None:
            require_utc(self.claimed_expiry_utc)
        if self.kind is EvidenceKind.PUBLIC_PRODUCT_DOCUMENTATION and (
            self.scope_claims or self.maximum_retention_days_claim is not None
            or self.claimed_expiry_utc is not None
        ):
            raise ValueError("Public documentation cannot claim account-level rights")

    @property
    def independently_verified(self):
        return False

    @property
    def eligible_for_source_data(self):
        return False

    @property
    def production_approved(self):
        return False


@dataclass(frozen=True)
class ProviderRightsReview:
    product: BarProduct
    reviewed_at_utc: datetime
    evidence_ids_seen: tuple[str, ...]
    claimed_scopes_unverified: tuple[RightsScope, ...]
    missing_scope_claims: tuple[RightsScope, ...]
    expired_claims: tuple[str, ...]
    unresolved: tuple[str, ...]

    @property
    def provider_authorization_verified(self):
        return False

    @property
    def raw_ohlcv_retention_allowed(self):
        return False

    @property
    def derived_ohlcv_retention_allowed(self):
        return False

    @property
    def real_backtest_allowed(self):
        return False

    @property
    def native_m1_m5_m15_qualified(self):
        return False

    @property
    def production_authorized(self):
        return False

    @property
    def actionable(self):
        return False


def review_unverified_source_claims(
    product: BarProduct,
    evidence: tuple[UnverifiedRightsClaim, ...],
    *,
    reviewed_at_utc: datetime,
) -> ProviderRightsReview:
    """Compute missing *claims*, NOT validated permissions.

    A public product page, contract version or even a self-declared letter
    is never a rights grant. Separate review by the actual provider and an
    independent account/terms custodian is required before live access.
    """
    describe_bar_product(product)
    require_utc(reviewed_at_utc)
    if not isinstance(evidence, tuple) or any(
        not isinstance(c, UnverifiedRightsClaim) for c in evidence
    ):
        raise TypeError("Explicit tuple of typed evidence claims required")
    if len(evidence) > 128:
        raise ValueError("Unbounded evidence review forbidden")
    ids = [c.evidence_id for c in evidence]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate evidence docket ID")
    if any(c.product is not product for c in evidence):
        raise ValueError("Cross-product licence claims cannot be reused")
    if any(c.recorded_at_utc > reviewed_at_utc for c in evidence):
        raise ValueError("Future-dated evidence cannot be reviewed")

    expired = tuple(sorted(c.evidence_id for c in evidence
                   if c.claimed_expiry_utc is not None
                   and c.claimed_expiry_utc <= reviewed_at_utc))
    active = [c for c in evidence
              if c.evidence_id not in expired
              and c.kind is not EvidenceKind.PUBLIC_PRODUCT_DOCUMENTATION]
    claimed = tuple(s for s in _REQUIRED
                    if any(s in c.scope_claims for c in active))
    missing = tuple(s for s in _REQUIRED if s not in claimed)
    missing_flags = ["NO_ACCOUNT_SPECIFIC_INDEPENDENT_PROVIDER_ENTITLEMENT"]
    if not evidence:
        missing_flags.append("NO_ENTITLEMENT_EVIDENCE_REFERENCES")
    if not active:
        missing_flags.append("NO_ACTIVE_ACCOUNT_RIGHTS_CLAIM")
    if expired:
        missing_flags.append("EXPIRED_RIGHTS_CLAIM_PRESENT")
    if missing:
        missing_flags.append("MISSING_REQUIRED_SCOPE_CLAIMS")
    missing_flags += [
        "VENDOR_GRANT_AUTHENTICITY_NOT_VERIFIED",
        "ACCOUNT_TO_PRODUCT_BINDING_NOT_VERIFIED",
        "EXPLICIT_DATA_WINDOW_RETENTION_RESTRICTIONS_NOT_VERIFIED",
        "LIVE_NATIVE_M1_M5_M15_TIMESTAMP_FIRST_KNOWN_NOT_VERIFIED",
        "HOST_WAL_ENCRYPTION_ACL_AND_REVOKE_FLOW_NOT_APPROVED",
        "B5_DETECTOR_SIMULATOR_BACKTEST_NOT_READY",
    ]
    return ProviderRightsReview(
        product, reviewed_at_utc, tuple(sorted(ids)),
        claimed, missing, expired, tuple(missing_flags),
    )


def require_authorized_source(review: ProviderRightsReview):
    """Explicit fail-closed boundary — there is no trust-root wired in P0.26."""
    if not isinstance(review, ProviderRightsReview):
        raise TypeError("Typed review required")
    raise PermissionError(
        "P0.26 only evaluates unverified evidence: no approved provider trust root"
    )
