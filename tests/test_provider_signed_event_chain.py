"""GĐ4/P0.28 synthetic Ed25519 source-rights prefix verification tests.

Only local fixture keys, never real SSI/DNSE credentials or trusted grants.
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
    SignedRightsEvent, ClaimedExternalLedgerPin, RightsChainRejected,
    RightsChainState, EventKind, verify_pinned_rights_event_chain,
    require_rights_chain_authorization,
)

NOW = datetime(2026, 11, 6, 16, 0, tzinfo=timezone.utc)
SSI = BarProduct.SSI_FASTCONNECT_INTRADAY_OHLC
DNSE = BarProduct.DNSE_OPENAPI_OHLC
EMPTY = "0" * 64
SIGNATURE_PLACEHOLDER = base64.b64encode(bytes(64)).decode("ascii")
KEY_ID = "KEY-2026TESTKEY"


def event(kind=EventKind.GRANT_CANDIDATE, *, index=1, previous=EMPTY,
          product=SSI, key_id=KEY_ID, nonce=None, event_id=None,
          published=None, effective=None, expires=None, claims=None):
    pubtime=published or NOW-timedelta(minutes=2)+timedelta(seconds=index)
    efftime=effective or pubtime
    if claims is None:
        claims=(RightsScope.READ_HISTORICAL, RightsScope.RESEARCH_BACKTEST) if (
            kind is EventKind.GRANT_CANDIDATE
        ) else ()
    if expires is None and kind is EventKind.GRANT_CANDIDATE:
        expires=NOW+timedelta(hours=1)
    return SignedRightsEvent(
        product, index, previous,
        event_id or f"EVNT-2026TEST{index:04d}", "EVID-2026RIGHT1",
        kind, key_id, nonce or f"{index:032x}",
        pubtime, efftime, expires, claims, SIGNATURE_PLACEHOLDER,
    )


class SignedRightsEventChainTests(unittest.TestCase):
    def setUp(self):
        self.key=Ed25519PrivateKey.from_private_bytes(b"\x67"*32)
        self.other_key=Ed25519PrivateKey.from_private_bytes(b"\x68"*32)
        self.public=self.key.public_key().public_bytes(
            serialization.Encoding.Raw,serialization.PublicFormat.Raw
        )

    def sign(self, e, *, key=None):
        signer=self.key if key is None else key
        return replace(e, signature_base64=base64.b64encode(
            signer.sign(e.signing_bytes())
        ).decode("ascii"))

    def chain(self, *kinds, product=SSI):
        previous=EMPTY
        events=[]
        for i,k in enumerate(kinds,1):
            e=self.sign(event(k,index=i,previous=previous,product=product))
            events.append(e)
            previous=e.chain_hash()
        return tuple(events)

    def pin(self, events, *, product=SSI, key_id=KEY_ID, public=None,
            expected_tail=None, expected_sequence=None,
            pinned_at=None, fingerprint=None):
        public=self.public if public is None else public
        return ClaimedExternalLedgerPin(
            product, "HEAD-2026TEST0001", key_id, public,
            fingerprint or sha256(public).hexdigest(),
            len(events) if expected_sequence is None else expected_sequence,
            events[-1].chain_hash() if expected_tail is None else expected_tail,
            NOW-timedelta(seconds=1) if pinned_at is None else pinned_at
        )

    def verify(self, events, *, pin=None, now=NOW):
        return verify_pinned_rights_event_chain(
            events, self.pin(events) if pin is None else pin,
            checked_at_utc=now
        )

    def test_signed_single_candidate_is_only_cryptographic_integrity(self):
        chain=self.chain(EventKind.GRANT_CANDIDATE)
        result=self.verify(chain)
        self.assertEqual(result.verified_events,1)
        self.assertEqual(result.state,RightsChainState.SIGNED_CANDIDATE_UNAUTHORIZED)
        self.assertTrue(result.signature_integrity_verified)
        for attr in (
            "signer_authority_verified","head_custody_independently_verified",
            "current_revocation_freshness_verified","permission_to_read_or_cache",
            "backtest_allowed","actionable",
        ):
            self.assertFalse(getattr(result,attr))
        with self.assertRaises(PermissionError):
            require_rights_chain_authorization(result)

    def test_crypto_proof_not_external_vendor_signer_identity(self):
        chain=self.chain(EventKind.GRANT_CANDIDATE)
        pin=self.pin(chain)
        self.assertFalse(pin.pinned_by_independent_provider)
        self.assertFalse(pin.live_revocation_freshness_verified)
        self.assertFalse(self.verify(chain,pin=pin).signer_authority_verified)

    def test_signed_revoke_is_irreversible_hold(self):
        chain=self.chain(EventKind.GRANT_CANDIDATE,EventKind.PROVIDER_REVOKE)
        r=self.verify(chain)
        self.assertEqual(r.state,RightsChainState.SIGNED_HOLD_UNAUTHORIZED)
        self.assertFalse(r.permission_to_read_or_cache)

    def test_signed_security_suspension_is_hold(self):
        chain=self.chain(EventKind.GRANT_CANDIDATE,EventKind.SECURITY_SUSPEND)
        self.assertEqual(self.verify(chain).state,RightsChainState.SIGNED_HOLD_UNAUTHORIZED)

    def test_signed_later_candidate_does_not_release_old_revocation(self):
        chain=self.chain(EventKind.GRANT_CANDIDATE,EventKind.PROVIDER_REVOKE,
                         EventKind.GRANT_CANDIDATE)
        self.assertEqual(self.verify(chain).state,RightsChainState.SIGNED_HOLD_UNAUTHORIZED)

    def test_expired_candidate_is_not_valid_even_with_fresh_head(self):
        e=event(expires=NOW)
        events=(self.sign(e),)
        self.assertEqual(self.verify(events).state,
                         RightsChainState.SIGNED_CANDIDATE_EXPIRED)

    def test_expired_candidate_never_becomes_live_at_exact_cutoff(self):
        e=event(expires=NOW+timedelta(seconds=1))
        events=(self.sign(e),)
        new_time=NOW+timedelta(seconds=1)
        p=self.pin(events,pinned_at=NOW)
        self.assertEqual(self.verify(events,pin=p,now=new_time).state,
                         RightsChainState.SIGNED_CANDIDATE_EXPIRED)

    def test_invalid_signature_on_tampered_scopes_rejected(self):
        chain=self.chain(EventKind.GRANT_CANDIDATE)
        tampered=(replace(chain[0],
                          scope_claims=(RightsScope.RETAIN_RAW_OHLCV,)),)
        with self.assertRaises(RightsChainRejected):
            self.verify(tampered,pin=self.pin(tampered))

    def test_wrong_signing_key_rejected_even_if_pin_has_real_public(self):
        e=self.sign(event(),key=self.other_key)
        with self.assertRaises(RightsChainRejected):
            self.verify((e,))

    def test_public_key_fingerprint_mismatch_rejected(self):
        chain=self.chain(EventKind.GRANT_CANDIDATE)
        with self.assertRaises(RightsChainRejected):
            self.pin(chain,fingerprint="f"*64)

    def test_valid_other_key_cannot_impersonate_expected_key_with_same_pin(self):
        chain=self.chain(EventKind.GRANT_CANDIDATE)
        other_public=self.other_key.public_key().public_bytes(
            serialization.Encoding.Raw,serialization.PublicFormat.Raw
        )
        pin=self.pin(chain,public=other_public)
        with self.assertRaises(RightsChainRejected):
            self.verify(chain,pin=pin)

    def test_wrong_pinned_chain_tip_rejected(self):
        chain=self.chain(EventKind.GRANT_CANDIDATE)
        with self.assertRaises(RightsChainRejected):
            self.verify(chain,pin=self.pin(chain,expected_tail="f"*64))

    def test_truncated_chain_vs_external_tail_and_sequence_rejected(self):
        chain=self.chain(EventKind.GRANT_CANDIDATE,EventKind.PROVIDER_REVOKE)
        with self.assertRaises(RightsChainRejected):
            self.verify(chain[:1],pin=self.pin(chain))

    def test_no_events_even_with_forged_head_rejected(self):
        chain=self.chain(EventKind.GRANT_CANDIDATE)
        with self.assertRaises(RightsChainRejected):
            self.verify((),pin=self.pin(chain))

    def test_reordered_chain_rejected(self):
        chain=self.chain(EventKind.GRANT_CANDIDATE,EventKind.PROVIDER_REVOKE)
        with self.assertRaises(RightsChainRejected):
            self.verify(tuple(reversed(chain)),pin=self.pin(chain))

    def test_chain_link_tamper_with_updated_signature_rejected(self):
        chain=self.chain(EventKind.GRANT_CANDIDATE,EventKind.PROVIDER_REVOKE)
        wrong=self.sign(replace(chain[1],previous_sha256="f"*64))
        with self.assertRaises(RightsChainRejected):
            self.verify((chain[0],wrong),pin=self.pin((chain[0],wrong)))

    def test_mixed_product_denied_even_with_signed_dnse_event(self):
        first=self.chain(EventKind.GRANT_CANDIDATE)[0]
        second=self.sign(event(EventKind.SECURITY_SUSPEND,index=2,
                               previous=first.chain_hash(),product=DNSE))
        with self.assertRaises(RightsChainRejected):
            self.verify((first,second),pin=self.pin((first,second)))

    def test_mismatched_key_id_denied_even_with_valid_signature(self):
        first=self.chain(EventKind.GRANT_CANDIDATE)[0]
        second=self.sign(event(EventKind.SECURITY_SUSPEND,index=2,
                              previous=first.chain_hash(),
                              key_id="KEY-DIFFERENT1"))
        with self.assertRaises(RightsChainRejected):
            self.verify((first,second),pin=self.pin((first,second)))

    def test_replayed_nonce_rejected_even_with_distinct_signatures(self):
        first=self.chain(EventKind.GRANT_CANDIDATE)[0]
        second=self.sign(event(EventKind.PROVIDER_REVOKE,index=2,
                               previous=first.chain_hash(),nonce=first.nonce_hex))
        with self.assertRaises(RightsChainRejected):
            self.verify((first,second),pin=self.pin((first,second)))

    def test_duplicate_event_id_rejected_even_with_distinct_nonces(self):
        first=self.chain(EventKind.GRANT_CANDIDATE)[0]
        second=self.sign(event(EventKind.SECURITY_SUSPEND,index=2,
                               previous=first.chain_hash(),event_id=first.event_id))
        with self.assertRaises(RightsChainRejected):
            self.verify((first,second),pin=self.pin((first,second)))

    def test_future_published_event_fails_before_crypto_authority(self):
        candidate=self.sign(event(published=NOW+timedelta(seconds=1)))
        with self.assertRaises(RightsChainRejected):
            self.verify((candidate,))

    def test_nonmonotone_publication_time_rejected(self):
        first=self.chain(EventKind.GRANT_CANDIDATE)[0]
        second=self.sign(event(EventKind.SECURITY_SUSPEND,index=2,
                               previous=first.chain_hash(),
                               published=first.published_at_utc-timedelta(seconds=1)))
        with self.assertRaises(RightsChainRejected):
            self.verify((first,second),pin=self.pin((first,second)))

    def test_stale_or_future_external_pin_rejected(self):
        chain=self.chain(EventKind.GRANT_CANDIDATE)
        for date in (NOW-timedelta(minutes=5,seconds=1),
                     NOW+timedelta(microseconds=1)):
            with self.subTest(date=date),self.assertRaises(RightsChainRejected):
                self.verify(chain,pin=self.pin(chain,pinned_at=date))

    def test_typed_pin_and_event_collection_required(self):
        chain=self.chain(EventKind.GRANT_CANDIDATE)
        with self.assertRaises(TypeError):
            self.verify(list(chain),pin=self.pin(chain))
        with self.assertRaises(TypeError):
            self.verify(chain,pin={"approved":True})
        with self.assertRaises(TypeError):
            require_rights_chain_authorization({"signed":True})

    def test_empty_or_invalid_scopes_rejected(self):
        for scopes in ((), ("READ_HISTORICAL",), (RightsScope.READ_HISTORICAL,)*2):
            with self.subTest(scopes=scopes),self.assertRaises(RightsChainRejected):
                event(claims=scopes)

    def test_hold_with_scopes_or_expiry_is_not_regrant(self):
        with self.assertRaises(RightsChainRejected):
            event(EventKind.PROVIDER_REVOKE,claims=(RightsScope.READ_HISTORICAL,))
        with self.assertRaises(RightsChainRejected):
            event(EventKind.SECURITY_SUSPEND,
                  expires=NOW+timedelta(hours=1))

    def test_unknown_key_id_nonce_schema_and_signature_rejected(self):
        base=event()
        for k,v in (
            ("key_id","KEY-abc"),
            ("event_id","../bad-event"),
            ("nonce_hex","ABC"),
            ("signature_base64","not-base64"),
            ("signature_base64",base64.b64encode(bytes(32)).decode()),
            ("sequence",True),
        ):
            with self.subTest(k=k),self.assertRaises((RightsChainRejected,TypeError)):
                replace(base,**{k:v})

    def test_effective_timestamp_after_publication_rejected(self):
        with self.assertRaises(RightsChainRejected):
            event(effective=NOW,published=NOW-timedelta(seconds=1))

    def test_naive_time_rejected(self):
        with self.assertRaises(ValueError):
            event(published=NOW.replace(tzinfo=None))
        chain=self.chain(EventKind.GRANT_CANDIDATE)
        with self.assertRaises(ValueError):
            self.pin(chain,pinned_at=NOW.replace(tzinfo=None))
        with self.assertRaises(ValueError):
            self.verify(chain,now=NOW.replace(tzinfo=None))

    def test_signed_event_output_does_not_contain_credentials_or_quotes(self):
        chain=self.chain(EventKind.GRANT_CANDIDATE)
        r=self.verify(chain)
        txt=repr(r)+repr(self.pin(chain))
        for forbidden in ("consumerSecret","X-API-Key","password","ohlcv_price",
                          "account_number"):
            self.assertNotIn(forbidden,txt)
        self.assertFalse(hasattr(r,"market_data"))
        self.assertFalse(hasattr(r,"private_key"))

    def test_dataclass_property_cannot_promote_authorization(self):
        chain=self.chain(EventKind.GRANT_CANDIDATE)
        r=self.verify(chain)
        with self.assertRaises(TypeError):
            replace(r,permission_to_read_or_cache=True)
        with self.assertRaises(TypeError):
            replace(self.pin(chain),pinned_by_independent_provider=True)
        with self.assertRaises(FrozenInstanceError):
            r.state=RightsChainState.SIGNED_HOLD_UNAUTHORIZED

    def test_pin_can_be_created_by_caller_but_cannot_be_approved(self):
        chain=self.chain(EventKind.GRANT_CANDIDATE)
        forged_head=self.pin(chain)
        self.assertEqual(self.verify(chain,pin=forged_head).verified_events,1)
        self.assertFalse(forged_head.pinned_by_independent_provider)
        self.assertFalse(self.verify(chain,pin=forged_head).backtest_allowed)

    def test_no_validity_claim_without_full_tail(self):
        chain=self.chain(EventKind.GRANT_CANDIDATE, EventKind.PROVIDER_REVOKE)
        with self.assertRaises(RightsChainRejected):
            self.verify((chain[0],),pin=self.pin(chain,expected_sequence=1))

    def test_enforces_product_specific_pinned_head(self):
        chain=self.chain(EventKind.GRANT_CANDIDATE)
        with self.assertRaises(RightsChainRejected):
            self.verify(chain,pin=self.pin(chain,product=DNSE))


if __name__=="__main__":
    unittest.main()
