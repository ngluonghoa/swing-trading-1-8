"""REL-F1: synthetic rollback plans preserve current protected-state identities."""
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
import unittest

from release_fixtures import T0, UI, SCHEMAS, bundle, digest, manifest, retained
from swing_trading.release_manifest import Component, ManifestRejected, StateKind, StateReader
from swing_trading.rollback_preflight import (
    RetainedStateMetadata, RetainedStatePin, RollbackBlocker, plan_engineering_rollback,
)


class RollbackPreflightTests(unittest.TestCase):
    def setUp(self):
        self.target, self.target_blob = manifest(1)
        self.current, self.current_blob = manifest(2, rollback=self.target.manifest_sha256())
        self.state = retained(self.current)

    def plan(self, *, current=None, target=None, state=None, current_blob=None,
             target_blob=None, expected_state=None, ui=UI, now=None):
        current = self.current if current is None else current
        target = self.target if target is None else target
        state = self.state if state is None else state
        return plan_engineering_rollback(
            bundle(current, self.current_blob if current_blob is None else current_blob),
            bundle(target, self.target_blob if target_blob is None else target_blob), state,
            expected_retained_metadata_sha256=state.metadata_sha256() if expected_state is None else expected_state,
            locked_ui_spec_sha256=ui, checked_at_utc=T0 + timedelta(minutes=4) if now is None else now,
        )

    def codes(self, result):
        return tuple(f.blocker for f in result.findings)

    def test_compatible_metadata_is_only_review_required_not_execution(self):
        result = self.plan()
        self.assertEqual(result.disposition, "METADATA_COMPATIBLE_REVIEW_REQUIRED")
        self.assertEqual(result.findings, ())
        self.assertEqual(result.current_manifest_sha256, self.current.manifest_sha256())
        self.assertEqual(result.target_manifest_sha256, self.target.manifest_sha256())
        self.assertFalse(hasattr(result, "approved"))
        self.assertFalse(hasattr(result, "execute"))

    def test_current_market_audit_custody_and_position_snapshots_preserved_exactly(self):
        result = self.plan()
        self.assertEqual(result.preserve_states, self.state.states)
        self.assertEqual(result.retained_metadata_sha256, self.state.metadata_sha256())
        self.assertEqual(tuple(p.state_kind for p in result.preserve_states), tuple(StateKind))

    def test_no_target_history_is_substituted_for_current_state(self):
        result = self.plan()
        self.assertEqual(tuple(p.snapshot_sha256 for p in result.preserve_states),
                         tuple(p.snapshot_sha256 for p in self.state.states))
        self.assertNotIn(self.target.artifact.content_sha256,
                         tuple(p.snapshot_sha256 for p in result.preserve_states))

    def test_target_bundle_cannot_be_selected_by_label_without_exact_pin(self):
        result = self.plan(current=replace(self.current, rollback_target_manifest_sha256=None))
        self.assertIn(RollbackBlocker.TARGET_NOT_PINNED, self.codes(result))
        self.assertEqual(result.disposition, "BLOCKED")

    def test_same_release_id_with_changed_versions_is_not_a_previous_release(self):
        target = replace(self.target, release_id=self.current.release_id)
        current = replace(self.current, rollback_target_manifest_sha256=target.manifest_sha256())
        self.assertIn(RollbackBlocker.SAME_RELEASE_ID, self.codes(self.plan(current=current, target=target)))

    def test_changed_target_metadata_invalidates_current_rollback_pin(self):
        target = replace(self.target, release_version="1.8.0-dev.99")
        self.assertIn(RollbackBlocker.TARGET_NOT_PINNED, self.codes(self.plan(target=target)))

    def test_target_component_set_is_returned_without_mixing_current_parameters(self):
        pins = tuple(replace(p, content_sha256=digest("NEW_PARAMETERS"))
                     if p.component is Component.PARAMETER_SET else p for p in self.current.components)
        current = replace(self.current, components=pins)
        result = self.plan(current=current, state=retained(current))
        self.assertEqual(result.target_component_pins, self.target.components)
        self.assertNotEqual(result.target_component_pins, current.components)

    def test_old_release_without_current_custody_format_is_blocked(self):
        newer_schema = digest("CUSTODY_FORMAT_V2")
        readers = tuple(replace(r, schema_sha256s=tuple(sorted((*r.schema_sha256s, newer_schema))))
                        if r.state_kind is StateKind.CUSTODY_FLOOR else r for r in self.current.state_readers)
        current = replace(self.current, state_readers=readers)
        state = retained(current, schema_overrides={StateKind.CUSTODY_FLOOR: newer_schema})
        result = self.plan(current=current, state=state)
        self.assertEqual(result.disposition, "BLOCKED")
        self.assertTrue(any(f.blocker is RollbackBlocker.TARGET_STATE_UNREADABLE
                            and f.state_kind is StateKind.CUSTODY_FLOOR for f in result.findings))
        self.assertEqual(result.preserve_states, state.states)

    def test_each_protected_state_schema_needs_explicit_target_reader(self):
        for kind in StateKind:
            with self.subTest(kind=kind):
                newer = digest("new-schema-" + kind.value)
                readers = tuple(replace(r, schema_sha256s=tuple(sorted((*r.schema_sha256s, newer))))
                                if r.state_kind is kind else r for r in self.current.state_readers)
                current = replace(self.current, state_readers=readers)
                state = retained(current, schema_overrides={kind: newer})
                result = self.plan(current=current, state=state)
                self.assertTrue(any(f.blocker is RollbackBlocker.TARGET_STATE_UNREADABLE
                                    and f.state_kind is kind for f in result.findings))

    def test_explicit_old_reader_of_retained_new_format_may_plan_without_downgrade(self):
        newer = digest("NEW_CUSTODY_FORMAT")
        both = tuple(replace(r, schema_sha256s=tuple(sorted((*r.schema_sha256s, newer))))
                     if r.state_kind is StateKind.CUSTODY_FLOOR else r for r in self.target.state_readers)
        target = replace(self.target, state_readers=both)
        current = replace(self.current, state_readers=both,
                          rollback_target_manifest_sha256=target.manifest_sha256())
        state = retained(current, schema_overrides={StateKind.CUSTODY_FLOOR: newer})
        result = self.plan(current=current, target=target, state=state)
        self.assertEqual(result.disposition, "METADATA_COMPATIBLE_REVIEW_REQUIRED")
        self.assertEqual(result.preserve_states, state.states)

    def test_unreadable_current_state_blocks_even_when_target_can_read_it(self):
        newer = digest("UNRECOGNIZED_CURRENT_FORMAT")
        readers = tuple(replace(r, schema_sha256s=tuple(sorted((*r.schema_sha256s, newer))))
                        if r.state_kind is StateKind.AUDIT_HISTORY else r for r in self.target.state_readers)
        target = replace(self.target, state_readers=readers)
        current = replace(self.current, rollback_target_manifest_sha256=target.manifest_sha256())
        state = retained(current, schema_overrides={StateKind.AUDIT_HISTORY: newer})
        result = self.plan(current=current, target=target, state=state)
        self.assertTrue(any(f.blocker is RollbackBlocker.CURRENT_STATE_UNREADABLE
                            and f.state_kind is StateKind.AUDIT_HISTORY for f in result.findings))

    def test_schema_mismatch_never_offers_restore_or_drop_security_state(self):
        state = retained(self.current, schema_overrides={StateKind.CUSTODY_FLOOR: digest("unknown")})
        result = self.plan(state=state)
        self.assertEqual(result.disposition, "BLOCKED")
        self.assertEqual(result.preserve_states, state.states)
        self.assertFalse(hasattr(result, "restore_backup"))
        self.assertFalse(hasattr(result, "clear_hold"))

    def test_cache_namespace_changes_across_release_even_with_same_component_labels(self):
        result = self.plan()
        self.assertTrue(result.cache_rebuild_required)
        self.assertEqual(result.target_cache_namespace_sha256, self.target.cache_namespace_sha256())
        self.assertNotEqual(result.target_cache_namespace_sha256, self.state.current_cache_namespace_sha256)

    def test_cache_from_wrong_release_is_not_treated_as_current(self):
        state = replace(self.state, current_cache_namespace_sha256=self.target.cache_namespace_sha256())
        self.assertIn(RollbackBlocker.CACHE_NAMESPACE_MISMATCH, self.codes(self.plan(state=state)))

    def test_both_ui_pins_must_match_the_supplied_locked_spec(self):
        self.assertIn(RollbackBlocker.LOCKED_UI_MISMATCH, self.codes(self.plan(ui=digest("wrong-ui"))))
        for which in ("current", "target"):
            with self.subTest(which=which):
                m = getattr(self, which)
                pins = tuple(replace(p, content_sha256=digest("drifted-ui"))
                             if p.component is Component.UI_TEMPLATE else p for p in m.components)
                changed = replace(m, components=pins)
                result = self.plan(**{which: changed, "state": retained(changed)}) if which == "current" else self.plan(target=changed)
                self.assertIn(RollbackBlocker.LOCKED_UI_MISMATCH, self.codes(result))

    def test_future_target_current_or_retained_clock_is_blocked(self):
        future_target = replace(self.target, created_at_utc=T0 + timedelta(minutes=5))
        current = replace(self.current, rollback_target_manifest_sha256=future_target.manifest_sha256())
        self.assertIn(RollbackBlocker.INVALID_CHRONOLOGY,
                      self.codes(self.plan(current=current, target=future_target, state=retained(current))))
        self.assertIn(RollbackBlocker.INVALID_CHRONOLOGY,
                      self.codes(self.plan(now=T0 + timedelta(minutes=2))))
        older = replace(self.state, observed_at_utc=T0)
        self.assertIn(RollbackBlocker.INVALID_CHRONOLOGY, self.codes(self.plan(state=older)))

    def test_changed_preserved_snapshot_rejected_against_original_state_pin(self):
        pins = tuple(replace(p, snapshot_sha256=digest("OLD_RESTORED_FLOOR"))
                     if p.state_kind is StateKind.CUSTODY_FLOOR else p for p in self.state.states)
        changed = replace(self.state, states=pins)
        with self.assertRaises(ManifestRejected):
            self.plan(state=changed, expected_state=self.state.metadata_sha256())

    def test_incomplete_untyped_or_duplicate_protected_state_is_rejected(self):
        for bad in (self.state.states[:-1], tuple(reversed(self.state.states)),
                    (self.state.states[0],) * 4, list(self.state.states)):
            with self.assertRaises(ManifestRejected):
                replace(self.state, states=bad)
        with self.assertRaises(TypeError):
            plan_engineering_rollback(None, None, {}, expected_retained_metadata_sha256="a" * 64,
                                      locked_ui_spec_sha256=UI, checked_at_utc=T0)

    def test_absent_positions_are_not_inferred_as_flat(self):
        states = tuple(p for p in self.state.states if p.state_kind is not StateKind.POSITION_CONTEXT)
        with self.assertRaises(ManifestRejected):
            replace(self.state, states=states)

    def test_artifact_integrity_failure_stops_before_plan(self):
        with self.assertRaises(ManifestRejected):
            self.plan(target_blob=self.target_blob + b"tampered")
        with self.assertRaises(ManifestRejected):
            self.plan(current_blob=self.current_blob + b"tampered")

    def test_missing_pin_arguments_cannot_default_to_self_approval(self):
        with self.assertRaises(TypeError):
            plan_engineering_rollback(bundle(self.current, self.current_blob),
                                      bundle(self.target, self.target_blob), self.state)

    def test_repeated_planning_is_deterministic_without_mutating_retained_state(self):
        original = self.state.metadata_sha256()
        self.assertEqual(self.plan(), self.plan())
        self.assertEqual(self.state.metadata_sha256(), original)
        self.assertEqual(self.current.rollback_target_manifest_sha256, self.target.manifest_sha256())

    def test_report_and_preserved_state_are_immutable(self):
        result = self.plan()
        with self.assertRaises(FrozenInstanceError):
            result.preserve_states = ()
        with self.assertRaises(FrozenInstanceError):
            result.preserve_states[0].snapshot_sha256 = digest("old")
        with self.assertRaises(TypeError):
            replace(result, approved=True)


if __name__ == "__main__":
    unittest.main()
