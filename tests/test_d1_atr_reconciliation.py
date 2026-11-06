"""P0.10 synthetic D1 session-inventory and ATR14 incremental/revision tests."""
import unittest
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from swing_trading.d1_atr_reconciliation import (
    ATRReplayAudit, ATRReplayState, D1ExpectedSession, D1SessionInventory,
    SessionAuditState, audit_d1_session_inventory, reconcile_atr14_d1,
)
from swing_trading.market_data import PriceBasis
from swing_trading.source_quality import resolve_as_known, QualityState
from test_causal_indicators import AS_OF, d1, make_bar, snap


OLD_AS_OF = AS_OF - timedelta(hours=1)


def sessions(rows, *, first_known=None):
    return D1SessionInventory(
        "fixture-generated NOT official market sessions",
        "fixture-calendar-v1", "fixture-manifest-r1",
        first_known or (OLD_AS_OF - timedelta(days=1)),
        tuple(D1ExpectedSession(row.market_bar_key.session_period_id,
                                row.market_bar_key.bar_start_utc,
                                row.selected.bar_end_utc) for row in rows),
    )


def adjusted(row, *, known=None, high=Decimal("20"), close=Decimal("19")):
    """A synthetic newer source revision, first-known AFTER old checkpoint."""
    original = row.selected
    first_known = known or OLD_AS_OF + timedelta(minutes=2)
    retrieved = first_known + timedelta(minutes=1)
    verified = retrieved + timedelta(minutes=1)
    revision = replace(
        original.observation_revision,
        source_revision_or_payload_digest="synthetic-correction-" +
                                          original.market_bar_key.session_period_id,
        first_known_time_utc=first_known, retrieved_at_utc=retrieved,
    )
    new = replace(
        original, observation_revision=revision,
        high=high, close=close, retrieved_at_utc=retrieved,
        verified_at_utc=verified,
    )
    return resolve_as_known(new.market_bar_key, (new,), AS_OF)


def evaluate(old, new, inventory=None, *, old_time=OLD_AS_OF, new_time=AS_OF):
    return reconcile_atr14_d1(
        old, new, inventory or sessions(new),
        old_as_of_utc=old_time, as_of_utc=new_time,
    )


class D1SessionInventoryTests(unittest.TestCase):
    def test_exact_slots_match_but_do_not_certify_real_market(self):
        seq = d1(20)
        result = audit_d1_session_inventory(seq, sessions(seq), as_of_utc=AS_OF)
        self.assertEqual(result.state, SessionAuditState.MATCH_UNCERTIFIED)
        self.assertEqual(result.reason, "EXACT_MATCH_TO_UNCERTIFIED_SESSION_INVENTORY")
        self.assertEqual(result.expected_count, 20)
        self.assertEqual(result.actual_count, 20)
        self.assertFalse(result.calendar_certified)
        self.assertFalse(result.actionable)

    def test_missing_session_is_not_silent_smoothing(self):
        seq = d1(20)
        result = audit_d1_session_inventory(
            seq[:7] + seq[8:], sessions(seq), as_of_utc=AS_OF)
        self.assertEqual(result.state, SessionAuditState.BLOCKED)
        self.assertEqual(result.reason, "EXPECTED_SESSION_INVENTORY_DIFFERS")
        self.assertEqual(result.missing_session_ids, ("fixture-session-7",))
        self.assertEqual(result.unexpected_session_ids, ())

    def test_unexpected_session_is_not_a_calendar_proxy(self):
        seq = d1(20)
        result = audit_d1_session_inventory(
            seq, sessions(seq[:-1]), as_of_utc=AS_OF)
        self.assertEqual(result.unexpected_session_ids, ("fixture-session-19",))
        self.assertEqual(result.state, SessionAuditState.BLOCKED)

    def test_mismatched_start_end_fails_even_with_same_session_id(self):
        seq = d1(20)
        inv = sessions(seq)
        slots = list(inv.slots)
        slots[5] = replace(slots[5], start_utc=slots[5].start_utc+timedelta(minutes=1))
        result = audit_d1_session_inventory(
            seq, replace(inv, slots=tuple(slots)), as_of_utc=AS_OF)
        self.assertEqual(result.reason, "SESSION_BOUNDARY_MISMATCH")

    def test_different_calendar_revision_blocks(self):
        seq = d1(20)
        inv = replace(sessions(seq), calendar_version="unknown-calendar-v2")
        result = audit_d1_session_inventory(seq, inv, as_of_utc=AS_OF)
        self.assertEqual(result.reason, "CALENDAR_VERSION_MISMATCH")

    def test_future_manifest_is_not_visible(self):
        seq = d1(20)
        inv = sessions(seq, first_known=AS_OF+timedelta(minutes=1))
        result = audit_d1_session_inventory(seq, inv, as_of_utc=AS_OF)
        self.assertEqual(result.reason, "INVENTORY_NOT_KNOWN_AS_OF")

    def test_duplicate_unsorted_or_overlapping_manifest_rejected(self):
        inv = sessions(d1(20))
        with self.assertRaises(ValueError):
            replace(inv, slots=inv.slots + (inv.slots[-1],))
        bad = replace(inv.slots[-1], session_period_id="fixture-other",
                      start_utc=inv.slots[-2].start_utc)
        with self.assertRaises(ValueError):
            replace(inv, slots=inv.slots[:-1] + (bad,))
        with self.assertRaises(ValueError):
            replace(inv, independently_certified=True)

    def test_partial_or_future_known_source_rejected(self):
        seq = list(d1(20))
        seq[10] = snap(replace(seq[10].selected,
                               quality_state=QualityState.UNVERIFIED))
        result = audit_d1_session_inventory(
            tuple(seq), sessions(d1(20)), as_of_utc=AS_OF)
        self.assertEqual(result.state, SessionAuditState.BLOCKED)
        self.assertIn("SOURCE_HISTORY_", result.reason)

    def test_wrong_input_and_utc_not_silently_fixed(self):
        seq=d1(20)
        with self.assertRaises(TypeError):
            audit_d1_session_inventory(seq, "fixture", as_of_utc=AS_OF)
        with self.assertRaises(ValueError):
            audit_d1_session_inventory(seq, sessions(seq),
                                      as_of_utc=AS_OF.replace(tzinfo=None))
        with self.assertRaises(TypeError):
            replace(sessions(seq), slots=(seq[0],))


class ATR14ReplayTests(unittest.TestCase):
    def test_idempotent_replay_requires_no_work(self):
        rows = d1(21)
        r = evaluate(rows, rows)
        self.assertEqual(r.state, ATRReplayState.PARITY_UNCERTIFIED)
        self.assertEqual(r.first_dirty_index, None)
        self.assertEqual(r.replay_from_index, None)
        self.assertEqual(r.replayed_true_ranges, 0)
        self.assertEqual(r.old_atr, r.replay_atr)
        self.assertEqual(r.batch_atr, r.replay_atr)
        self.assertFalse(r.source_certified)
        self.assertFalse(r.actionable)

    def test_append_only_reuses_last_good_checkpoint(self):
        rows = d1(21)
        out = evaluate(rows[:20], rows)
        self.assertEqual(out.state, ATRReplayState.PARITY_UNCERTIFIED)
        self.assertEqual(out.first_dirty_index, 20)
        self.assertEqual(out.replay_from_index, 20)
        self.assertEqual(out.replayed_true_ranges, 1)
        self.assertEqual(out.batch_atr, out.replay_atr)

    def test_early_close_correction_rewinds_to_seed(self):
        old = d1(21)
        current = list(old)
        current[8] = adjusted(current[8])
        result = evaluate(old, tuple(current))
        self.assertEqual(result.state, ATRReplayState.PARITY_UNCERTIFIED)
        self.assertEqual(result.first_dirty_index, 8)
        self.assertEqual(result.replay_from_index, 0)
        self.assertEqual(result.replayed_true_ranges, 20)
        self.assertNotEqual(result.old_atr, result.batch_atr)
        self.assertEqual(result.batch_atr, result.replay_atr)

    def test_post_seed_close_correction_replays_from_dirty_bar(self):
        old = d1(21)
        current = list(old)
        current[17] = adjusted(current[17])
        result = evaluate(old, tuple(current))
        self.assertEqual(result.state, ATRReplayState.PARITY_UNCERTIFIED)
        self.assertEqual(result.first_dirty_index, 17)
        self.assertEqual(result.replay_from_index, 17)
        self.assertEqual(result.replayed_true_ranges, 4)
        self.assertNotEqual(result.old_atr, result.batch_atr)
        self.assertEqual(result.batch_atr, result.replay_atr)

    def test_first_post_seed_bar_replay_exact(self):
        old = d1(21)
        current = list(old)
        current[15] = adjusted(current[15])
        r = evaluate(old, tuple(current))
        self.assertEqual(r.first_dirty_index, 15)
        self.assertEqual(r.replay_from_index, 15)
        self.assertEqual(r.batch_atr, r.replay_atr)

    def test_revision_with_pre_existing_knowledge_fails_closed(self):
        old = d1(21)
        current = list(old)
        current[17] = adjusted(current[17],
                               known=OLD_AS_OF - timedelta(minutes=10))
        r = evaluate(old, tuple(current))
        self.assertEqual(r.state, ATRReplayState.BLOCKED)
        self.assertEqual(r.reason, "CORRECTION_WAS_ALREADY_KNOWN_AT_CHECKPOINT")

    def test_late_correction_not_visible_to_current_asof_blocks(self):
        old = d1(21)
        current = list(old)
        later = AS_OF + timedelta(minutes=10)
        current[17] = adjusted(current[17], known=later)
        # resolve_as_known returns no visible revision at the requested time.
        r = evaluate(old, tuple(current), inventory=sessions(old))
        self.assertEqual(r.state, ATRReplayState.BLOCKED)
        self.assertTrue(r.reason.startswith("CURRENT_HISTORY_"))

    def test_revision_conflict_blocks_no_silent_latest(self):
        old = d1(21)
        current = list(old)
        updated = adjusted(current[16])
        original = current[16].selected
        newer = updated.selected
        current[16] = resolve_as_known(
            original.market_bar_key, (original, newer), AS_OF)
        r = evaluate(old, tuple(current), inventory=sessions(old))
        self.assertEqual(r.state, ATRReplayState.BLOCKED)
        self.assertTrue(r.reason.startswith("CURRENT_HISTORY_"))

    def test_missing_session_blocks_replay_even_with_15_bars(self):
        old = d1(21)
        current = old[:3] + old[4:]
        r = evaluate(old[:20], current, inventory=sessions(old))
        self.assertEqual(r.state, ATRReplayState.BLOCKED)
        self.assertIn("EXPECTED_SESSION_INVENTORY_DIFFERS", r.reason)

    def test_truncated_history_cannot_continue_checkpoint(self):
        old = d1(21)
        r = evaluate(old, old[:-1], inventory=sessions(old))
        self.assertEqual(r.reason,
                         "HISTORY_TRUNCATION_REQUIRES_INDEPENDENT_RESEED")

    def test_source_or_adjustment_rebase_requires_reseed(self):
        old = d1(21)
        new = []
        for snap0 in old:
            bar = snap0.selected
            revised = replace(bar.observation_revision,
                              adjustment_revision="rebase-v2")
            new.append(snap(replace(bar, observation_revision=revised)))
        r = evaluate(old, tuple(new))
        self.assertEqual(r.state, ATRReplayState.BLOCKED)
        self.assertEqual(r.reason,
                         "SOURCE_OR_ADJUSTMENT_POLICY_CHANGED_RESEED_REQUIRED")

    def test_mixed_price_basis_blocks_instead_of_converting(self):
        old=d1(21)
        new=list(old)
        c=new[12].selected
        k=replace(c.market_bar_key, price_basis=PriceBasis.ADJUSTED)
        o=replace(c.observation_key, market_bar_key=k)
        v=replace(c.observation_revision, observation_key=o)
        changed=replace(c, market_bar_key=k, observation_key=o,
                        observation_revision=v)
        new[12]=snap(changed)
        r=evaluate(old,tuple(new))
        self.assertEqual(r.state,ATRReplayState.BLOCKED)

    def test_old_checkpoint_must_be_source_qualified_at_old_clock(self):
        old=list(d1(21))
        c=old[4].selected
        old[4]=snap(replace(c, verified_at_utc=AS_OF-timedelta(minutes=10)))
        r=evaluate(tuple(old),d1(21))
        self.assertEqual(r.state,ATRReplayState.BLOCKED)
        self.assertTrue(r.reason.startswith("OLD_HISTORY_"))

    def test_manifest_must_be_known_at_old_checkpoint(self):
        seq=d1(21)
        inv=sessions(seq,first_known=OLD_AS_OF+timedelta(minutes=1))
        r=evaluate(seq,seq,inventory=inv)
        self.assertEqual(r.reason,"SESSION_INVENTORY_NOT_KNOWN_AT_CHECKPOINT")

    def test_out_of_order_asof_and_unapproved_state(self):
        seq=d1(21)
        r=evaluate(seq,seq,old_time=AS_OF,new_time=OLD_AS_OF)
        self.assertEqual(r.reason,"AS_OF_CLOCK_MOVED_BACKWARDS")
        with self.assertRaises(ValueError):
            ATRReplayAudit(ATRReplayState.PARITY_UNCERTIFIED,"fixture",
                           Decimal(1),Decimal(1),Decimal(1),
                           None,None,0,source_certified=True)
        with self.assertRaises(ValueError):
            evaluate(seq,seq,new_time=AS_OF.replace(tzinfo=None))


if __name__=="__main__":
    unittest.main()
