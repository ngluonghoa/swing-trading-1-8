"""P0.29 synthetic fixtures ONLY. Never enrol these test keys with a provider.

No network, external storage, source quotes, API secrets or real custodian.
"""
import base64
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from swing_trading.native_minute_bar_source_plan import BarProduct
from swing_trading.provider_rights_review import RightsScope
from swing_trading.provider_signed_event_chain import (
    EventKind, RightsChainRejected, RightsChainState, SignedRightsEvent,
)
from swing_trading.provider_head_custody import (
    ClaimedCustodyAnchor, SignedLedgerKeyEpoch, ClaimedCustodyFloor,
    HeadFreshnessChallenge, SignedCustodianHead, HeadCustodyRejected,
    CustodiedRightsVerification, bootstrap_claimed_custody_floor,
    verify_custodied_rights_chain, require_custodied_rights_authorization,
)

NOW = datetime(2026, 11, 7, 0, 10, tzinfo=timezone.utc)
SSI = BarProduct.SSI_FASTCONNECT_INTRADAY_OHLC
DNSE = BarProduct.DNSE_OPENAPI_OHLC
ZERO = "0" * 64
PLACEHOLDER = base64.b64encode(bytes(64)).decode("ascii")


def public(key):
    return key.public_key().public_bytes(serialization.Encoding.Raw,
                                        serialization.PublicFormat.Raw)


def signature(key, message):
    return base64.b64encode(key.sign(message)).decode("ascii")


class FixtureFloorStore:
    """Test-only model of CAS; no durability/ACL/rollback guarantee."""
    def __init__(self, floor):
        self.floor = floor

    def read_floor(self, anchor_sha256):
        if self.floor is None or self.floor.anchor_sha256 != anchor_sha256:
            raise LookupError("Missing fixture floor")
        return self.floor

    def compare_and_swap(self, expected_floor_sha256, next_floor):
        if self.floor is None or self.floor.floor_sha256() != expected_floor_sha256:
            return False
        self.floor = next_floor
        return True


class HeadCustodyTests(unittest.TestCase):
    def setUp(self):
        # Public reproducible fixture seeds, never broker/custodian keys.
        self.root = Ed25519PrivateKey.from_private_bytes(b"\x91" * 32)
        self.keys = tuple(Ed25519PrivateKey.from_private_bytes(bytes([n]) * 32)
                          for n in (0x92, 0x93, 0x94))
        self.other_root = Ed25519PrivateKey.from_private_bytes(b"\x95" * 32)
        self.anchor = self.make_anchor()
        self.floor = bootstrap_claimed_custody_floor(
            self.anchor, checked_at_utc=NOW - timedelta(minutes=1))
        self.epochs = (self.epoch(),)
        self.events = self.make_events(EventKind.GRANT_CANDIDATE)

    def make_anchor(self, product=SSI, root=None):
        raw = public(root or self.root)
        return ClaimedCustodyAnchor(product, "CUST-SYNTHETIC01", "KEY-ROOTTEST0001",
                                    raw, sha256(raw).hexdigest(), "EVID-ROOTCLAIM001",
                                    "ACTR-OPERATOR001", "ACTR-REVIEWER001")

    def epoch(self, number=1, *, previous=None, activation=1, recorded=None,
              expires=None, anchor=None, key=None):
        anchor = anchor or self.anchor
        e = SignedLedgerKeyEpoch(
            anchor.product, anchor.anchor_sha256(), number,
            f"KEY-LEDGERTEST{number:04d}", public(key or self.keys[number - 1]),
            activation, recorded or NOW - timedelta(minutes=10 - number),
            expires or NOW + timedelta(hours=1),
            ZERO if previous is None else previous.registry_sha256(),
            f"EVID-KEYCLAIM{number:04d}", PLACEHOLDER, PLACEHOLDER,
            None if number == 1 else PLACEHOLDER,
        )
        return self.sign_epoch(e, key=key)

    def sign_epoch(self, epoch, *, key=None, root=None, previous_key=None):
        new_key = key or self.keys[epoch.epoch - 1]
        old_key = previous_key or self.keys[max(0, epoch.epoch - 2)]
        return replace(epoch,
                       root_signature_base64=signature(root or self.root, epoch.signing_bytes("ROOT")),
                       new_key_signature_base64=signature(new_key, epoch.signing_bytes("NEW_KEY")),
                       previous_key_signature_base64=(None if epoch.epoch == 1 else
                           signature(old_key, epoch.signing_bytes("PREVIOUS_KEY"))))

    def make_events(self, *kinds, epochs=None, expiry=None):
        epochs = epochs or self.epochs
        previous = ZERO
        result = []
        for index, kind in enumerate(kinds, 1):
            epoch = [e for e in epochs if e.activates_at_sequence <= index][-1]
            published = NOW - timedelta(minutes=2) + timedelta(seconds=index)
            e = SignedRightsEvent(
                epoch.product, index, previous, f"EVNT-SYNTHETIC{index:04d}",
                "EVID-RIGHTSCLAIM01", kind, epoch.key_id, f"{index:032x}",
                published, published,
                (expiry or NOW + timedelta(hours=1)) if kind is EventKind.GRANT_CANDIDATE else None,
                (RightsScope.READ_HISTORICAL, RightsScope.RESEARCH_BACKTEST)
                if kind is EventKind.GRANT_CANDIDATE else (), PLACEHOLDER,
            )
            e = replace(e, signature_base64=signature(self.keys[epoch.epoch - 1], e.signing_bytes()))
            result.append(e)
            previous = e.chain_hash()
        return tuple(result)

    def bundle(self, *, events=None, epochs=None, anchor=None, floor=None, now=NOW):
        events = self.events if events is None else events
        epochs = self.epochs if epochs is None else epochs
        anchor = anchor or self.anchor
        floor = floor or self.floor
        challenge = HeadFreshnessChallenge(
            anchor.product, anchor.anchor_sha256(), floor.floor_sha256(),
            f"CHAL-SYNTHETIC{floor.generation + 1:04d}", f"{floor.generation + 1:032x}",
            now - timedelta(seconds=20), now + timedelta(seconds=40),
        )
        active = epochs[-1]
        head = SignedCustodianHead(
            anchor.product, anchor.anchor_sha256(), f"HEAD-SYNTHETIC{floor.head_serial + 1:04d}",
            floor.head_serial + 1, challenge.challenge_id, challenge.nonce_hex,
            floor.floor_sha256(), active.epoch, active.registry_sha256(), active.key_id,
            sha256(active.public_key_raw).hexdigest(), len(events), events[-1].chain_hash(),
            now - timedelta(seconds=10), challenge.expires_at_utc, False, PLACEHOLDER,
        )
        head = self.sign_head(head)
        return dict(events=events, key_epochs=epochs, anchor=anchor, floor=floor,
                    challenge=challenge, head=head, checked_at_utc=now)

    def sign_head(self, head, root=None, **changes):
        head = replace(head, **changes)
        return replace(head, signature_base64=signature(root or self.root, head.signing_bytes()))

    def verify(self, **changes):
        b = self.bundle()
        b.update(changes)
        return verify_custodied_rights_chain(**b)

    def reject(self, bundle):
        with self.assertRaises((RightsChainRejected, TypeError, ValueError)):
            verify_custodied_rights_chain(**bundle)

    def rotated(self, *kinds):
        second = self.epoch(2, previous=self.epochs[0], activation=2)
        epochs = (*self.epochs, second)
        events = self.make_events(*(kinds or (EventKind.GRANT_CANDIDATE,) * 2), epochs=epochs)
        return self.bundle(events=events, epochs=epochs)

    def test_valid_response_yields_only_conditional_cas_proposal(self):
        r = self.verify()
        self.assertTrue(r.conditional_signature_integrity_verified)
        self.assertTrue(r.external_atomic_commit_required)
        self.assertEqual(r.expected_floor_sha256, self.floor.floor_sha256())
        self.assertEqual(r.proposed_floor.generation, 1)
        self.assertEqual(r.proposed_floor.sequence, 1)
        self.assertEqual(r.state, RightsChainState.SIGNED_CANDIDATE_UNAUTHORIZED)
        self.assertEqual(self.floor.generation, 0)

    def test_self_created_root_never_proves_provider_or_permissions(self):
        r = self.verify()
        for attr in ("provider_key_owner_verified", "custodian_independence_verified",
                     "durable_rollback_protection_verified", "current_revocation_freshness_verified",
                     "permission_to_read_or_cache", "backtest_allowed", "production_authorized", "actionable"):
            self.assertFalse(getattr(r, attr), attr)
        self.assertFalse(self.anchor.provider_key_owner_verified)
        with self.assertRaises(PermissionError):
            require_custodied_rights_authorization(r)

    def test_unchanged_event_head_can_refresh_with_new_challenge_and_serial(self):
        old = self.verify()
        b = self.bundle(floor=old.proposed_floor, now=NOW + timedelta(seconds=30))
        r = verify_custodied_rights_chain(**b)
        self.assertEqual(r.proposed_floor.sequence, old.proposed_floor.sequence)
        self.assertEqual(r.proposed_floor.head_serial, 2)
        self.assertEqual(r.proposed_floor.generation, 2)

    def test_head_signature_tampering_rejected(self):
        b = self.bundle()
        b["head"] = replace(b["head"], service_suspended=True)
        self.reject(b)

    def test_head_signed_by_ledger_key_instead_of_custodian_rejected(self):
        b = self.bundle()
        b["head"] = self.sign_head(b["head"], root=self.keys[0])
        self.reject(b)

    def test_wrong_root_signature_rejected(self):
        b = self.bundle()
        b["head"] = self.sign_head(b["head"], root=self.other_root)
        self.reject(b)

    def test_other_product_even_with_valid_root_signature_rejected(self):
        b = self.bundle()
        b["head"] = self.sign_head(b["head"], product=DNSE)
        self.reject(b)

    def test_connected_mcp_is_not_same_signed_openapi_product(self):
        b = self.bundle()
        b["head"] = self.sign_head(b["head"], product=BarProduct.SSI_CONNECTED_INTRADAY_TICKS)
        self.reject(b)

    def test_root_substitution_cannot_reuse_previous_floor(self):
        old_floor = self.verify().proposed_floor
        anchor = self.make_anchor(root=self.other_root)
        epoch = self.epoch(anchor=anchor)
        epoch = self.sign_epoch(epoch, root=self.other_root)
        events = self.make_events(EventKind.GRANT_CANDIDATE, epochs=(epoch,))
        b = self.bundle(anchor=anchor, floor=old_floor, epochs=(epoch,), events=events,
                        now=NOW + timedelta(seconds=30))
        b["head"] = self.sign_head(b["head"], root=self.other_root)
        self.reject(b)

    def test_anchor_provenance_substitution_rejected(self):
        b = self.bundle()
        b["anchor"] = replace(self.anchor, provenance_evidence_id="EVID-DIFFERENT001")
        self.reject(b)

    def test_challenge_nonce_mismatch_with_valid_signature_rejected(self):
        b = self.bundle()
        b["head"] = self.sign_head(b["head"], challenge_nonce_hex="a" * 32)
        self.reject(b)

    def test_challenge_id_mismatch_with_valid_signature_rejected(self):
        b = self.bundle()
        b["head"] = self.sign_head(b["head"], challenge_id="CHAL-DIFFERENT001")
        self.reject(b)

    def test_reply_to_different_floor_rejected(self):
        b = self.bundle()
        b["head"] = self.sign_head(b["head"], floor_sha256="a" * 64)
        self.reject(b)

    def test_missing_floor_is_not_silently_bootstrapped(self):
        self.reject({**self.bundle(), "floor": None})

    def test_challenge_expiry_boundary_is_closed(self):
        b = self.bundle()
        b["checked_at_utc"] = b["challenge"].expires_at_utc
        self.reject(b)

    def test_head_expiry_boundary_is_closed(self):
        b = self.bundle()
        b["head"] = self.sign_head(b["head"], expires_at_utc=NOW)
        self.reject(b)

    def test_head_cannot_outlive_challenge(self):
        b = self.bundle()
        b["head"] = self.sign_head(b["head"], expires_at_utc=NOW + timedelta(seconds=41))
        self.reject(b)

    def test_head_cannot_predate_challenge_even_with_new_signature(self):
        b = self.bundle()
        b["head"] = self.sign_head(b["head"], issued_at_utc=NOW - timedelta(seconds=21),
                                     expires_at_utc=NOW + timedelta(seconds=30))
        self.reject(b)

    def test_future_head_is_rejected(self):
        b = self.bundle()
        b["head"] = self.sign_head(b["head"], issued_at_utc=NOW + timedelta(seconds=1))
        self.reject(b)

    def test_clock_rollback_behind_floor_is_rejected(self):
        old = self.verify()
        b = self.bundle(floor=old.proposed_floor)
        self.reject(b)

    def test_full_old_response_replay_against_advanced_floor_rejected(self):
        b = self.bundle()
        r = verify_custodied_rights_chain(**b)
        b["floor"] = r.proposed_floor
        self.reject(b)

    def test_consumed_nonce_cannot_be_reissued_to_next_floor(self):
        floor = self.verify().proposed_floor
        b = self.bundle(floor=floor, now=NOW + timedelta(seconds=30))
        b["challenge"] = replace(b["challenge"], nonce_hex=floor.challenge_nonce_hex)
        b["head"] = self.sign_head(b["head"], challenge_nonce_hex=floor.challenge_nonce_hex)
        self.reject(b)

    def test_consumed_challenge_id_cannot_be_reissued(self):
        floor = self.verify().proposed_floor
        b = self.bundle(floor=floor, now=NOW + timedelta(seconds=30))
        b["challenge"] = replace(b["challenge"], challenge_id=floor.challenge_id)
        b["head"] = self.sign_head(b["head"], challenge_id=floor.challenge_id)
        self.reject(b)

    def test_head_serial_must_strictly_increase_even_on_refresh(self):
        floor = self.verify().proposed_floor
        b = self.bundle(floor=floor, now=NOW + timedelta(seconds=30))
        b["head"] = self.sign_head(b["head"], head_serial=floor.head_serial)
        self.reject(b)

    def test_old_sequence_with_fresh_signature_rejected(self):
        events = self.make_events(EventKind.GRANT_CANDIDATE, EventKind.PROVIDER_REVOKE)
        floor = verify_custodied_rights_chain(**self.bundle(events=events)).proposed_floor
        b = self.bundle(floor=floor, now=NOW + timedelta(seconds=30))
        self.reject(b)

    def test_same_sequence_fork_rejected_after_resigning_everything(self):
        floor = self.verify().proposed_floor
        e = replace(self.events[0], event_id="EVNT-FORKED000001")
        e = replace(e, signature_base64=signature(self.keys[0], e.signing_bytes()))
        b = self.bundle(events=(e,), floor=floor, now=NOW + timedelta(seconds=30))
        self.reject(b)

    def test_longer_fork_does_not_pass_merely_by_increasing_sequence(self):
        floor = self.verify().proposed_floor
        first = replace(self.events[0], event_id="EVNT-FORKED000001")
        first = replace(first, signature_base64=signature(self.keys[0], first.signing_bytes()))
        second = self.make_events(EventKind.GRANT_CANDIDATE, EventKind.GRANT_CANDIDATE)[1]
        second = replace(second, previous_sha256=first.chain_hash())
        second = replace(second, signature_base64=signature(self.keys[0], second.signing_bytes()))
        self.reject(self.bundle(events=(first, second), floor=floor, now=NOW + timedelta(seconds=30)))

    def test_append_only_extension_preserves_previously_observed_prefix(self):
        floor = self.verify().proposed_floor
        events = self.make_events(EventKind.GRANT_CANDIDATE, EventKind.PROVIDER_REVOKE)
        r = verify_custodied_rights_chain(**self.bundle(events=events, floor=floor,
                                                       now=NOW + timedelta(seconds=30)))
        self.assertEqual(r.proposed_floor.sequence, 2)
        self.assertTrue(r.proposed_floor.hold_observed)

    def test_valid_rotation_verifies_original_and_new_key_without_resigning_history(self):
        b = self.rotated()
        r = verify_custodied_rights_chain(**b)
        self.assertEqual(b["events"][0], self.events[0])
        self.assertEqual(r.proposed_floor.key_epoch, 2)
        self.assertEqual(r.verified_events, 2)
        self.assertFalse(r.permission_to_read_or_cache)

    def test_rotation_preserves_hold_across_later_candidate(self):
        b = self.rotated(EventKind.PROVIDER_REVOKE, EventKind.GRANT_CANDIDATE)
        r = verify_custodied_rights_chain(**b)
        self.assertEqual(r.state, RightsChainState.SIGNED_HOLD_UNAUTHORIZED)

    def test_rotation_requires_previous_key_continuity(self):
        b = self.rotated()
        old, new = b["key_epochs"]
        forged = self.sign_epoch(new, previous_key=self.keys[2])
        b["key_epochs"] = (old, forged)
        b["head"] = self.sign_head(b["head"], key_registry_sha256=forged.registry_sha256())
        self.reject(b)

    def test_rotation_requires_new_key_proof_of_possession(self):
        b = self.rotated()
        old, new = b["key_epochs"]
        forged = self.sign_epoch(new, key=self.keys[2])
        b["key_epochs"] = (old, forged)
        b["head"] = self.sign_head(b["head"], key_registry_sha256=forged.registry_sha256())
        self.reject(b)

    def test_rotation_requires_custodian_root_countersignature(self):
        b = self.rotated()
        old, new = b["key_epochs"]
        forged = self.sign_epoch(new, root=self.other_root)
        b["key_epochs"] = (old, forged)
        b["head"] = self.sign_head(b["head"], key_registry_sha256=forged.registry_sha256())
        self.reject(b)

    def test_signature_roles_cannot_be_swapped(self):
        b = self.rotated()
        old, new = b["key_epochs"]
        forged = replace(new, previous_key_signature_base64=new.new_key_signature_base64,
                         new_key_signature_base64=new.previous_key_signature_base64)
        b["key_epochs"] = (old, forged)
        b["head"] = self.sign_head(b["head"], key_registry_sha256=forged.registry_sha256())
        self.reject(b)

    def test_rotation_registry_gap_rejected(self):
        b = self.rotated()
        b["key_epochs"] = (b["key_epochs"][1],)
        self.reject(b)

    def test_key_registry_previous_hash_must_match(self):
        b = self.rotated()
        old, new = b["key_epochs"]
        new = self.sign_epoch(replace(new, previous_epoch_sha256="a" * 64))
        b["key_epochs"] = (old, new)
        b["head"] = self.sign_head(b["head"], key_registry_sha256=new.registry_sha256())
        self.reject(b)

    def test_old_key_cannot_sign_new_epoch_event(self):
        b = self.rotated()
        first, second = b["events"]
        second = replace(second, key_id=self.epochs[0].key_id)
        second = replace(second, signature_base64=signature(self.keys[0], second.signing_bytes()))
        b["events"] = (first, second)
        b["head"] = self.sign_head(b["head"], tail_sha256=second.chain_hash())
        self.reject(b)

    def test_new_key_cannot_sign_old_prefix(self):
        b = self.rotated()
        first, second = b["events"]
        first = replace(first, key_id=b["key_epochs"][1].key_id)
        first = replace(first, signature_base64=signature(self.keys[1], first.signing_bytes()))
        second = replace(second, previous_sha256=first.chain_hash())
        second = replace(second, signature_base64=signature(self.keys[1], second.signing_bytes()))
        b["events"] = (first, second)
        b["head"] = self.sign_head(b["head"], tail_sha256=second.chain_hash())
        self.reject(b)

    def test_event_before_key_provenance_is_rejected(self):
        e = self.epoch(recorded=NOW - timedelta(seconds=30))
        self.reject(self.bundle(epochs=(e,)))

    def test_current_key_expiry_is_closed_at_boundary(self):
        e = self.epoch(expires=NOW - timedelta(seconds=10))
        self.reject(self.bundle(epochs=(e,)))

    def test_expired_old_key_cannot_authorize_rotation(self):
        old = self.epoch(expires=NOW - timedelta(minutes=7))
        new = self.epoch(2, previous=old, activation=2, recorded=old.expires_at_utc)
        events = self.make_events(EventKind.GRANT_CANDIDATE, EventKind.GRANT_CANDIDATE,
                                  epochs=(old, new))
        self.reject(self.bundle(events=events, epochs=(old, new)))

    def test_future_key_registry_is_rejected(self):
        e = self.epoch(recorded=NOW + timedelta(seconds=1))
        self.reject(self.bundle(epochs=(e,)))

    def test_root_key_cannot_also_be_ledger_key(self):
        e = self.epoch(key=self.root)
        self.reject(self.bundle(epochs=(e,)))

    def test_rotated_key_fingerprint_cannot_reuse_previous_public_key(self):
        old = self.epochs[0]
        new = self.epoch(2, previous=old, activation=2, key=self.keys[0])
        self.reject(self.bundle(epochs=(old, new)))

    def test_key_id_reuse_rejected_even_with_different_public_key(self):
        b = self.rotated()
        old, new = b["key_epochs"]
        new = self.sign_epoch(replace(new, key_id=old.key_id))
        b["key_epochs"] = (old, new)
        b["head"] = self.sign_head(b["head"], ledger_key_id=old.key_id,
                                     key_registry_sha256=new.registry_sha256())
        self.reject(b)

    def test_head_cannot_claim_unpublished_next_key_epoch(self):
        old = self.epochs[0]
        new = self.epoch(2, previous=old, activation=2)
        self.reject(self.bundle(epochs=(old, new)))

    def test_rollback_of_key_epoch_rejected_despite_fresh_response(self):
        floor = verify_custodied_rights_chain(**self.rotated()).proposed_floor
        events = self.make_events(EventKind.GRANT_CANDIDATE, EventKind.GRANT_CANDIDATE)
        self.reject(self.bundle(events=events, floor=floor, now=NOW + timedelta(seconds=30)))

    def test_rotation_extends_previously_observed_event_and_registry_floors(self):
        floor = self.verify().proposed_floor
        b = self.rotated()
        b = self.bundle(events=b["events"], epochs=b["key_epochs"], floor=floor,
                        now=NOW + timedelta(seconds=30))
        r = verify_custodied_rights_chain(**b)
        self.assertEqual(r.proposed_floor.key_epoch, 2)
        self.assertEqual(r.proposed_floor.generation, 2)

    def test_retired_key_may_verify_history_signed_before_its_expiry(self):
        old = self.epoch(expires=NOW - timedelta(seconds=118))
        new = self.epoch(2, previous=old, activation=2)
        events = self.make_events(EventKind.GRANT_CANDIDATE, EventKind.GRANT_CANDIDATE,
                                  epochs=(old, new))
        r = verify_custodied_rights_chain(**self.bundle(events=events, epochs=(old, new)))
        self.assertEqual(r.verified_events, 2)

    def test_multiple_rotations_keep_original_history_and_hold(self):
        old = self.epochs[0]
        second = self.epoch(2, previous=old, activation=2)
        third = self.epoch(3, previous=second, activation=3)
        epochs = (old, second, third)
        events = self.make_events(EventKind.GRANT_CANDIDATE, EventKind.PROVIDER_REVOKE,
                                  EventKind.GRANT_CANDIDATE, epochs=epochs)
        r = verify_custodied_rights_chain(**self.bundle(events=events, epochs=epochs))
        self.assertEqual(r.proposed_floor.key_epoch, 3)
        self.assertEqual(r.state, RightsChainState.SIGNED_HOLD_UNAUTHORIZED)

    def test_key_registry_cannot_cross_provider_even_with_same_root(self):
        epoch = self.sign_epoch(replace(self.epochs[0], product=DNSE))
        self.reject(self.bundle(epochs=(epoch,)))

    def test_head_cannot_pin_another_active_key_fingerprint(self):
        b = self.bundle()
        b["head"] = self.sign_head(b["head"], ledger_key_sha256="a" * 64)
        self.reject(b)

    def test_rotation_cannot_activate_at_same_sequence_as_previous_epoch(self):
        new = self.epoch(2, previous=self.epochs[0], activation=1)
        self.reject(self.bundle(epochs=(*self.epochs, new)))

    def test_complete_external_floor_reset_is_outside_integrity_proof_and_still_unauthorized(self):
        held_events = self.make_events(EventKind.GRANT_CANDIDATE, EventKind.PROVIDER_REVOKE)
        held = verify_custodied_rights_chain(**self.bundle(events=held_events))
        self.assertTrue(held.proposed_floor.hold_observed)
        # An attacker replaces the entire retained floor, not just the head.
        # No stateless verifier can recognize this without independent custody.
        reset = bootstrap_claimed_custody_floor(self.anchor, checked_at_utc=NOW)
        r = verify_custodied_rights_chain(**self.bundle(floor=reset,
                                                       now=NOW + timedelta(seconds=30)))
        self.assertTrue(r.conditional_signature_integrity_verified)
        self.assertFalse(r.durable_rollback_protection_verified)
        self.assertFalse(r.current_revocation_freshness_verified)
        with self.assertRaises(PermissionError):
            require_custodied_rights_authorization(r)

    def test_rewriting_prior_registry_is_rejected(self):
        floor = self.verify().proposed_floor
        old = self.sign_epoch(replace(self.epochs[0], provenance_evidence_id="EVID-REWRITTEN001"))
        new = self.epoch(2, previous=old, activation=2)
        events = self.make_events(EventKind.GRANT_CANDIDATE, EventKind.GRANT_CANDIDATE,
                                  epochs=(old, new))
        self.reject(self.bundle(events=events, epochs=(old, new), floor=floor,
                                now=NOW + timedelta(seconds=30)))

    def test_custodian_service_suspension_is_sticky_in_next_floor(self):
        b = self.bundle()
        b["head"] = self.sign_head(b["head"], service_suspended=True)
        first = verify_custodied_rights_chain(**b)
        b = self.bundle(floor=first.proposed_floor, now=NOW + timedelta(seconds=30))
        self.assertFalse(b["head"].service_suspended)
        second = verify_custodied_rights_chain(**b)
        self.assertEqual(second.state, RightsChainState.SIGNED_HOLD_UNAUTHORIZED)
        self.assertTrue(second.proposed_floor.hold_observed)

    def test_security_suspend_event_blocks_after_rotation(self):
        b = self.rotated(EventKind.SECURITY_SUSPEND, EventKind.GRANT_CANDIDATE)
        self.assertEqual(verify_custodied_rights_chain(**b).state,
                         RightsChainState.SIGNED_HOLD_UNAUTHORIZED)

    def test_candidate_expiry_remains_closed_with_fresh_head(self):
        events = self.make_events(EventKind.GRANT_CANDIDATE, expiry=NOW)
        r = verify_custodied_rights_chain(**self.bundle(events=events))
        self.assertEqual(r.state, RightsChainState.SIGNED_CANDIDATE_EXPIRED)

    def test_event_after_signed_head_is_rejected(self):
        e = replace(self.events[0], published_at_utc=NOW - timedelta(seconds=5))
        e = replace(e, signature_base64=signature(self.keys[0], e.signing_bytes()))
        self.reject(self.bundle(events=(e,)))

    def test_truncated_history_rejected(self):
        b = self.rotated()
        b["events"] = b["events"][:1]
        self.reject(b)

    def test_reordered_history_rejected(self):
        b = self.rotated()
        b["events"] = tuple(reversed(b["events"]))
        self.reject(b)

    def test_forged_event_signature_rejected(self):
        e = replace(self.events[0], signature_base64=PLACEHOLDER)
        self.reject(self.bundle(events=(e,)))

    def test_challenge_ttl_cannot_be_weakened_by_caller(self):
        c = self.bundle()["challenge"]
        with self.assertRaises(HeadCustodyRejected):
            replace(c, expires_at_utc=c.issued_at_utc + timedelta(seconds=61))
        with self.assertRaises(HeadCustodyRejected):
            replace(c, expires_at_utc=c.issued_at_utc)

    def test_head_ttl_cannot_be_weakened_by_caller(self):
        h = self.bundle()["head"]
        with self.assertRaises(HeadCustodyRejected):
            replace(h, expires_at_utc=h.issued_at_utc + timedelta(seconds=61))

    def test_invalid_or_naive_utc_rejected(self):
        c = self.bundle()["challenge"]
        for invalid in (NOW.replace(tzinfo=None), "2026-11-07", NOW.astimezone(timezone(timedelta(hours=7)))):
            with self.subTest(invalid=invalid), self.assertRaises((TypeError, ValueError)):
                replace(c, issued_at_utc=invalid)

    def test_boolean_or_unbounded_counters_rejected(self):
        for invalid in (True, 0, -1, 2**63, 1.0):
            with self.subTest(invalid=invalid), self.assertRaises(HeadCustodyRejected):
                replace(self.bundle()["head"], head_serial=invalid)

    def test_noncanonical_signatures_rejected(self):
        for bad in ("invalid", PLACEHOLDER + "\n", base64.b64encode(bytes(63)).decode("ascii")):
            with self.subTest(bad=bad), self.assertRaises(RightsChainRejected):
                replace(self.bundle()["head"], signature_base64=bad)

    def test_opaque_metadata_rejects_account_url_or_secret_text(self):
        for bad in ("https://provider.example/keys", "account=12345678", "token-super-secret"):
            with self.subTest(bad=bad), self.assertRaises(HeadCustodyRejected):
                replace(self.anchor, provenance_evidence_id=bad)

    def test_same_operator_and_reviewer_claim_is_rejected(self):
        with self.assertRaises(HeadCustodyRejected):
            replace(self.anchor, independent_reviewer_actor_id=self.anchor.operator_actor_id)

    def test_wrong_root_fingerprint_is_rejected(self):
        with self.assertRaises(HeadCustodyRejected):
            replace(self.anchor, expected_root_sha256="a" * 64)

    def test_schema_requires_immutable_bounded_epochs(self):
        self.reject({**self.bundle(), "key_epochs": list(self.epochs)})
        self.reject({**self.bundle(), "key_epochs": ()})
        self.reject({**self.bundle(), "key_epochs": self.epochs * 17})

    def test_subclass_cannot_override_signed_head_bytes(self):
        class FakeHead(SignedCustodianHead):
            def signing_bytes(self):
                return b"different"
        h = self.bundle()["head"]
        fake = FakeHead(**h.__dict__)
        self.reject({**self.bundle(), "head": fake})

    def test_state_objects_are_immutable_and_cannot_set_permission_flags(self):
        r = self.verify()
        with self.assertRaises(FrozenInstanceError):
            r.proposed_floor.generation = 0
        with self.assertRaises(TypeError):
            replace(r, permission_to_read_or_cache=True)
        with self.assertRaises(TypeError):
            replace(r, current_revocation_freshness_verified=True)

    def test_no_approval_through_forged_report_or_local_cas(self):
        r = self.verify()
        store = FixtureFloorStore(self.floor)
        self.assertTrue(store.compare_and_swap(r.expected_floor_sha256, r.proposed_floor))
        forged = CustodiedRightsVerification(SSI, RightsChainState.SIGNED_CANDIDATE_UNAUTHORIZED,
                                            1, r.expected_floor_sha256, r.proposed_floor)
        with self.assertRaises(PermissionError):
            require_custodied_rights_authorization(forged)
        with self.assertRaises(TypeError):
            require_custodied_rights_authorization({"permission_to_read_or_cache": True})

    def test_two_concurrent_proposals_cannot_both_commit_in_fixture_model(self):
        first = self.verify()
        second_bundle = self.bundle()
        second_bundle["head"] = self.sign_head(second_bundle["head"], service_suspended=True)
        second = verify_custodied_rights_chain(**second_bundle)
        store = FixtureFloorStore(self.floor)
        self.assertTrue(store.compare_and_swap(second.expected_floor_sha256, second.proposed_floor))
        self.assertFalse(store.compare_and_swap(first.expected_floor_sha256, first.proposed_floor))
        self.assertTrue(store.read_floor(self.anchor.anchor_sha256()).hold_observed)

    def test_lost_floor_requires_external_recovery_not_auto_reenrolment(self):
        store = FixtureFloorStore(None)
        with self.assertRaises(LookupError):
            store.read_floor(self.anchor.anchor_sha256())
        self.assertFalse(store.compare_and_swap(self.floor.floor_sha256(), self.verify().proposed_floor))
        self.reject({**self.bundle(), "floor": None})

    def test_bootstrap_cannot_contain_prior_head_or_hidden_hold(self):
        for changes in ({"head_serial": 1}, {"sequence": 1}, {"key_epoch": 1}, {"hold_observed": True}):
            with self.subTest(changes=changes), self.assertRaises(HeadCustodyRejected):
                replace(self.floor, **changes)

    def test_report_contains_only_opaque_integrity_metadata(self):
        r = self.verify()
        rendered = repr(r)
        for forbidden in ("public_key_raw", "PRIVATE KEY", "consumerSecret", "X-API-Key", "OHLCV"):
            self.assertNotIn(forbidden, rendered)


if __name__ == "__main__":
    unittest.main()
