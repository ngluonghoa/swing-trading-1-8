"""P0.13 non-actionable separate SHORT/SWING B5 grid protocol tests."""
import unittest
from dataclasses import replace
from decimal import Decimal

from swing_trading.b5_calibration_draft import (
    B5CalibrationAxis, B5CalibrationGridDraft, B5CalibrationSlot,
    CalibrationDraftState, build_b5_calibration_grid,
)
from swing_trading.b5_formula_geometry import draft_for
from swing_trading.contracts import Strategy


class B5CalibrationGridDraftTests(unittest.TestCase):
    def test_complete_independent_strategy_variant_axis_matrix(self):
        r=build_b5_calibration_grid()
        self.assertEqual(len(r.slots),24)
        self.assertEqual(len(r.protocols),4)
        self.assertEqual(r.state,CalibrationDraftState.PRE_REGISTERED_UNCALIBRATED)
        self.assertFalse(r.approved)
        self.assertFalse(r.executable)
        self.assertFalse(r.actionable)
        for strategy in Strategy:
            for variant in ("B5/E_RECLAIM","B5/E_FAILED_BREAK"):
                subset=[x for x in r.slots if x.strategy is strategy and x.variant_id==variant]
                self.assertEqual({x.axis for x in subset},set(B5CalibrationAxis))
                self.assertEqual(len(subset),6)
                self.assertTrue(all(x.candidate_values is None
                                    and x.calibrated_value is None
                                    and x.parameter_approved is False for x in subset))
                protocol=next(x for x in r.protocols
                              if x.strategy is strategy and x.variant_id==variant)
                self.assertEqual(protocol.formula_version,draft_for(strategy).rule_version)
                self.assertTrue(all(not getattr(protocol,k) for k in (
                    "holdout_selection_frozen", "split_calendar_qualified",
                    "input_source_licensed", "source_history_complete",
                    "first_known_replay_verified",
                    "fill_cost_settlement_simulator_approved",
                    "risk_policy_approved", "oos_executed", "validation_approved",
                )))

    def test_strategies_do_not_share_slot_objects_or_threshold_values(self):
        r=build_b5_calibration_grid()
        a=next(x for x in r.slots if x.strategy is Strategy.SHORT
               and x.variant_id=="B5/E_RECLAIM"
               and x.axis is B5CalibrationAxis.RC_WINDOW_SESSIONS)
        b=next(x for x in r.slots if x.strategy is Strategy.SWING
               and x.variant_id=="B5/E_RECLAIM"
               and x.axis is B5CalibrationAxis.RC_WINDOW_SESSIONS)
        self.assertIsNot(a,b)
        self.assertIsNone(a.candidate_values)
        self.assertIsNone(b.candidate_values)

    def test_tuning_grid_candidate_numeric_injection_refused(self):
        r=build_b5_calibration_grid()
        slot=r.slots[0]
        for candidate in ((Decimal("1"),),(),(Decimal("0.5"),Decimal("1"))):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                replace(slot,candidate_values=candidate)
        with self.assertRaises(ValueError):
            replace(slot,calibrated_value=Decimal("0"))
        with self.assertRaises(ValueError):
            replace(slot,parameter_approved=True)

    def test_axis_unit_must_match_and_rvol_is_explicit(self):
        r=build_b5_calibration_grid()
        for slot in r.slots:
            if slot.axis is B5CalibrationAxis.RC_WINDOW_SESSIONS:
                self.assertEqual(slot.unit,"EXCHANGE_TRADING_SESSIONS")
            elif slot.axis is B5CalibrationAxis.RF_MIN_RVOL:
                self.assertEqual(slot.unit,"RVOL_TOD_OR_APPROVED_RVOL_RATIO")
            else:
                self.assertEqual(slot.unit,"ATR14_D1_MULTIPLE")
        with self.assertRaises(ValueError):
            replace(r.slots[0],unit="DAYS")

    def test_strategy_variant_axis_are_not_strings(self):
        r=build_b5_calibration_grid()
        with self.assertRaises(TypeError):
            replace(r.slots[0],strategy="SHORT")
        with self.assertRaises(ValueError):
            replace(r.slots[0],variant_id="B5/E_OTHER")
        with self.assertRaises(TypeError):
            replace(r.slots[0],axis="RC_WINDOW_SESSIONS")

    def test_duplicate_or_missing_axis_is_rejected(self):
        r=build_b5_calibration_grid()
        with self.assertRaises(ValueError):
            replace(r,slots=r.slots[:-1])
        with self.assertRaises(ValueError):
            replace(r,slots=r.slots[:-1]+(r.slots[0],))
        with self.assertRaises(ValueError):
            replace(r,slots=r.slots+(r.slots[0],))

    def test_unique_protocol_per_strategy_variant_required(self):
        r=build_b5_calibration_grid()
        with self.assertRaises(ValueError):
            replace(r,protocols=r.protocols[:-1])
        with self.assertRaises(ValueError):
            replace(r,protocols=r.protocols[:-1]+(r.protocols[0],))

    def test_protocol_metrics_are_frozen_as_ids_no_phantom_score(self):
        r=build_b5_calibration_grid()
        p=r.protocols[0]
        self.assertIn("FALSE_ALERT_RATE",p.metric_ids)
        self.assertIn("NET_EXPECTANCY_AFTER_COSTS",p.metric_ids)
        self.assertIn("HOLDOUT_STABILITY",p.metric_ids)
        with self.assertRaises(ValueError):
            replace(p,metric_ids=("PROFIT",))

    def test_protocol_cannot_claim_verified_data_or_oos(self):
        p=build_b5_calibration_grid().protocols[0]
        for field in (
            "holdout_selection_frozen", "split_calendar_qualified",
            "input_source_licensed", "source_history_complete",
            "first_known_replay_verified",
            "fill_cost_settlement_simulator_approved",
            "risk_policy_approved", "oos_executed", "validation_approved",
        ):
            with self.subTest(field=field),self.assertRaises(ValueError):
                replace(p,**{field:True})

    def test_grid_cannot_be_approved_or_executable(self):
        r=build_b5_calibration_grid()
        for key in ("approved","executable","actionable"):
            with self.subTest(key=key),self.assertRaises(ValueError):
                replace(r,**{key:True})
        with self.assertRaises(ValueError):
            replace(r,grid_version="B5/P0.14_APPROVED")

    def test_empty_inputs_not_silent_defaults(self):
        r=build_b5_calibration_grid()
        with self.assertRaises(TypeError):
            replace(r,slots=list(r.slots))
        with self.assertRaises(TypeError):
            replace(r,protocols=list(r.protocols))


if __name__=="__main__":
    unittest.main()
