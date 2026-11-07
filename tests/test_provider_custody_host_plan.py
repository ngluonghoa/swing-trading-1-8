"""GĐ4/P0.29b synthetic-only host onboarding and witnessed floor fixtures.

No real provider keys, actual rights, market data, or host attestation.
"""
import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

from swing_trading.provider_head_custody import ClaimedMonotonicFloor, CustodyProduct
from swing_trading.provider_custody_host_plan import (
    ClaimedExternalEvidence, ClaimedHostControl, ClaimedIndependentAnchor,
    EvidenceRole, ExternalOnboardingReport, FixtureFloorRecord, HostControl,
    HostPreflightRejected, append_fixture_floor, inspect_external_onboarding,
    inspect_fixture_floor_history, require_external_trust,
)

NOW = datetime(2026, 11, 7, 4, 0, tzinfo=timezone.utc)
P = CustodyProduct.SSI_FASTCONNECT_OHLC
Q = CustodyProduct.DNSE_OPENAPI_OHLC
ACCOUNT = 'a'*64
KEY = 'b'*64
TAIL = 'c'*64


def evidence(role, *, product=P, index=1, actor=None, recorded=None, expires=None):
    return ClaimedExternalEvidence(
        product, role, f'EVID-2026R{index:06d}',actor or f'ACTR-2026R{index:06d}',
        recorded or NOW-timedelta(minutes=10),expires or NOW+timedelta(hours=1))


def control(kind, *, index=1, present=True):
    return ClaimedHostControl(kind,f'EVID-2026H{index:06d}',f'ACTR-2026H{index:06d}',present)


def all_evidence():
    return tuple(evidence(role,index=i) for i,role in enumerate(EvidenceRole,1))


def all_controls():
    return tuple(control(c,index=i) for i,c in enumerate(HostControl,1))


def floor(*,product=P, account=ACCOUNT, sequence=1, tail=TAIL, key=KEY,
          epoch=1, issued=None, observed=None):
    return ClaimedMonotonicFloor(product,'KEY-2026TESTKEY',key,epoch,sequence,
        tail,account,issued or NOW-timedelta(minutes=2),
        observed or NOW,'EVID-2026FLOOR01')


def anchor(rec):
    return ClaimedIndependentAnchor(rec.product,rec.account_binding_sha256_claim,
        rec.index,rec.record_sha256,'EVID-2026WITNESS1')


class OnboardingEvidenceTests(unittest.TestCase):
    def test_missing_all_yields_denied_plan(self):
        report=inspect_external_onboarding(P,(),(),checked_at_utc=NOW)
        self.assertEqual(len(report.missing_roles),6)
        self.assertEqual(len(report.missing_controls),9)
        self.assertFalse(report.vendor_key_origin_verified)

    def test_complete_claims_are_still_denied(self):
        report=inspect_external_onboarding(P,all_evidence(),all_controls(),checked_at_utc=NOW)
        self.assertEqual(report.missing_roles,())
        self.assertEqual(report.missing_controls,())
        self.assertFalse(report.secure_host_approved)
        self.assertFalse(report.fresh_revocation_stream_authenticated)
        self.assertFalse(report.rights_to_read_or_cache)
        self.assertFalse(report.trading_actionable)
        with self.assertRaises(PermissionError): require_external_trust(report)

    def test_partial_inventory_preserves_specific_missing_gates(self):
        report=inspect_external_onboarding(P,(evidence(EvidenceRole.PROVIDER_KEY_ISSUER),),
            (control(HostControl.NO_SYMLINK_OR_REPARSE),),checked_at_utc=NOW)
        self.assertNotIn(EvidenceRole.PROVIDER_KEY_ISSUER,report.missing_roles)
        self.assertIn(EvidenceRole.INDEPENDENT_HEAD_CUSTODIAN,report.missing_roles)
        self.assertIn(HostControl.ATOMIC_FSYNC_AND_LOCKING,report.missing_controls)

    def test_host_control_false_is_missing(self):
        report=inspect_external_onboarding(P,(),(control(HostControl.NO_SYMLINK_OR_REPARSE,present=False),),checked_at_utc=NOW)
        self.assertIn(HostControl.NO_SYMLINK_OR_REPARSE,report.missing_controls)

    def test_role_actor_separation(self):
        roles=(evidence(EvidenceRole.PROVIDER_KEY_ISSUER,index=1),
               evidence(EvidenceRole.INDEPENDENT_HEAD_CUSTODIAN,index=2,actor='ACTR-2026R000001'))
        with self.assertRaises(HostPreflightRejected):
            inspect_external_onboarding(P,roles,(),checked_at_utc=NOW)

    def test_duplicate_role(self):
        roles=(evidence(EvidenceRole.PROVIDER_KEY_ISSUER,index=1),evidence(EvidenceRole.PROVIDER_KEY_ISSUER,index=2))
        with self.assertRaises(HostPreflightRejected):inspect_external_onboarding(P,roles,(),checked_at_utc=NOW)

    def test_cross_product_role(self):
        with self.assertRaises(HostPreflightRejected):
            inspect_external_onboarding(P,(evidence(EvidenceRole.PROVIDER_KEY_ISSUER,product=Q),),(),checked_at_utc=NOW)

    def test_duplicate_evidence_id(self):
        one=evidence(EvidenceRole.PROVIDER_KEY_ISSUER)
        two=replace(evidence(EvidenceRole.INDEPENDENT_HEAD_CUSTODIAN,index=2),evidence_id=one.evidence_id)
        with self.assertRaises(HostPreflightRejected):
            inspect_external_onboarding(P,(one,two),(),checked_at_utc=NOW)

    def test_future_role_document(self):
        one=evidence(EvidenceRole.PROVIDER_KEY_ISSUER,recorded=NOW+timedelta(seconds=1))
        with self.assertRaises(HostPreflightRejected):inspect_external_onboarding(P,(one,),(),checked_at_utc=NOW)

    def test_expired_document(self):
        one=evidence(EvidenceRole.PROVIDER_KEY_ISSUER,expires=NOW)
        with self.assertRaises(HostPreflightRejected):inspect_external_onboarding(P,(one,),(),checked_at_utc=NOW)

    def test_duplicate_host_control(self):
        x=control(HostControl.ATOMIC_FSYNC_AND_LOCKING,index=1)
        y=control(HostControl.ATOMIC_FSYNC_AND_LOCKING,index=2)
        with self.assertRaises(HostPreflightRejected):inspect_external_onboarding(P,(),(x,y),checked_at_utc=NOW)

    def test_host_reused_role_evidence_id(self):
        x=evidence(EvidenceRole.PROVIDER_KEY_ISSUER)
        y=replace(control(HostControl.ATOMIC_FSYNC_AND_LOCKING),evidence_id=x.evidence_id)
        with self.assertRaises(HostPreflightRejected):inspect_external_onboarding(P,(x,),(y,),checked_at_utc=NOW)

    def test_onboarding_role_type(self):
        with self.assertRaises(TypeError):evidence('PROVIDER_KEY_ISSUER')

    def test_onboarding_product_type(self):
        with self.assertRaises(TypeError):evidence(EvidenceRole.PROVIDER_KEY_ISSUER,product='SSI')

    def test_invalid_actor_id(self):
        with self.assertRaises(HostPreflightRejected):evidence(EvidenceRole.PROVIDER_KEY_ISSUER,actor='operator@example.org')

    def test_expiry_order_invalid(self):
        with self.assertRaises(HostPreflightRejected):evidence(EvidenceRole.PROVIDER_KEY_ISSUER,expires=NOW-timedelta(minutes=20))

    def test_invalid_claimed_present_type(self):
        with self.assertRaises(TypeError):replace(control(HostControl.NO_SYMLINK_OR_REPARSE),claimed_present=1)

    def test_fake_verified_evidence_fails_to_promote(self):
        self.assertFalse(all_evidence()[0].independently_authenticated)
        self.assertFalse(all_controls()[0].verified_on_host)

    def test_invalid_input_collections(self):
        with self.assertRaises(TypeError):inspect_external_onboarding(P,[],(),checked_at_utc=NOW)
        with self.assertRaises(TypeError):inspect_external_onboarding(P,(),[],checked_at_utc=NOW)
        with self.assertRaises(TypeError):inspect_external_onboarding('SSI',(),(),checked_at_utc=NOW)

    def test_naive_or_non_utc_clock(self):
        with self.assertRaises(HostPreflightRejected):inspect_external_onboarding(P,(),(),checked_at_utc=NOW.replace(tzinfo=None))
        with self.assertRaises(HostPreflightRejected):inspect_external_onboarding(P,(),(),checked_at_utc=NOW.replace(tzinfo=timezone(timedelta(hours=7))))

    def test_manifest_immutable(self):
        report=inspect_external_onboarding(P,(),(),checked_at_utc=NOW)
        with self.assertRaises(FrozenInstanceError):report.state='APPROVED'

    def test_permissions_are_hard_false_even_if_completely_claimed(self):
        report=inspect_external_onboarding(Q,
            tuple(evidence(role,product=Q,index=i) for i,role in enumerate(EvidenceRole,1)),
            all_controls(),checked_at_utc=NOW)
        self.assertEqual(report.state,'INDEPENDENT_VERIFICATION_REQUIRED')
        self.assertFalse(report.vendor_key_origin_verified)
        self.assertFalse(report.rights_to_read_or_cache)


class FloorFixtureTests(unittest.TestCase):
    def setUp(self):
        self.first=append_fixture_floor(None,floor())
        self.second=append_fixture_floor(self.first,floor(sequence=2,tail='d'*64,
            issued=NOW-timedelta(minutes=1),observed=NOW+timedelta(seconds=1)))

    def test_genesis_checksum(self):
        self.assertEqual(self.first.index,1)
        self.assertEqual(self.first.previous_record_sha256,'0'*64)
        self.assertEqual(self.first.compute_sha256(),self.first.record_sha256)

    def test_next_checkpoint_link(self):
        self.assertEqual(self.second.previous_record_sha256,self.first.record_sha256)
        self.assertEqual(self.second.index,2)

    def test_witnessed_history_is_only_conditional(self):
        report=inspect_fixture_floor_history((self.first,self.second),anchor(self.second))
        self.assertTrue(report.anchor_digest_matches_claim)
        self.assertEqual(report.observed_sequence,2)
        self.assertFalse(report.trusted_monotonic_across_restarts)
        self.assertFalse(report.vendor_key_owner_verified)
        self.assertFalse(report.data_retention_allowed)
        self.assertFalse(report.trading_actionable)
        with self.assertRaises(PermissionError):require_external_trust(report)

    def test_replay_truncated_file_detected_by_independent_anchor_claim(self):
        with self.assertRaises(HostPreflightRejected):
            inspect_fixture_floor_history((self.first,),anchor(self.second))

    def test_replay_old_anchor_detected(self):
        with self.assertRaises(HostPreflightRejected):
            inspect_fixture_floor_history((self.first,self.second),anchor(self.first))

    def test_same_sequence_same_tail_later_observation(self):
        third=append_fixture_floor(self.second,floor(sequence=2,tail='d'*64,
            issued=NOW-timedelta(seconds=30),observed=NOW+timedelta(seconds=2)))
        result=inspect_fixture_floor_history((self.first,self.second,third),anchor(third))
        self.assertEqual(result.observed_sequence,2)

    def test_rollback_sequence_rejected_on_append(self):
        with self.assertRaises(HostPreflightRejected):append_fixture_floor(self.second,floor(sequence=1,observed=NOW+timedelta(seconds=3)))

    def test_equal_sequence_different_tail_rejected(self):
        with self.assertRaises(HostPreflightRejected):append_fixture_floor(self.second,floor(sequence=2,tail='e'*64,observed=NOW+timedelta(seconds=3)))

    def test_swapped_account_rejected(self):
        with self.assertRaises(HostPreflightRejected):append_fixture_floor(self.first,floor(account='f'*64,sequence=2,observed=NOW+timedelta(seconds=3)))

    def test_swapped_provider_rejected(self):
        with self.assertRaises(HostPreflightRejected):append_fixture_floor(self.first,floor(product=Q,sequence=2,observed=NOW+timedelta(seconds=3)))

    def test_key_epoch_rotation_denied_in_fixture(self):
        with self.assertRaises(HostPreflightRejected):append_fixture_floor(self.first,floor(sequence=2,epoch=2,observed=NOW+timedelta(seconds=3)))

    def test_same_epoch_new_key_denied(self):
        with self.assertRaises(HostPreflightRejected):append_fixture_floor(self.first,floor(sequence=2,key='f'*64,observed=NOW+timedelta(seconds=3)))

    def test_old_issue_time_denied(self):
        with self.assertRaises(HostPreflightRejected):append_fixture_floor(self.first,floor(sequence=2,issued=NOW-timedelta(minutes=3),observed=NOW+timedelta(seconds=3)))

    def test_old_observed_time_denied(self):
        with self.assertRaises(HostPreflightRejected):append_fixture_floor(self.first,floor(sequence=2,observed=NOW-timedelta(seconds=1)))

    def test_identical_noop_denied(self):
        with self.assertRaises(HostPreflightRejected):append_fixture_floor(self.first,floor())

    def test_mutated_immutable_record_checksum_denied(self):
        with self.assertRaises(HostPreflightRejected):replace(self.first,tail_sha256='e'*64)

    def test_mutated_final_digest_denied(self):
        with self.assertRaises(HostPreflightRejected):replace(self.second,record_sha256='f'*64)

    def test_swapped_order_rejected(self):
        with self.assertRaises(HostPreflightRejected):inspect_fixture_floor_history((self.second,self.first),anchor(self.second))

    def test_removed_middle_record_rejected(self):
        third=append_fixture_floor(self.second,floor(sequence=3,tail='f'*64,
            issued=NOW,observed=NOW+timedelta(seconds=5)))
        with self.assertRaises(HostPreflightRejected):inspect_fixture_floor_history((self.first,third),anchor(third))

    def test_anchor_cross_provider_denied(self):
        with self.assertRaises(HostPreflightRejected):inspect_fixture_floor_history((self.first,),replace(anchor(self.first),product=Q))

    def test_anchor_wrong_account_denied(self):
        with self.assertRaises(HostPreflightRejected):inspect_fixture_floor_history((self.first,),replace(anchor(self.first),account_binding_sha256_claim='f'*64))

    def test_anchor_wrong_digest_denied(self):
        with self.assertRaises(HostPreflightRejected):inspect_fixture_floor_history((self.first,),replace(anchor(self.first),expected_record_sha256='f'*64))

    def test_empty_history_denied(self):
        with self.assertRaises(HostPreflightRejected):inspect_fixture_floor_history((),anchor(self.first))

    def test_mutable_history_denied(self):
        with self.assertRaises(TypeError):inspect_fixture_floor_history([self.first],anchor(self.first))

    def test_untyped_floor_denied(self):
        with self.assertRaises(TypeError):append_fixture_floor(None,object())

    def test_untyped_anchor_denied(self):
        with self.assertRaises(TypeError):inspect_fixture_floor_history((self.first,),object())

    def test_invalid_anchor_index(self):
        with self.assertRaises(HostPreflightRejected):replace(anchor(self.first),expected_index=0)

    def test_invalid_witness_id(self):
        with self.assertRaises(HostPreflightRejected):replace(anchor(self.first),witness_evidence_id='mysecret')

    def test_claimed_anchor_is_never_authenticated(self):
        self.assertFalse(anchor(self.first).independently_authenticated)
        self.assertFalse(self.first.host_protected)

    def test_local_file_restart_with_separately_held_anchor_claim(self):
        """Metadata-only fixture file round-trip: DOES NOT protect from attacker replacing both."""
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'fixture.json'
            rows=[]
            for r in (self.first,self.second):
                rows.append({k:(getattr(r,k).value if k=='product' else getattr(r,k).isoformat() if k.endswith('_utc') else getattr(r,k))
                             for k in r.__dataclass_fields__})
            path.write_text(json.dumps(rows,sort_keys=True),encoding='utf-8')
            loaded=json.loads(path.read_text(encoding='utf-8'))
            restored=tuple(FixtureFloorRecord(**{k:(P if k=='product' else datetime.fromisoformat(v) if k.endswith('_utc') else v)
                                          for k,v in row.items()}) for row in loaded)
            self.assertEqual(inspect_fixture_floor_history(restored,anchor(self.second)).checkpoint_count,2)
            # Simulate replay of old local file while an out-of-band witness retains future anchor.
            path.write_text(json.dumps(rows[:1]),encoding='utf-8')
            older=tuple(FixtureFloorRecord(**{k:(P if k=='product' else datetime.fromisoformat(v) if k.endswith('_utc') else v)
                                          for k,v in row.items()}) for row in json.loads(path.read_text()))
            with self.assertRaises(HostPreflightRejected):inspect_fixture_floor_history(older,anchor(self.second))

    def test_unchanged_file_with_forged_older_anchor_passes_only_conditionally(self):
        """Shows irreducible threat: attacker can replace BOTH local file AND witness."""
        report=inspect_fixture_floor_history((self.first,),anchor(self.first))
        self.assertTrue(report.anchor_digest_matches_claim)
        self.assertFalse(report.trusted_monotonic_across_restarts)

    def test_no_secrets_in_fixture_record(self):
        rendered=repr(self.first)
        self.assertNotIn('consumerSecret',rendered)
        self.assertNotIn('X-API-Key',rendered)
        self.assertNotIn('raw_ohlcv',rendered)

    def test_bypassed_python_dataclass_mutation_rechecked_on_inspection(self):
        """A malformed untrusted in-memory object must not pass after init validation."""
        record=append_fixture_floor(None,floor())
        object.__setattr__(record,'tail_sha256','f'*64)
        with self.assertRaises(HostPreflightRejected):
            inspect_fixture_floor_history((record,),anchor(self.first))

    def test_bypassed_prior_mutation_rechecked_before_append(self):
        record=append_fixture_floor(None,floor())
        object.__setattr__(record,'tail_sha256','f'*64)
        with self.assertRaises(HostPreflightRejected):
            append_fixture_floor(record,floor(sequence=2,observed=NOW+timedelta(seconds=2)))

    def test_same_key_fingerprint_different_key_id_denied(self):
        other=replace(floor(sequence=2,observed=NOW+timedelta(seconds=3)),
                      custody_key_id='KEY-OTHERKEY01')
        with self.assertRaises(HostPreflightRejected):
            append_fixture_floor(self.first,other)

    def test_reports_immutable(self):
        result=inspect_fixture_floor_history((self.first,),anchor(self.first))
        with self.assertRaises(FrozenInstanceError):result.trading_actionable=True

    def test_require_external_trust_unknown_type(self):
        with self.assertRaises(TypeError):require_external_trust(object())


if __name__ == '__main__':
    unittest.main()
