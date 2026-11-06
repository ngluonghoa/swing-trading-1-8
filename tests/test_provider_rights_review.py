"""GĐ4/P0.26 — synthetic rights claim audits, NEVER source authorization."""
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import unittest

from swing_trading.native_minute_bar_source_plan import BarProduct
from swing_trading.provider_rights_review import (
    EvidenceKind, RightsScope, ProviderRightsReview,
    UnverifiedRightsClaim, review_unverified_source_claims,
    require_authorized_source,
)

NOW=datetime(2026,11,6,15,0,tzinfo=timezone.utc)
SSI=BarProduct.SSI_FASTCONNECT_INTRADAY_OHLC
DNSE=BarProduct.DNSE_OPENAPI_OHLC


def claim(*, product=SSI, evidence_id="EVID-2026SSI01",
          kind=EvidenceKind.ACCOUNT_ENTITLEMENT_CLAIM,
          scopes=(RightsScope.READ_HISTORICAL,),
          expiry=None, retention=30, recorded=NOW-timedelta(days=1),
          version="V2_ACCOUNT_DOC_CLAIM"):
    return UnverifiedRightsClaim(
        product=product, evidence_id=evidence_id, kind=kind,
        recorded_at_utc=recorded, scope_claims=scopes,
        contract_version_claim=version,
        maximum_retention_days_claim=retention,
        claimed_expiry_utc=expiry,
    )


class ProviderRightsReviewTests(unittest.TestCase):
    def audit(self, *items, product=SSI):
        return review_unverified_source_claims(
            product, tuple(items), reviewed_at_utc=NOW
        )

    def test_empty_intake_has_concrete_missing_claims_and_closed_authorization(self):
        r=self.audit()
        self.assertEqual(r.evidence_ids_seen,())
        self.assertEqual(set(r.missing_scope_claims),set(RightsScope))
        self.assertIn("NO_ENTITLEMENT_EVIDENCE_REFERENCES",r.unresolved)
        self.assertFalse(r.provider_authorization_verified)
        self.assertFalse(r.real_backtest_allowed)
        self.assertFalse(r.production_authorized)
        with self.assertRaises(PermissionError):
            require_authorized_source(r)

    def test_public_document_does_not_claim_any_account_rights(self):
        public=claim(kind=EvidenceKind.PUBLIC_PRODUCT_DOCUMENTATION,
                     scopes=(),retention=None,evidence_id="EVID-PUBLICDOC1")
        r=self.audit(public)
        self.assertEqual(r.evidence_ids_seen,("EVID-PUBLICDOC1",))
        self.assertEqual(r.claimed_scopes_unverified,())
        self.assertIn("NO_ACTIVE_ACCOUNT_RIGHTS_CLAIM",r.unresolved)
        self.assertFalse(r.raw_ohlcv_retention_allowed)

    def test_public_docs_cannot_fake_scope_or_expiry(self):
        for kw in ({"scopes":(RightsScope.RETAIN_RAW_OHLCV,)},
                   {"expiry":NOW+timedelta(days=1)},
                   {"retention":30}):
            with self.subTest(kw=kw),self.assertRaises(ValueError):
                claim(kind=EvidenceKind.PUBLIC_PRODUCT_DOCUMENTATION,
                      scopes=(),retention=None,**kw)

    def test_account_entitlement_claim_only_read_is_not_retention_or_bt(self):
        r=self.audit(claim())
        self.assertEqual(r.claimed_scopes_unverified,
                         (RightsScope.READ_HISTORICAL,))
        self.assertIn(RightsScope.RETAIN_RAW_OHLCV,r.missing_scope_claims)
        self.assertIn(RightsScope.RESEARCH_BACKTEST,r.missing_scope_claims)
        self.assertFalse(r.provider_authorization_verified)
        self.assertFalse(r.real_backtest_allowed)

    def test_even_claim_of_all_scopes_is_not_a_legal_authorization(self):
        c=claim(scopes=tuple(RightsScope),
                kind=EvidenceKind.VENDOR_RIGHTS_LETTER_CLAIM)
        r=self.audit(c)
        self.assertEqual(r.missing_scope_claims,())
        self.assertEqual(set(r.claimed_scopes_unverified),set(RightsScope))
        self.assertIn("VENDOR_GRANT_AUTHENTICITY_NOT_VERIFIED",r.unresolved)
        self.assertFalse(r.raw_ohlcv_retention_allowed)
        self.assertFalse(r.derived_ohlcv_retention_allowed)
        self.assertFalse(r.real_backtest_allowed)
        with self.assertRaises(PermissionError):
            require_authorized_source(r)

    def test_claim_expired_right_now_is_not_valid_claim(self):
        c=claim(expiry=NOW,scopes=tuple(RightsScope))
        r=self.audit(c)
        self.assertEqual(r.expired_claims,("EVID-2026SSI01",))
        self.assertEqual(r.claimed_scopes_unverified,())
        self.assertEqual(set(r.missing_scope_claims),set(RightsScope))
        self.assertIn("EXPIRED_RIGHTS_CLAIM_PRESENT",r.unresolved)

    def test_future_expiry_is_only_unverified_claim(self):
        c=claim(expiry=NOW+timedelta(days=90))
        r=self.audit(c)
        self.assertEqual(r.expired_claims,())
        self.assertEqual(r.claimed_scopes_unverified,
                         (RightsScope.READ_HISTORICAL,))
        self.assertFalse(r.provider_authorization_verified)

    def test_cross_product_grant_claim_cannot_apply_to_dnse(self):
        with self.assertRaises(ValueError):
            self.audit(claim(),product=DNSE)
        d=claim(product=DNSE,evidence_id="EVID-2026DNSE01")
        r=self.audit(d,product=DNSE)
        self.assertEqual(r.product,DNSE)
        self.assertFalse(r.provider_authorization_verified)

    def test_duplicate_evidence_ids_rejected_even_if_scopes_differ(self):
        a=claim()
        b=claim(scopes=(RightsScope.RESEARCH_BACKTEST,))
        with self.assertRaises(ValueError):
            self.audit(a,b)

    def test_future_dated_record_cannot_be_reviewed_at_earlier_clock(self):
        with self.assertRaises(ValueError):
            self.audit(claim(recorded=NOW+timedelta(seconds=1)))

    def test_opaque_id_must_not_be_url_secret_or_account_number(self):
        for raw in ("https://api.ssi.com.vn/token","KEY-SECRET-abcdef",
                    "EVID-aabb", "EVID-12/34/56","EVID-X", "EVID-ABC def"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                claim(evidence_id=raw)

    def test_bad_scope_type_duplicate_scope_or_collection_rejected(self):
        for raw in ((RightsScope.READ_HISTORICAL,RightsScope.READ_HISTORICAL),
                    ("READ_HISTORICAL",), [RightsScope.READ_HISTORICAL]):
            with self.subTest(raw=raw),self.assertRaises(ValueError):
                claim(scopes=raw)

    def test_retention_claim_rejects_negative_huge_and_bool(self):
        for n in (-1,3651,True,False,"30",3.4):
            with self.subTest(retention=n),self.assertRaises(ValueError):
                claim(retention=n)

    def test_invalid_version_free_text_and_raw_token_rejected(self):
        for value in ("", "ssi v2 secret", "TOKEN=xyz", "https://ssi.com",
                      "../secret"):
            with self.subTest(value=value),self.assertRaises(ValueError):
                claim(version=value)

    def test_naive_timestamps_rejected(self):
        with self.assertRaises(ValueError):
            claim(recorded=NOW.replace(tzinfo=None))
        with self.assertRaises(ValueError):
            claim(expiry=NOW.replace(tzinfo=None))
        with self.assertRaises(ValueError):
            review_unverified_source_claims(
                SSI,(),reviewed_at_utc=NOW.replace(tzinfo=None)
            )

    def test_untyped_inputs_and_overlarge_review_refused(self):
        with self.assertRaises(TypeError):
            review_unverified_source_claims(SSI,[claim()],reviewed_at_utc=NOW)
        with self.assertRaises(TypeError):
            review_unverified_source_claims("SSI",(),reviewed_at_utc=NOW)
        with self.assertRaises(ValueError):
            self.audit(*(claim(evidence_id=f"EVID-{i:08d}") for i in range(129)))

    def test_two_distinct_complementary_claims_never_compose_legal_grant(self):
        a=claim()
        b=claim(evidence_id="EVID-OTHERSCP1",
                scopes=(RightsScope.RESEARCH_BACKTEST,RightsScope.OUT_OF_SAMPLE_EVALUATION))
        r=self.audit(a,b)
        self.assertEqual(len(r.claimed_scopes_unverified),3)
        self.assertGreater(len(r.missing_scope_claims),0)
        self.assertFalse(r.provider_authorization_verified)
        self.assertFalse(r.real_backtest_allowed)

    def test_review_report_contains_only_opaque_docket_metadata(self):
        c=claim(expiry=NOW+timedelta(days=1))
        text=repr(self.audit(c))
        self.assertNotIn("consumerSecret",text)
        self.assertNotIn("X-API-Key",text)
        self.assertNotIn("api.ssi.com.vn",text)
        self.assertNotIn("password",text.lower())
        self.assertFalse(hasattr(self.audit(c),"source_agreement_text"))

    def test_approval_flags_cannot_be_turned_on_by_dataclass_replace(self):
        c=claim(scopes=tuple(RightsScope))
        r=self.audit(c)
        with self.assertRaises(TypeError):
            replace(c,independently_verified=True)
        for field in ("provider_authorization_verified",
                      "production_authorized", "real_backtest_allowed",
                      "raw_ohlcv_retention_allowed", "actionable"):
            with self.subTest(field=field),self.assertRaises(TypeError):
                replace(r,**{field:True})
        with self.assertRaises(FrozenInstanceError):
            r.unresolved=()

    def test_require_boundary_does_not_accept_forged_nonreport(self):
        with self.assertRaises(TypeError):
            require_authorized_source({"approved":True})


if __name__=="__main__":
    unittest.main()
