"""GĐ4/P0.27 synthetic independent-review packet and revoke/expiry tests."""
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import unittest

from swing_trading.native_minute_bar_source_plan import BarProduct
from swing_trading.provider_rights_review import (
    EvidenceKind, RightsScope, UnverifiedRightsClaim
)
from swing_trading.provider_review_packet import (
    ClaimedReviewAttestation, UnverifiedHoldNotice, ReviewRole,
    HoldKind, PacketState, IndependentReviewPacket,
    assemble_independent_review_packet, require_independently_authorized_packet
)

NOW = datetime(2026, 11, 6, 16, tzinfo=timezone.utc)
SSI = BarProduct.SSI_FASTCONNECT_INTRADAY_OHLC
DNSE = BarProduct.DNSE_OPENAPI_OHLC
EVID = "EVID-2026RIGHT1"


def claim(*, product=SSI, evid=EVID,
          kind=EvidenceKind.VENDOR_RIGHTS_LETTER_CLAIM,
          scopes=tuple(RightsScope), expiry=NOW+timedelta(days=30),
          recorded=NOW-timedelta(days=2)):
    return UnverifiedRightsClaim(
        product, evid, kind, recorded, scopes, "V2_CLAIM",
        30 if kind is not EvidenceKind.PUBLIC_PRODUCT_DOCUMENTATION else None,
        expiry if kind is not EvidenceKind.PUBLIC_PRODUCT_DOCUMENTATION else None,
    )


def mark(role, *, product=SSI, evid=EVID, index=0, actor=None,
         time=NOW-timedelta(days=1)):
    actor = actor or f"ACTR-{role.name[:8]}{index:04d}"
    return ClaimedReviewAttestation(
        product, evid, f"ATST-2026{role.name[:4]}{index:04d}",
        role, actor, time,
    )


def all_marks():
    return tuple(mark(role, index=i) for i, role in enumerate(ReviewRole))


def hold(*, product=SSI, evid=EVID,
         kind=HoldKind.PROVIDER_REVOCATION_CLAIM, index=0,
         effective=NOW-timedelta(hours=1),
         observed=NOW-timedelta(minutes=1)):
    return UnverifiedHoldNotice(
        product, evid, f"HOLD-2026NOTICE{index:04d}",
        kind, effective, observed
    )


def packet(*, claims=None, attestations=None, holds=(), product=SSI,
           now=NOW):
    return assemble_independent_review_packet(
        product,
        tuple([claim()]) if claims is None else claims,
        all_marks() if attestations is None else attestations,
        holds,
        reviewed_at_utc=now,
    )


class IndependentRightsPacketTests(unittest.TestCase):
    def test_no_evidence_or_attestations_incomplete(self):
        r=packet(claims=(), attestations=())
        self.assertEqual(r.state,PacketState.EVIDENCE_INCOMPLETE)
        self.assertEqual(set(r.missing_review_roles),set(ReviewRole))
        self.assertEqual(set(r.missing_scope_claims),set(RightsScope))
        self.assertFalse(r.prepared_for_external_review)
        self.assertFalse(r.permission_to_read)

    def test_complete_claims_are_only_ready_for_external_review(self):
        r=packet()
        self.assertEqual(r.state,PacketState.READY_FOR_EXTERNAL_REVIEW_ONLY)
        self.assertTrue(r.prepared_for_external_review)
        self.assertEqual(r.missing_review_roles,())
        self.assertEqual(r.missing_scope_claims,())
        self.assertEqual(set(r.claimed_roles_present),set(ReviewRole))
        self.assertEqual(r.held_evidence_ids,())
        self.assertFalse(r.external_identity_or_signature_verified)
        self.assertFalse(r.provider_entitlement_verified)
        self.assertFalse(r.permission_to_store_raw_or_derived)
        self.assertFalse(r.real_backtest_allowed)
        self.assertFalse(r.production_authorized)
        self.assertFalse(r.actionable)

    def test_even_complete_packet_cannot_authorize_access(self):
        with self.assertRaises(PermissionError):
            require_independently_authorized_packet(packet())

    def test_missing_one_claimed_role_stays_incomplete(self):
        r=packet(attestations=all_marks()[:2])
        self.assertEqual(r.state,PacketState.EVIDENCE_INCOMPLETE)
        self.assertEqual(r.missing_review_roles,(ReviewRole.STORAGE_SECURITY,))
        self.assertIn("CLAIMED_REVIEW_ROLES_INCOMPLETE",r.outstanding)

    def test_role_separation_rejects_same_claimed_actor_in_two_roles(self):
        a=mark(ReviewRole.PROVIDER_ENTITLEMENT)
        b=mark(ReviewRole.INDEPENDENT_COMPLIANCE,
               actor=a.opaque_actor_ref,index=1)
        with self.assertRaises(ValueError):
            packet(attestations=(a,b))

    def test_distinct_claimed_actors_do_not_prove_independent_identity(self):
        r=packet()
        self.assertTrue(r.prepared_for_external_review)
        self.assertFalse(r.external_identity_or_signature_verified)

    def test_public_document_cannot_provide_attested_account_rights(self):
        doc=claim(kind=EvidenceKind.PUBLIC_PRODUCT_DOCUMENTATION,
                  scopes=(),evid="EVID-PUBLICDOC1")
        marker=mark(ReviewRole.PROVIDER_ENTITLEMENT,
                    evid="EVID-PUBLICDOC1")
        with self.assertRaises(ValueError):
            packet(claims=(doc,),attestations=(marker,))

    def test_public_only_without_attestations_remains_incomplete(self):
        doc=claim(kind=EvidenceKind.PUBLIC_PRODUCT_DOCUMENTATION,
                  scopes=(),evid="EVID-PUBLICDOC1")
        r=packet(claims=(doc,),attestations=())
        self.assertEqual(r.state,PacketState.EVIDENCE_INCOMPLETE)

    def test_cross_product_attestation_rejected(self):
        x=mark(ReviewRole.PROVIDER_ENTITLEMENT,product=DNSE)
        with self.assertRaises(ValueError):
            packet(attestations=(x,))

    def test_unknown_evidence_attestation_rejected(self):
        x=mark(ReviewRole.PROVIDER_ENTITLEMENT,
               evid="EVID-UNSEEN001")
        with self.assertRaises(ValueError):
            packet(attestations=(x,))

    def test_duplicate_attestation_ids_rejected(self):
        a=mark(ReviewRole.PROVIDER_ENTITLEMENT)
        with self.assertRaises(ValueError):
            packet(attestations=(a,a))

    def test_attestation_cannot_be_before_claim_or_after_review_cutoff(self):
        for dt in (NOW-timedelta(days=3), NOW+timedelta(seconds=1)):
            x=mark(ReviewRole.PROVIDER_ENTITLEMENT,time=dt)
            with self.subTest(time=dt),self.assertRaises(ValueError):
                packet(attestations=(x,))

    def test_non_utc_attestation_and_hold_rejected(self):
        with self.assertRaises(ValueError):
            mark(ReviewRole.PROVIDER_ENTITLEMENT,
                 time=NOW.replace(tzinfo=None))
        with self.assertRaises(ValueError):
            hold(observed=NOW.replace(tzinfo=None))
        with self.assertRaises(ValueError):
            packet(now=NOW.replace(tzinfo=None))

    def test_hold_notice_fails_if_effective_after_observation(self):
        with self.assertRaises(ValueError):
            hold(effective=NOW,observed=NOW-timedelta(minutes=1))

    def test_hold_is_global_block_even_with_fully_claimed_all_scopes(self):
        r=packet(holds=(hold(),))
        self.assertEqual(r.state,PacketState.BLOCKED_HOLD)
        self.assertFalse(r.prepared_for_external_review)
        self.assertEqual(r.held_evidence_ids,(EVID,))
        self.assertIn("REVIEW_PACKET_HELD_NO_REINSTATEMENT",r.outstanding)
        self.assertIn("OUTSTANDING_CACHE_ACCESS_BLOCK_AND_RETENTION_PURGE_AUDIT",r.outstanding)
        self.assertFalse(r.permission_to_read)
        with self.assertRaises(PermissionError):
            require_independently_authorized_packet(r)

    def test_security_suspension_or_expiry_notice_also_block(self):
        for kind in (HoldKind.SECURITY_SUSPENSION,
                     HoldKind.EXPIRED_TERMS_NOTICE):
            with self.subTest(kind=kind):
                r=packet(holds=(hold(kind=kind),))
                self.assertEqual(r.state,PacketState.BLOCKED_HOLD)

    def test_expired_claim_without_hold_remains_expired_not_ready(self):
        c=claim(expiry=NOW)
        r=packet(claims=(c,))
        self.assertEqual(r.state,PacketState.BLOCKED_EXPIRED)
        self.assertEqual(r.expired_evidence_ids,(EVID,))
        self.assertFalse(r.prepared_for_external_review)

    def test_expired_and_revoked_claim_prefer_hard_hold(self):
        c=claim(expiry=NOW)
        r=packet(claims=(c,),holds=(hold(),))
        self.assertEqual(r.state,PacketState.BLOCKED_HOLD)
        self.assertEqual(r.expired_evidence_ids,(EVID,))

    def test_missing_expiry_claim_never_completes_packet(self):
        c=claim(expiry=None)
        r=packet(claims=(c,))
        self.assertEqual(r.state,PacketState.EVIDENCE_INCOMPLETE)
        self.assertEqual(r.missing_expiry_ids,(EVID,))
        self.assertIn("EVIDENCE_EXPIRY_WINDOW_MISSING",r.outstanding)

    def test_no_reinstatement_event_available(self):
        self.assertEqual(set(HoldKind),{
            HoldKind.PROVIDER_REVOCATION_CLAIM,
            HoldKind.EXPIRED_TERMS_NOTICE,
            HoldKind.SECURITY_SUSPENSION,
        })
        self.assertFalse(packet(holds=(hold(),)).production_authorized)

    def test_cross_product_hold_rejected(self):
        with self.assertRaises(ValueError):
            packet(holds=(hold(product=DNSE),))

    def test_unknown_evidence_hold_rejected(self):
        with self.assertRaises(ValueError):
            packet(holds=(hold(evid="EVID-NOTKNOWN1"),))

    def test_duplicate_hold_event_ids_rejected(self):
        x=hold()
        with self.assertRaises(ValueError):
            packet(holds=(x,x))

    def test_hold_observed_before_claim_or_future_is_rejected(self):
        for dt in (NOW-timedelta(days=4), NOW+timedelta(seconds=1)):
            h=hold(effective=dt-timedelta(minutes=1),observed=dt)
            with self.subTest(time=dt),self.assertRaises(ValueError):
                packet(holds=(h,))

    def test_duplicate_evidence_claims_rejected_via_prior_p026_gate(self):
        with self.assertRaises(ValueError):
            packet(claims=(claim(),claim()))

    def test_partial_licence_claims_cannot_be_review_ready(self):
        partial=claim(scopes=(RightsScope.READ_HISTORICAL,))
        r=packet(claims=(partial,))
        self.assertEqual(r.state,PacketState.EVIDENCE_INCOMPLETE)
        self.assertIn(RightsScope.RESEARCH_BACKTEST,r.missing_scope_claims)
        self.assertFalse(r.real_backtest_allowed)

    def test_id_formats_reject_urls_secrets_and_free_text(self):
        for bad in ("https://ssi.vn","john@example.com","token:SECRET",
                    "ACTR-1", "../evidence"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    mark(ReviewRole.PROVIDER_ENTITLEMENT,actor=bad)
        with self.assertRaises(ValueError):
            replace(mark(ReviewRole.PROVIDER_ENTITLEMENT),
                    attestation_id="ATST-ABC")
        with self.assertRaises(ValueError):
            replace(hold(),event_id="HOLD-NO")

    def test_bad_role_and_hold_kinds_rejected(self):
        with self.assertRaises(TypeError):
            replace(mark(ReviewRole.PROVIDER_ENTITLEMENT),role="COMPLIANCE")
        with self.assertRaises(TypeError):
            replace(hold(),kind="REVOKE")

    def test_unbounded_event_histories_rejected(self):
        markers=tuple(mark(ReviewRole.PROVIDER_ENTITLEMENT,index=i)
                      for i in range(33))
        with self.assertRaises(ValueError):
            packet(attestations=markers)
        holds=tuple(hold(index=i) for i in range(129))
        with self.assertRaises(ValueError):
            packet(holds=holds)

    def test_wrong_container_types_and_event_types_rejected(self):
        with self.assertRaises(TypeError):
            packet(attestations=list(all_marks()))
        with self.assertRaises(TypeError):
            packet(holds=[hold()])
        with self.assertRaises(TypeError):
            packet(holds=("REVOKED",))
        with self.assertRaises(TypeError):
            packet(claims=[claim()])

    def test_full_packet_contains_only_opaque_metadata(self):
        r=packet()
        text=repr(r)
        self.assertIn("EVID-2026RIGHT1",text)
        for forbidden in ("consumerSecret", "X-API-Key", "password",
                          "john@example.com","9999999"):
            self.assertNotIn(forbidden,text)
        self.assertFalse(hasattr(r,"raw_quotes"))
        self.assertFalse(hasattr(r,"vendor_contract_text"))

    def test_approval_properties_not_forgeable_with_replace(self):
        p=packet()
        for field in ("external_identity_or_signature_verified",
                      "provider_entitlement_verified","permission_to_read",
                      "permission_to_store_raw_or_derived",
                      "real_backtest_allowed","production_authorized","actionable"):
            with self.subTest(field=field),self.assertRaises(TypeError):
                replace(p,**{field:True})
        with self.assertRaises(FrozenInstanceError):
            p.state=PacketState.READY_FOR_EXTERNAL_REVIEW_ONLY

    def test_require_authorized_rejects_forged_dict(self):
        with self.assertRaises(TypeError):
            require_independently_authorized_packet({"signed":True})

    def test_no_holds_does_not_mean_full_history_verified(self):
        p=packet()
        self.assertTrue(p.prepared_for_external_review)
        self.assertIn("SIGNED_APPROVAL_OR_TAMPER_EVIDENT_LEDGER_NOT_DEPLOYED",
                      p.outstanding)
        self.assertFalse(p.provider_entitlement_verified)


if __name__ == "__main__":
    unittest.main()
