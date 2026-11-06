"""Synthetic P0.14 B5 chronology, label purge and embargo tests."""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from swing_trading.b5_temporal_split_audit import (
    B5Fold, SessionFold, B5SplitCandidate, B5LabelFootprint,
    SplitAuditState, audit_b5_temporal_split,
)
from swing_trading.contracts import Strategy
from swing_trading.d1_atr_reconciliation import (
    D1SessionInventory, D1ExpectedSession,
)


UTC=timezone.utc
AUDIT_ASOF=datetime(2026,11,6,10,0,tzinfo=UTC)
START=datetime(2026,6,1,2,0,tzinfo=UTC)


def calendar(n=80):
    return D1SessionInventory(
        "synthetic NOT official exchange calendar","fixture-clock-v1",
        "fixture-calendar-rev1",START-timedelta(days=1),
        tuple(D1ExpectedSession(
            "s"+str(i),START+timedelta(days=i),
            START+timedelta(days=i,hours=6)) for i in range(n)),
    )


def plan(strategy=Strategy.SHORT, variant="B5/E_RECLAIM",
         embargo=3, max_span=10):
    return B5SplitCandidate(
        strategy,variant,calendar(),
        SessionFold(B5Fold.TRAIN,0,20),
        SessionFold(B5Fold.VALIDATION,23,40),
        SessionFold(B5Fold.HOLDOUT,43,60),
        embargo,max_span,"synthetic-sha-1","label-policy-draft-v1",
    )


def event(pl,name,decision,label_end,**changes):
    slots=pl.calendar.slots
    payload=dict(
        event_id=name,strategy=pl.strategy,variant_id=pl.variant_id,
        decision_session_id=slots[decision].session_period_id,
        label_end_session_id=slots[label_end].session_period_id,
        first_known_time_utc=slots[decision].end_utc,
        label_first_known_utc=slots[label_end].end_utc,
        source_revision="synthetic-first-known-v1",
        label_policy_version=pl.label_policy_version,
    )
    payload.update(changes)
    return B5LabelFootprint(**payload)


def records(pl):
    return (event(pl,"train",9,12),event(pl,"validation",26,29),
            event(pl,"holdout",47,50))


def inspect(pl=None,rows=None):
    pl=pl or plan()
    return audit_b5_temporal_split(pl, records(pl) if rows is None else rows,
                                   as_of_utc=AUDIT_ASOF)


class B5TemporalAuditTests(unittest.TestCase):
    def test_properly_separated_short_is_still_uncertified(self):
        p=plan()
        r=inspect(p)
        self.assertEqual(r.state,SplitAuditState.STRUCTURALLY_SEPARATED_UNCERTIFIED)
        self.assertEqual((r.train_count,r.validation_count,r.holdout_count),(1,1,1))
        self.assertEqual(r.violations,())
        self.assertFalse(r.trading_calendar_certified)
        self.assertFalse(r.source_licence_verified)
        self.assertFalse(r.holdout_unsealed)
        self.assertFalse(r.threshold_approved)
        self.assertFalse(r.historical_backtest_run)
        self.assertFalse(r.actionable)

    def test_swing_has_its_own_candidate_split_and_long_label_span(self):
        p=plan(Strategy.SWING,variant="B5/E_FAILED_BREAK",max_span=60)
        rows=(event(p,"train",0,21),event(p,"val",23,32),
              event(p,"holdout",43,55))
        r=inspect(p,rows)
        self.assertEqual(r.state,SplitAuditState.STRUCTURALLY_SEPARATED_UNCERTIFIED)
        self.assertEqual(r.variant_id,"B5/E_FAILED_BREAK")
        self.assertEqual(r.strategy,Strategy.SWING)
        self.assertFalse(r.actionable)

    def test_train_label_overlaps_validation_is_blocked_even_with_embargo(self):
        p=plan()
        rows=(event(p,"train",18,24),)+records(p)[1:]
        r=inspect(p,rows)
        self.assertIn(("train","TRAIN_LABEL_LEAKS_INTO_VALIDATION"),r.violations)
        self.assertEqual(r.state,SplitAuditState.BLOCKED)

    def test_validation_label_overlaps_holdout(self):
        p=plan()
        rows=(records(p)[0],event(p,"validation",38,44),records(p)[2])
        r=inspect(p,rows)
        self.assertIn(("validation","VALIDATION_LABEL_LEAKS_INTO_HOLDOUT"),r.violations)

    def test_future_feature_revision_at_decision_is_rejected(self):
        p=plan()
        base=records(p)
        changed=replace(base[0],first_known_time_utc=
                        p.calendar.slots[9].end_utc+timedelta(minutes=1))
        r=inspect(p,(changed,)+base[1:])
        self.assertIn(("train","FEATURE_REVISION_NOT_KNOWN_AT_DECISION"),r.violations)

    def test_label_cannot_be_known_before_its_horizon(self):
        p=plan()
        base=records(p)
        changed=replace(base[1],label_first_known_utc=
                        p.calendar.slots[29].end_utc-timedelta(minutes=1))
        r=inspect(p,(base[0],changed,base[2]))
        self.assertIn(("validation","LABEL_KNOWN_BEFORE_ITS_HORIZON_CLOSED"),r.violations)

    def test_holdout_label_cannot_extend_beyond_holdout(self):
        p=plan(max_span=60)
        rows=records(p)[:2]+(event(p,"holdout",58,62),)
        r=inspect(p,rows)
        self.assertIn(("holdout","HOLDOUT_LABEL_AFTER_WINDOW"),r.violations)

    def test_zero_or_excessive_label_horizon(self):
        p=plan()
        base=records(p)
        zero=event(p,"train",9,9)
        r=inspect(p,(zero,)+base[1:])
        self.assertIn(("train","LABEL_MUST_EXTEND_AFTER_DECISION"),r.violations)
        huge=event(p,"train",0,21)
        r=inspect(p,(huge,)+base[1:])
        self.assertIn(("train","LABEL_SPAN_EXCEEDS_DECLARED_CAP"),r.violations)

    def test_insufficient_embargo_gaps_are_blocked(self):
        p=plan(embargo=4)
        r=inspect(p)
        self.assertEqual(r.reason,"REQUIRED_EMBARGO_GAP_NOT_PROVIDED")

    def test_overlapping_scoring_windows_blocked(self):
        p=plan()
        p=replace(p,validation=SessionFold(B5Fold.VALIDATION,19,40))
        self.assertEqual(inspect(p).reason,"FOLD_OVERLAP_OR_OUTSIDE_MANIFEST")

    def test_event_during_embargo_cannot_be_scored(self):
        p=plan()
        row=event(p,"in-gap",21,24)
        result=inspect(p,records(p)+(row,))
        self.assertIn(("in-gap","EVENT_IN_EMBARGO_OR_OUTSIDE_SCORING_FOLD"),
                      result.violations)

    def test_duplicate_event_ids_are_rejected(self):
        p=plan()
        src=records(p)
        result=inspect(p,src+(replace(src[0]),))
        self.assertIn(("train","DUPLICATE_EVENT_ID"),result.violations)

    def test_event_order_is_explicit_not_silently_sorted(self):
        p=plan()
        r=inspect(p,tuple(reversed(records(p))))
        self.assertTrue(any(x[1]=="EVENTS_NOT_CHRONOLOGICALLY_SORTED"
                            for x in r.violations))

    def test_cross_strategy_or_variant_inputs_are_rejected(self):
        p=plan()
        row=replace(records(p)[1],strategy=Strategy.SWING)
        r=inspect(p,(records(p)[0],row,records(p)[2]))
        self.assertIn(("validation","OTHER_STRATEGY_OR_VARIANT_EVENT"),r.violations)
        row=replace(records(p)[1],variant_id="B5/E_FAILED_BREAK")
        r=inspect(p,(records(p)[0],row,records(p)[2]))
        self.assertIn(("validation","OTHER_STRATEGY_OR_VARIANT_EVENT"),r.violations)

    def test_wrong_label_policy_or_missing_session(self):
        p=plan()
        x=replace(records(p)[0],label_policy_version="unknown")
        self.assertIn(("train","LABEL_POLICY_VERSION_MISMATCH"),
                      inspect(p,(x,)+records(p)[1:]).violations)
        x=replace(records(p)[0],decision_session_id="missing")
        self.assertIn(("train","EVENT_SESSION_MISSING_FROM_MANIFEST"),
                      inspect(p,(x,)+records(p)[1:]).violations)

    def test_require_events_from_each_fold(self):
        p=plan()
        r=inspect(p,records(p)[:-1])
        self.assertEqual(r.reason,"REQUIRE_OBSERVED_EVENTS_IN_EACH_FOLD")
        self.assertEqual(inspect(p,()).state,SplitAuditState.BLOCKED)

    def test_manifest_not_known_at_audit_clock(self):
        p=plan()
        p=replace(p,calendar=replace(p.calendar,first_known_time_utc=
                   AUDIT_ASOF+timedelta(minutes=1)))
        self.assertEqual(inspect(p).reason,"CALENDAR_MANIFEST_NOT_KNOWN_AT_AUDIT_ASOF")

    def test_label_learned_only_after_audit_clock_rejected(self):
        p=plan()
        x=replace(records(p)[1],label_first_known_utc=AUDIT_ASOF+timedelta(days=1))
        r=inspect(p,(records(p)[0],x,records(p)[2]))
        self.assertIn(("validation","EVENT_OR_LABEL_NOT_KNOWN_AT_AUDIT_ASOF"),r.violations)

    def test_no_forged_approval_or_false_type(self):
        p=plan()
        for field in ("calendar_certified","source_licensed",
                      "holdout_frozen","approved"):
            with self.subTest(field=field),self.assertRaises(ValueError):
                replace(p,**{field:True})
        with self.assertRaises(ValueError):
            replace(p,embargo_sessions=True)
        with self.assertRaises(ValueError):
            replace(p,max_observed_label_span_sessions=0)
        with self.assertRaises(ValueError):
            replace(p,split_version="APPROVED")
        with self.assertRaises(ValueError):
            replace(inspect(p),historical_backtest_run=True)
        with self.assertRaises(ValueError):
            replace(inspect(p),holdout_unsealed=True)

    def test_unsupported_input_type_and_naive_clock(self):
        p=plan()
        with self.assertRaises(TypeError):
            audit_b5_temporal_split(p,list(records(p)),as_of_utc=AUDIT_ASOF)
        with self.assertRaises(TypeError):
            audit_b5_temporal_split("plan",records(p),as_of_utc=AUDIT_ASOF)
        with self.assertRaises(ValueError):
            audit_b5_temporal_split(p,records(p),as_of_utc=AUDIT_ASOF.replace(tzinfo=None))


if __name__=="__main__":
    unittest.main()
