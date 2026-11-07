"""Synthetic-only negative and identity checks for VN release/rollback preview."""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from swing_trading.vn_release_rollback import (
    FullExecutionProfile, RollbackLayer, Venue, VnPriceRuleSnapshot,
    VnRollbackContext, VnShareAvailability, preview_vn_rollback,
)


NOW = datetime(2026, 11, 7, 0, 0, tzinfo=timezone.utc)


def profile(**kwargs):
    base = dict(
        release_id="RC-1", code_git_sha="a" * 40,
        dependency_lock_sha256="b" * 64, strategy_id="SWING",
        detector_ruleset_id="RULE-1", detector_ruleset_sha256="c" * 64,
        parameter_set_id="PARAM-1", parameter_sha256="d" * 64,
        indicator_version="IND-1", source_provider="SSI",
        source_product_id="SSI-V2", source_revision_id="REV-1",
        source_rights_policy_id="RIGHTS-UNKNOWN", first_known_policy_id="FIRST-1",
        exchange_calendar_version="CAL-1", session_rules_version="SESSION-1",
        corporate_action_basis_id="CA-1", settlement_t2_policy_id="T2-1",
        execution_cost_model_id="COST-1", fill_liquidity_model_id="FILL-1",
        risk_policy_id="RISK-1", event_schema_id="EVT-1", cache_schema_id="CACHE-1",
        ui_design_id="UI_1_0_DESIGN_LOCKED", ui_report_contract_id="REPORT-1",
        audit_pipeline_id="EIGHT_STEP_AUDIT_V1", experiment_id="EXP-1",
    )
    base.update(kwargs)
    return FullExecutionProfile(**base)


def context(*, sellable=100, pending=500, requested=100, confirmed=True,
            corporate=True, price=Decimal("10000"), venue=Venue.HOSE,
            as_of=NOW, exchange_confirmed=True, exception_reviewed=True):
    return VnRollbackContext(
        venue=venue, symbol="FPT", checked_at_utc=as_of,
        share_availability=VnShareAvailability(
            broker_snapshot_id="BROKER-1", symbol="FPT", venue=venue, observed_at_utc=as_of,
            settled_sellable_qty=sellable, pending_t2_qty=pending,
            restricted_qty=0, requested_sell_qty=requested,
            broker_settlement_confirmation=confirmed,
            corporate_actions_reconciled=corporate,
        ),
        price_rules=VnPriceRuleSnapshot(
            venue=venue, rule_revision_id="VENUE-1", observed_at_utc=as_of,
            floor_vnd=Decimal("9300"), ceiling_vnd=Decimal("10700"),
            tick_vnd=Decimal("100"), proposed_order_price_vnd=price,
            exchange_session_confirmed=exchange_confirmed,
            exceptional_rule_reviewed=exception_reviewed,
        ),
    )


class ProfileContractTests(unittest.TestCase):
    def test_fingerprint_deterministic(self):
        self.assertEqual(profile().fingerprint_sha256, profile().fingerprint_sha256)
        self.assertEqual(len(profile().fingerprint_sha256), 64)

    def test_changed_parameter_changes_fingerprint(self):
        self.assertNotEqual(profile().fingerprint_sha256, profile(parameter_sha256="e" * 64).fingerprint_sha256)

    def test_source_provider_separated(self):
        self.assertNotEqual(profile().fingerprint_sha256, profile(source_provider="DNSE").fingerprint_sha256)

    def test_bad_untyped_sha_rejected(self):
        with self.assertRaises(ValueError):
            profile(parameter_sha256="not-hash")

    def test_ui_cannot_silently_change(self):
        with self.assertRaises(ValueError):
            profile(ui_design_id="UI_2")

    def test_eight_step_contract_locked(self):
        with self.assertRaises(ValueError):
            profile(audit_pipeline_id="SIX_STEP")

    def test_short_horizon_is_not_a_short_sale_right(self):
        self.assertEqual(profile(strategy_id="SHORT").strategy_id, "SHORT")
        with self.assertRaises(ValueError):
            profile(strategy_id="SHORT_SELL")

    def test_reject_secret_like_reference(self):
        with self.assertRaises(ValueError):
            profile(source_revision_id="https://secret.example/?token=abc")


class RollbackPreflightTests(unittest.TestCase):
    def setUp(self):
        self.a = profile()

    def test_no_lkg_claim_blocked(self):
        r = preview_vn_rollback(self.a, None, (RollbackLayer.R1_CODE,), context=context())
        self.assertIn("ROLLBACK_BLOCKED_NO_APPROVED_LKG", r.reasons)
        self.assertEqual(r.state, "SAFE_MODE_ONLY")
        self.assertFalse(r.can_activate)

    def test_parameter_only_scoped_and_invalidates_cache(self):
        target = replace(self.a, parameter_set_id="PARAM-0", parameter_sha256="e" * 64)
        r = preview_vn_rollback(self.a, target, (RollbackLayer.R2_RULE_PARAMS,), context=context())
        self.assertEqual(r.changed_layers, (RollbackLayer.R2_RULE_PARAMS,))
        self.assertTrue(r.invalidate_derived_cache)
        self.assertFalse(r.can_activate)

    def test_report_only_may_roll_back_without_changing_strategy(self):
        old = replace(self.a, ui_report_contract_id="REPORT-0")
        r = preview_vn_rollback(self.a, old, (RollbackLayer.R5_UI_REPORT,), context=context())
        self.assertEqual(r.changed_layers, (RollbackLayer.R5_UI_REPORT,))
        self.assertFalse(r.invalidate_derived_cache)
        self.assertEqual(old.ui_design_id, "UI_1_0_DESIGN_LOCKED")
        self.assertEqual(old.parameter_sha256, self.a.parameter_sha256)

    def test_out_of_scope_change_fails(self):
        target = replace(self.a, source_provider="DNSE")
        r = preview_vn_rollback(self.a, target, (RollbackLayer.R1_CODE,), context=context())
        self.assertIn("OUT_OF_SCOPE_R3_SOURCE_DATA", r.reasons)
        self.assertIn("SOURCE_RIGHTS_AND_REVISION_REQUALIFICATION_REQUIRED", r.reasons)

    def test_schema_change_needs_restore_proof(self):
        target = replace(self.a, cache_schema_id="CACHE-0")
        r = preview_vn_rollback(self.a, target, (RollbackLayer.R4_SCHEMA_CACHE,), context=context())
        self.assertIn("SCHEMA_COMPATIBILITY_AND_RESTORE_UNVERIFIED", r.reasons)
        self.assertTrue(r.invalidate_derived_cache)

    def test_calendar_t2_requires_requalification(self):
        target = replace(self.a, settlement_t2_policy_id="T2-0")
        r = preview_vn_rollback(self.a, target, (RollbackLayer.R6_ACCOUNT_SETTLEMENT,), context=context())
        self.assertIn("VN_SETTLEMENT_CALENDAR_RISK_REQUALIFICATION_REQUIRED", r.reasons)

    def test_pending_t2_not_sellable_even_if_large(self):
        r = preview_vn_rollback(self.a, self.a, (), context=context(sellable=50, pending=500, requested=100))
        self.assertIn("SELL_EXCEEDS_SETTLED_SELLABLE_SHARES", r.reasons)
        self.assertFalse(r.can_place_orders)

    def test_unverified_settlement_blocks_account_action(self):
        r = preview_vn_rollback(self.a, self.a, (), context=context(confirmed=False))
        self.assertIn("T2_SETTLEMENT_NOT_CONFIRMED_BY_BROKER", r.reasons)

    def test_corporate_action_requires_reconciliation(self):
        r = preview_vn_rollback(self.a, self.a, (), context=context(corporate=False))
        self.assertIn("CORPORATE_ACTIONS_NOT_RECONCILED", r.reasons)

    def test_price_outside_band_fails(self):
        r = preview_vn_rollback(self.a, self.a, (), context=context(price=Decimal("11000")))
        self.assertIn("PRICE_OUTSIDE_EXCHANGE_BAND", r.reasons)

    def test_invalid_tick_fails(self):
        r = preview_vn_rollback(self.a, self.a, (), context=context(price=Decimal("10050")))
        self.assertIn("INVALID_TICK_SIZE", r.reasons)

    def test_unknown_venue_rules_fail_closed(self):
        c = context(exchange_confirmed=False, exception_reviewed=False)
        r = preview_vn_rollback(self.a, self.a, (), context=c)
        self.assertIn("VENUE_RULES_NEED_EXTERNAL_CONFIRMATION", r.reasons)

    def test_market_context_cross_venue_rejected(self):
        p = context().price_rules
        with self.assertRaises(ValueError):
            VnRollbackContext(venue=Venue.HNX, symbol="SHS", checked_at_utc=NOW, price_rules=p)

    def test_cross_symbol_broker_snapshot_rejected(self):
        with self.assertRaises(ValueError):
            VnRollbackContext(venue=Venue.HOSE, symbol="SSI", checked_at_utc=NOW,
                share_availability=context().share_availability)

    def test_future_broker_observation_rejected(self):
        with self.assertRaises(ValueError):
            VnRollbackContext(venue=Venue.HOSE, symbol="FPT", checked_at_utc=NOW,
                share_availability=replace(context().share_availability, observed_at_utc=NOW + timedelta(seconds=1)))

    def test_bad_decimal_float_rejected(self):
        with self.assertRaises(ValueError):
            replace(context().price_rules, proposed_order_price_vnd=10000.0)

    def test_unknown_inventory_blocks(self):
        r = preview_vn_rollback(self.a, self.a, (), context=context(sellable=None))
        self.assertIn("BROKER_INVENTORY_PARTIALLY_UNKNOWN", r.reasons)
        self.assertTrue(r.account_reconciliation_required)

    def test_duplicate_layer_rejected(self):
        with self.assertRaises(ValueError):
            preview_vn_rollback(self.a, self.a, (RollbackLayer.R1_CODE, RollbackLayer.R1_CODE))

    def test_no_context_cannot_be_authorized(self):
        r = preview_vn_rollback(self.a, self.a, ())
        self.assertFalse(r.can_activate)
        self.assertIn("VN_MARKET_ACCOUNT_CONTEXT_NOT_VERIFIED", r.reasons)

    def test_no_broker_side_effect_even_when_all_fields_populated(self):
        r = preview_vn_rollback(self.a, replace(self.a, release_id="RC-0"),
                                (RollbackLayer.R7_DOCS_RELEASE,), context=context())
        self.assertEqual(r.state, "SAFE_MODE_ONLY")
        self.assertFalse(r.can_activate)
        self.assertFalse(r.can_place_orders)
        self.assertIn("LKG_INDEPENDENT_APPROVAL_AND_RESTORE_PROOF_UNVERIFIED", r.reasons)


if __name__ == "__main__":
    unittest.main()
