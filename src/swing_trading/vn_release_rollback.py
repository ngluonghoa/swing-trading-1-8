"""VN cash-equity release / rollback preflight (engineering-only, read-only).

This module deliberately cannot approve a release, move a release pointer,
place orders, restore a database or grant source entitlements. It only makes
profile dependencies and failure conditions explicit for independent review.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from hashlib import sha256
import json
import re


_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA40 = re.compile(r"^[a-f0-9]{40}$")
_SHA64 = re.compile(r"^[a-f0-9]{64}$")


def _utc(value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError("Timestamp must be timezone-aware UTC")


def _ref(value: str) -> None:
    if not isinstance(value, str) or not _REF.fullmatch(value):
        raise ValueError("Nonempty opaque version/reference ID required; no secrets or free text")


class Venue(str, Enum):
    HOSE = "HOSE"
    HNX = "HNX"
    UPCOM = "UPCOM"


class RollbackLayer(str, Enum):
    R1_CODE = "R1_CODE"
    R2_RULE_PARAMS = "R2_RULE_PARAMS"
    R3_SOURCE_DATA = "R3_SOURCE_DATA"
    R4_SCHEMA_CACHE = "R4_SCHEMA_CACHE"
    R5_UI_REPORT = "R5_UI_REPORT"
    R6_ACCOUNT_SETTLEMENT = "R6_ACCOUNT_SETTLEMENT"
    R7_DOCS_RELEASE = "R7_DOCS_RELEASE"


_LAYER_FIELDS: dict[RollbackLayer, tuple[str, ...]] = {
    RollbackLayer.R1_CODE: ("code_git_sha", "dependency_lock_sha256"),
    RollbackLayer.R2_RULE_PARAMS: (
        "strategy_id", "detector_ruleset_id", "detector_ruleset_sha256",
        "parameter_set_id", "parameter_sha256", "indicator_version",
    ),
    RollbackLayer.R3_SOURCE_DATA: (
        "source_provider", "source_product_id", "source_revision_id",
        "source_rights_policy_id", "first_known_policy_id",
        "corporate_action_basis_id",
    ),
    RollbackLayer.R4_SCHEMA_CACHE: ("event_schema_id", "cache_schema_id"),
    RollbackLayer.R5_UI_REPORT: ("ui_design_id", "ui_report_contract_id"),
    RollbackLayer.R6_ACCOUNT_SETTLEMENT: (
        "exchange_calendar_version", "session_rules_version",
        "settlement_t2_policy_id", "execution_cost_model_id",
        "fill_liquidity_model_id", "risk_policy_id",
    ),
    RollbackLayer.R7_DOCS_RELEASE: (
        "audit_pipeline_id", "experiment_id", "release_id",
    ),
}


@dataclass(frozen=True)
class FullExecutionProfile:
    """Immutable *claimed* profile identity, not an approved release/LKG.

    The snapshot is fully explicit; no provider rights or account state is inferred
    from a populated profile. Hashes identify assets but are not signatures.
    """

    release_id: str
    code_git_sha: str
    dependency_lock_sha256: str
    strategy_id: str
    detector_ruleset_id: str
    detector_ruleset_sha256: str
    parameter_set_id: str
    parameter_sha256: str
    indicator_version: str
    source_provider: str
    source_product_id: str
    source_revision_id: str
    source_rights_policy_id: str
    first_known_policy_id: str
    exchange_calendar_version: str
    session_rules_version: str
    corporate_action_basis_id: str
    settlement_t2_policy_id: str
    execution_cost_model_id: str
    fill_liquidity_model_id: str
    risk_policy_id: str
    event_schema_id: str
    cache_schema_id: str
    ui_design_id: str
    ui_report_contract_id: str
    audit_pipeline_id: str
    experiment_id: str

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            _ref(value)
        if not _SHA40.fullmatch(self.code_git_sha):
            raise ValueError("code_git_sha must be a full lowercase Git SHA-1")
        for name in ("dependency_lock_sha256", "detector_ruleset_sha256", "parameter_sha256"):
            if not _SHA64.fullmatch(getattr(self, name)):
                raise ValueError(f"{name} must be a lowercase SHA256")
        if self.strategy_id not in ("SHORT", "SWING"):
            raise ValueError("VN strategy must be SHORT or SWING, not a short-sale permission")
        if self.source_provider not in ("SSI", "DNSE"):
            raise ValueError("Use an isolated SSI or DNSE provider namespace per profile")
        if self.audit_pipeline_id != "EIGHT_STEP_AUDIT_V1":
            raise ValueError("Eight-step audit contract may not be silently replaced")
        if self.ui_design_id != "UI_1_0_DESIGN_LOCKED":
            raise ValueError("Approved UI v1.0 design remains locked")

    @property
    def fingerprint_sha256(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return sha256(("SwingTrading1.8/VnFullExecutionProfile/v1\0" + payload).encode()).hexdigest()


@dataclass(frozen=True)
class VnShareAvailability:
    """Caller-provided broker snapshot; *never* an independently verified balance.

    T+2 pending securities are explicitly excluded from sellable quantity. The
    simulator may not convert pending to settled merely by advancing its clock.
    """

    broker_snapshot_id: str
    symbol: str
    venue: Venue
    observed_at_utc: datetime
    settled_sellable_qty: int | None
    pending_t2_qty: int | None
    restricted_qty: int | None
    requested_sell_qty: int
    broker_settlement_confirmation: bool
    corporate_actions_reconciled: bool

    def __post_init__(self) -> None:
        _ref(self.broker_snapshot_id)
        _ref(self.symbol)
        if not isinstance(self.venue, Venue):
            raise ValueError("Known broker position venue required")
        _utc(self.observed_at_utc)
        for name in ("settled_sellable_qty", "pending_t2_qty", "restricted_qty"):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"{name} must be nonnegative int or unknown")
        if type(self.requested_sell_qty) is not int or self.requested_sell_qty < 0:
            raise ValueError("requested_sell_qty must be a nonnegative integer")
        if type(self.broker_settlement_confirmation) is not bool or type(self.corporate_actions_reconciled) is not bool:
            raise ValueError("Flags must be booleans")


@dataclass(frozen=True)
class VnPriceRuleSnapshot:
    """Exchange- and session-specific price rules supplied externally.

    No permanent 7/10/15% bands or tick schedule is hardcoded: first trading
    days, post-suspension sessions and corporate actions can change those rules.
    """

    venue: Venue
    rule_revision_id: str
    observed_at_utc: datetime
    floor_vnd: Decimal | None
    ceiling_vnd: Decimal | None
    tick_vnd: Decimal | None
    proposed_order_price_vnd: Decimal | None
    exchange_session_confirmed: bool
    exceptional_rule_reviewed: bool

    def __post_init__(self) -> None:
        if not isinstance(self.venue, Venue):
            raise ValueError("Known venue required")
        _ref(self.rule_revision_id)
        _utc(self.observed_at_utc)
        for name in ("floor_vnd", "ceiling_vnd", "tick_vnd", "proposed_order_price_vnd"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, Decimal) or not value.is_finite() or value <= 0):
                raise ValueError(f"{name} must be a positive finite Decimal or unknown")
        if self.floor_vnd is not None and self.ceiling_vnd is not None and self.floor_vnd > self.ceiling_vnd:
            raise ValueError("Reversed floor/ceiling")
        if type(self.exchange_session_confirmed) is not bool or type(self.exceptional_rule_reviewed) is not bool:
            raise ValueError("Flags must be booleans")


@dataclass(frozen=True)
class VnRollbackContext:
    venue: Venue
    symbol: str
    checked_at_utc: datetime
    share_availability: VnShareAvailability | None = None
    price_rules: VnPriceRuleSnapshot | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.venue, Venue):
            raise ValueError("Known venue required")
        _ref(self.symbol)
        _utc(self.checked_at_utc)
        if self.price_rules is not None and self.price_rules.venue is not self.venue:
            raise ValueError("Exchange rule snapshot venue mismatch")
        if self.share_availability is not None and (self.share_availability.symbol != self.symbol or self.share_availability.venue is not self.venue):
            raise ValueError("Broker position must match exact symbol and venue")
        if self.share_availability is not None and self.share_availability.observed_at_utc > self.checked_at_utc:
            raise ValueError("Future broker snapshot forbidden")
        if self.price_rules is not None and self.price_rules.observed_at_utc > self.checked_at_utc:
            raise ValueError("Future rule snapshot forbidden")


@dataclass(frozen=True)
class RollbackPreflight:
    """Read-only analysis. No returned state is executable or authority-granting."""

    active_fingerprint: str
    target_fingerprint: str | None
    changed_layers: tuple[RollbackLayer, ...]
    requested_layers: tuple[RollbackLayer, ...]
    reasons: tuple[str, ...]
    invalidate_derived_cache: bool
    account_reconciliation_required: bool
    state: str = "SAFE_MODE_ONLY"
    can_activate: bool = False
    can_place_orders: bool = False

    def __post_init__(self) -> None:
        if self.state != "SAFE_MODE_ONLY" or self.can_activate or self.can_place_orders:
            raise ValueError("This engineering preview cannot authorize action")


def _changed_layers(active: FullExecutionProfile, target: FullExecutionProfile) -> tuple[RollbackLayer, ...]:
    return tuple(layer for layer, fields in _LAYER_FIELDS.items()
                 if any(getattr(active, f) != getattr(target, f) for f in fields))


def preview_vn_rollback(
    active: FullExecutionProfile,
    target_lkg_claim: FullExecutionProfile | None,
    requested_layers: tuple[RollbackLayer, ...],
    *,
    context: VnRollbackContext | None = None,
) -> RollbackPreflight:
    """Perform conservative candidate compatibility review; NEVER execute rollback.

    An LKG claim is not accepted as trusted from a caller or Git commit; an
    independent approval/recovery service is needed. A SELL recommendation is
    never interpreted as permission to short stock or to sell T+2 pending stock.
    """
    if not isinstance(active, FullExecutionProfile):
        raise TypeError("Typed active profile required")
    if target_lkg_claim is not None and not isinstance(target_lkg_claim, FullExecutionProfile):
        raise TypeError("Typed target LKG claim required")
    if not isinstance(requested_layers, tuple) or any(not isinstance(x, RollbackLayer) for x in requested_layers):
        raise TypeError("Typed rollback layers required")
    if len(set(requested_layers)) != len(requested_layers):
        raise ValueError("Duplicate rollback layers")
    if context is not None and not isinstance(context, VnRollbackContext):
        raise TypeError("Typed VN context required")

    reasons = []
    changed = ()
    if target_lkg_claim is None:
        reasons.append("ROLLBACK_BLOCKED_NO_APPROVED_LKG")
    else:
        changed = _changed_layers(active, target_lkg_claim)
        if not changed:
            reasons.append("NO_PROFILE_CHANGE_TO_ROLL_BACK")
        for layer in changed:
            if layer not in requested_layers:
                reasons.append("OUT_OF_SCOPE_" + layer.value)
        if RollbackLayer.R3_SOURCE_DATA in changed:
            reasons.append("SOURCE_RIGHTS_AND_REVISION_REQUALIFICATION_REQUIRED")
        if RollbackLayer.R4_SCHEMA_CACHE in changed:
            reasons.append("SCHEMA_COMPATIBILITY_AND_RESTORE_UNVERIFIED")
        if RollbackLayer.R6_ACCOUNT_SETTLEMENT in changed:
            reasons.append("VN_SETTLEMENT_CALENDAR_RISK_REQUALIFICATION_REQUIRED")
        if RollbackLayer.R5_UI_REPORT in changed:
            reasons.append("LOCKED_UI_CHANGE_REQUIRES_SEPARATE_APPROVAL")
        reasons.append("LKG_INDEPENDENT_APPROVAL_AND_RESTORE_PROOF_UNVERIFIED")

    account_gate = RollbackLayer.R6_ACCOUNT_SETTLEMENT in changed
    if context is None:
        reasons.append("VN_MARKET_ACCOUNT_CONTEXT_NOT_VERIFIED")
        account_gate = True
    else:
        if context.price_rules is None:
            reasons.append("VENUE_PRICE_SESSION_RULES_UNKNOWN")
        else:
            p = context.price_rules
            if not p.exchange_session_confirmed or not p.exceptional_rule_reviewed:
                reasons.append("VENUE_RULES_NEED_EXTERNAL_CONFIRMATION")
            if (p.floor_vnd is None or p.ceiling_vnd is None or p.tick_vnd is None
                    or p.proposed_order_price_vnd is None):
                reasons.append("PRICE_BAND_OR_TICK_UNKNOWN")
            else:
                if not p.floor_vnd <= p.proposed_order_price_vnd <= p.ceiling_vnd:
                    reasons.append("PRICE_OUTSIDE_EXCHANGE_BAND")
                if p.proposed_order_price_vnd % p.tick_vnd != 0:
                    reasons.append("INVALID_TICK_SIZE")
        if context.share_availability is None:
            reasons.append("BROKER_SHARE_AVAILABILITY_UNKNOWN")
            account_gate = True
        else:
            s = context.share_availability
            if not s.broker_settlement_confirmation:
                reasons.append("T2_SETTLEMENT_NOT_CONFIRMED_BY_BROKER")
                account_gate = True
            if not s.corporate_actions_reconciled:
                reasons.append("CORPORATE_ACTIONS_NOT_RECONCILED")
                account_gate = True
            if s.settled_sellable_qty is None or s.pending_t2_qty is None or s.restricted_qty is None:
                reasons.append("BROKER_INVENTORY_PARTIALLY_UNKNOWN")
                account_gate = True
            elif s.requested_sell_qty > s.settled_sellable_qty:
                reasons.append("SELL_EXCEEDS_SETTLED_SELLABLE_SHARES")
                account_gate = True
            # Never add pending_t2_qty to sellable, regardless of time advancement.

    reasons.append("NO_EXECUTION_OR_INDEPENDENT_RELEASE_CUSTODIAN_CONNECTED")
    return RollbackPreflight(
        active_fingerprint=active.fingerprint_sha256,
        target_fingerprint=target_lkg_claim.fingerprint_sha256 if target_lkg_claim else None,
        changed_layers=changed,
        requested_layers=requested_layers,
        reasons=tuple(dict.fromkeys(reasons)),
        invalidate_derived_cache=bool(set(changed) & {
            RollbackLayer.R1_CODE, RollbackLayer.R2_RULE_PARAMS,
            RollbackLayer.R3_SOURCE_DATA, RollbackLayer.R4_SCHEMA_CACHE,
            RollbackLayer.R6_ACCOUNT_SETTLEMENT,
        }),
        account_reconciliation_required=account_gate,
    )
