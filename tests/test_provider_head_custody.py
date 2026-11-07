"""P0.29 synthetic-only custody-head/floor/rotation negative-path tests."""
import base64
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from swing_trading.provider_head_custody import (
    ClaimedCustodianKey, ClaimedMonotonicFloor, ConditionalHeadAudit,
    CustodyProduct, CustodyRejected, DualSignedKeyRotation, SignedCustodyHead,
    audit_conditional_custody_head, require_authenticated_provider_rights,
)

NOW = datetime(2026, 11, 7, 4, 0, tzinfo=timezone.utc)
K1 = 'KEY-CUSTODIAN01'
K2 = 'KEY-CUSTODIAN02'
EVENT = 'KEY-EVENTKEY01'
P = CustodyProduct.SSI_FASTCONNECT_OHLC
B = 'b' * 64
A = 'a' * 64
C = 'c' * 64
D = 'd' * 64
SIG = base64.b64encode(bytes(64)).decode('ascii')


class P029CustodyTests(unittest.TestCase):
    def setUp(self):
        self.priv = Ed25519PrivateKey.from_private_bytes(b'\x91' * 32)
        self.priv2 = Ed25519PrivateKey.from_private_bytes(b'\x92' * 32)
        self.key = self.mkkey(self.priv, K1, 1)
        self.floor = self.mkfloor()
        self.head = self.mkhead()

    def mkkey(self, private, kid, epoch, product=P):
        pub = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        return ClaimedCustodianKey(product, kid, epoch, pub, sha256(pub).hexdigest(), 'EVID-2026CUSTODY01')

    def mkfloor(self, **kwargs):
        data=dict(product=P, custody_key_id=K1, custody_key_sha256=self.key.public_key_sha256,
                  custody_epoch=1, sequence=2, tail_sha256=A, account_binding_sha256_claim=C,
                  last_issued_at_utc=NOW-timedelta(minutes=2),
                  observed_at_utc=NOW-timedelta(minutes=1, seconds=40),
                  custody_evidence_id='EVID-2026FLOOR001')
        return ClaimedMonotonicFloor(**(data|kwargs))

    def mkhead(self, key=None, private=None, **kwargs):
        key = key or self.key
        private = private or self.priv
        data=dict(product=key.product, head_id='HEAD-2026CHAIN001',
                  custody_key_id=key.key_id, custody_epoch=key.epoch,
                  event_key_id=EVENT, event_public_key_sha256=D,
                  sequence=3, tail_sha256=B, account_binding_sha256_claim=C,
                  issued_at_utc=NOW-timedelta(seconds=30),
                  expires_at_utc=NOW+timedelta(minutes=3), signature_base64=SIG)
        unsigned=SignedCustodyHead(**(data|kwargs))
        return replace(unsigned,signature_base64=base64.b64encode(private.sign(unsigned.signing_bytes())).decode())

    def audit(self, *, head=None, key=None, floor=None, now=None, **kwargs):
        return audit_conditional_custody_head(head or self.head, key or self.key,
                                              floor or self.floor, checked_at_utc=now or NOW, **kwargs)

    def mkrotation(self, newkey, *, private=None, oldprivate=None, floor=None, head=None, **kwargs):
        floor=floor or self.floor
        head=head or self.mkhead(key=newkey, private=private or self.priv2)
        unsigned=DualSignedKeyRotation(
            product=P, previous_key_id=self.key.key_id,
            previous_key_sha256=self.key.public_key_sha256, previous_epoch=1,
            next_key_id=newkey.key_id, next_key_sha256=newkey.public_key_sha256,
            next_epoch=2, floor_sequence=floor.sequence, floor_tail_sha256=floor.tail_sha256,
            account_binding_sha256_claim=C,
            rotated_at_utc=NOW-timedelta(seconds=60), nonce_hex='1'*32,
            previous_signature_base64=SIG, next_signature_base64=SIG,
        )
        unsigned=replace(unsigned,**kwargs)
        sig1=base64.b64encode((oldprivate or self.priv).sign(unsigned.signing_bytes())).decode()
        sig2=base64.b64encode((private or self.priv2).sign(unsigned.signing_bytes())).decode()
        return replace(unsigned,previous_signature_base64=sig1,next_signature_base64=sig2)

    def test_signed_advanced_head_conditional_only(self):
        x=self.audit()
        self.assertTrue(x.custodian_signature_integrity)
        self.assertTrue(x.relative_floor_held)
        self.assertTrue(x.age_within_local_budget)
        self.assertFalse(x.conditional_event_chain_integrity)
        self.assertEqual((x.product,x.sequence,x.tail_sha256),(P,3,B))

    def test_not_authorized_even_when_crypto_matches(self):
        x=self.audit()
        for name in ('vendor_key_origin_verified','fresh_revocation_stream_authenticated',
                     'anti_rollback_across_restarts_verified','rights_to_read_or_cache',
                     'market_indicators_allowed','historical_backtest_allowed',
                     'trading_actionable'):
            self.assertFalse(getattr(x,name),name)
        with self.assertRaises(PermissionError):
            require_authenticated_provider_rights(x)

    def test_must_supply_typed_input(self):
        with self.assertRaises(TypeError):
            self.audit(head='bad')
        with self.assertRaises(TypeError):
            self.audit(key='bad')
        with self.assertRaises(TypeError):
            self.audit(floor='bad')
        with self.assertRaises(TypeError):
            require_authenticated_provider_rights('not_report')

    def test_cannot_mutate_reports_or_keys(self):
        with self.assertRaises(FrozenInstanceError):
            self.key.epoch=999
        with self.assertRaises(FrozenInstanceError):
            self.audit().relative_floor_held=False

    def test_key_owner_status_always_false(self):
        self.assertFalse(self.key.vendor_key_owner_verified)
        self.assertFalse(self.key.independently_enrolled)
        self.assertFalse(self.floor.externally_protected_storage_verified)

    def test_no_credentials_raw_payload_or_secrets_in_repr(self):
        self.assertNotIn(str(self.key.public_key),repr(self.key))
        self.assertNotIn(self.head.signature_base64,repr(self.head))
        self.assertNotIn(str(self.priv),repr(self.audit()))

    def test_same_sequence_same_tail_fresh_resign_valid(self):
        head=self.mkhead(sequence=2,tail_sha256=A)
        self.assertEqual(self.audit(head=head).sequence,2)

    def test_lower_sequence_rejected(self):
        with self.assertRaisesRegex(CustodyRejected,'rolled back'):
            self.audit(head=self.mkhead(sequence=1))

    def test_equal_sequence_fork_rejected(self):
        with self.assertRaisesRegex(CustodyRejected,'Equal-sequence fork'):
            self.audit(head=self.mkhead(sequence=2,tail_sha256=B))

    def test_same_epoch_key_substitution_rejected(self):
        newkey=self.mkkey(self.priv2,K2,1)
        with self.assertRaisesRegex(CustodyRejected,'same-epoch'):
            self.audit(head=self.mkhead(key=newkey,private=self.priv2),key=newkey)

    def test_head_key_mismatch_rejected(self):
        with self.assertRaisesRegex(CustodyRejected,'product/key'):
            self.audit(head=self.mkhead(custody_key_id=K2))

    def test_product_cross_provider_rejected(self):
        other=CustodyProduct.DNSE_OPENAPI_OHLC
        key=self.mkkey(self.priv,K1,1,product=other)
        with self.assertRaisesRegex(CustodyRejected,'product/key'):
            self.audit(key=key)

    def test_vcbs_product_is_typed_but_not_approved(self):
        key=self.mkkey(self.priv,K1,1,product=CustodyProduct.VCBS_MCP_D1)
        floor=self.mkfloor(product=CustodyProduct.VCBS_MCP_D1)
        head=self.mkhead(key=key)
        x=self.audit(head=head,key=key,floor=floor)
        self.assertEqual(x.product,CustodyProduct.VCBS_MCP_D1)
        self.assertFalse(x.rights_to_read_or_cache)

    def test_signature_tampered_head_rejected(self):
        unsigned=replace(self.head,sequence=4)
        with self.assertRaisesRegex(CustodyRejected,'signature'):
            self.audit(head=unsigned)

    def test_wrong_public_key_with_same_id_fingerprint_rejected(self):
        key2=self.mkkey(self.priv2,K1,1)
        floor=self.mkfloor(custody_key_sha256=key2.public_key_sha256)
        with self.assertRaisesRegex(CustodyRejected,'signature'):
            self.audit(key=key2,floor=floor)

    def test_invalid_key_fingerprint_rejected(self):
        with self.assertRaisesRegex(CustodyRejected,'fingerprint'):
            replace(self.key,public_key_sha256=D)

    def test_noncanonical_signature_rejected(self):
        with self.assertRaises(CustodyRejected):
            replace(self.head,signature_base64=SIG.rstrip('='))

    def test_future_head_rejected(self):
        head=self.mkhead(issued_at_utc=NOW+timedelta(seconds=1),expires_at_utc=NOW+timedelta(minutes=2))
        with self.assertRaisesRegex(CustodyRejected,'future'):
            self.audit(head=head)

    def test_stale_head_rejected(self):
        head=self.mkhead(issued_at_utc=NOW-timedelta(minutes=6),expires_at_utc=NOW-timedelta(minutes=2))
        with self.assertRaisesRegex(CustodyRejected,'stale'):
            self.audit(head=head)

    def test_head_expiry_equal_now_rejected(self):
        head=self.mkhead(issued_at_utc=NOW-timedelta(minutes=2),expires_at_utc=NOW)
        with self.assertRaisesRegex(CustodyRejected,'expired'):
            self.audit(head=head)

    def test_head_ttl_over_five_minutes_rejected(self):
        with self.assertRaisesRegex(CustodyRejected,'five minutes'):
            self.mkhead(expires_at_utc=NOW+timedelta(minutes=7))

    def test_floor_observed_future_rejected(self):
        with self.assertRaisesRegex(CustodyRejected,'Floor is from the future'):
            self.audit(floor=self.mkfloor(observed_at_utc=NOW+timedelta(seconds=1)))

    def test_floor_issue_after_observation_rejected(self):
        with self.assertRaisesRegex(CustodyRejected,'Floor observed before'):
            self.mkfloor(observed_at_utc=NOW-timedelta(minutes=3))

    def test_account_switch_rejected_even_with_valid_signature(self):
        with self.assertRaisesRegex(CustodyRejected,'binding'):
            self.audit(head=self.mkhead(account_binding_sha256_claim='d'*64))

    def test_same_key_for_head_and_event_rejected(self):
        with self.assertRaisesRegex(CustodyRejected,'distinct'):
            self.audit(head=self.mkhead(event_public_key_sha256=self.key.public_key_sha256))

    def test_head_issue_older_than_floor_rejected(self):
        with self.assertRaisesRegex(CustodyRejected,'issuance rolled back'):
            self.audit(floor=self.mkfloor(last_issued_at_utc=NOW-timedelta(seconds=20),
                                          observed_at_utc=NOW-timedelta(seconds=10)))

    def test_epoch_downgrade_rejected(self):
        floor=self.mkfloor(custody_epoch=2)
        with self.assertRaisesRegex(CustodyRejected,'epoch downgrade'):
            self.audit(floor=floor)

    def test_epoch_skip_rejected(self):
        key3=self.mkkey(self.priv2,K2,3)
        head=self.mkhead(key=key3,private=self.priv2)
        with self.assertRaisesRegex(CustodyRejected,'epoch downgrade/skip'):
            self.audit(head=head,key=key3)

    def test_one_epoch_change_without_rotation_fails(self):
        key2=self.mkkey(self.priv2,K2,2)
        with self.assertRaisesRegex(CustodyRejected,'Dual-signature'):
            self.audit(head=self.mkhead(key=key2,private=self.priv2),key=key2)

    def test_valid_dual_rotation_is_still_untrusted(self):
        key2=self.mkkey(self.priv2,K2,2)
        head=self.mkhead(key=key2,private=self.priv2)
        rotation=self.mkrotation(key2)
        result=self.audit(head=head,key=key2,rotation=rotation,previous_key=self.key)
        self.assertTrue(result.dual_rotation_signatures_verified)
        self.assertFalse(result.vendor_key_origin_verified)
        self.assertFalse(result.anti_rollback_across_restarts_verified)

    def test_bad_old_key_rotation_signature_rejected(self):
        key2=self.mkkey(self.priv2,K2,2)
        head=self.mkhead(key=key2,private=self.priv2)
        rot=self.mkrotation(key2,oldprivate=self.priv2)
        with self.assertRaisesRegex(CustodyRejected,'signature'):
            self.audit(head=head,key=key2,rotation=rot,previous_key=self.key)

    def test_bad_new_key_rotation_signature_rejected(self):
        key2=self.mkkey(self.priv2,K2,2)
        head=self.mkhead(key=key2,private=self.priv2)
        rot=self.mkrotation(key2,private=self.priv)
        with self.assertRaisesRegex(CustodyRejected,'signature'):
            self.audit(head=head,key=key2,rotation=rot,previous_key=self.key)

    def test_rotation_wrong_floor_tail_rejected(self):
        key2=self.mkkey(self.priv2,K2,2)
        head=self.mkhead(key=key2,private=self.priv2)
        rot=self.mkrotation(key2,floor_sequence=4)
        with self.assertRaisesRegex(CustodyRejected,'Rotation does not bind'):
            self.audit(head=head,key=key2,rotation=rot,previous_key=self.key)

    def test_rotation_wrong_product_rejected(self):
        key2=self.mkkey(self.priv2,K2,2)
        head=self.mkhead(key=key2,private=self.priv2)
        rot=self.mkrotation(key2,product=CustodyProduct.DNSE_MCP_D1)
        with self.assertRaisesRegex(CustodyRejected,'Rotation does not bind'):
            self.audit(head=head,key=key2,rotation=rot,previous_key=self.key)

    def test_rotation_time_before_floor_rejected(self):
        key2=self.mkkey(self.priv2,K2,2)
        head=self.mkhead(key=key2,private=self.priv2)
        rot=self.mkrotation(key2,rotated_at_utc=NOW-timedelta(minutes=5))
        with self.assertRaisesRegex(CustodyRejected,'Rotation time'):
            self.audit(head=head,key=key2,rotation=rot,previous_key=self.key)

    def test_rotation_old_public_key_not_floor_rejected(self):
        key2=self.mkkey(self.priv2,K2,2)
        head=self.mkhead(key=key2,private=self.priv2)
        rot=self.mkrotation(key2)
        wrong_old=self.mkkey(self.priv2,K1,1)
        with self.assertRaisesRegex(CustodyRejected,'Previous rotation key'):
            self.audit(head=head,key=key2,rotation=rot,previous_key=wrong_old)

    def test_same_epoch_rotation_not_allowed(self):
        with self.assertRaisesRegex(CustodyRejected,'same-epoch'):
            self.audit(rotation='not-valid')

    def test_pairing_event_pin_and_events_required(self):
        with self.assertRaisesRegex(CustodyRejected,'must be paired'):
            self.audit(event_pin='fake')
        with self.assertRaisesRegex(CustodyRejected,'must be paired'):
            self.audit(events=())

    def test_incorrect_types_of_event_pin_rejected(self):
        # The real P0.28 bridge is available in GitHub CI, not required for the
        # standalone local crypto/floor suite.
        with self.assertRaises((ImportError, CustodyRejected)):
            self.audit(events=(),event_pin='fake')

    def test_invalid_clock_rejected(self):
        with self.assertRaises(CustodyRejected):
            self.audit(now=NOW.replace(tzinfo=None))
        with self.assertRaises(CustodyRejected):
            self.audit(now=NOW.astimezone(timezone(timedelta(hours=7))))

    def test_unknown_or_untyped_products_rejected(self):
        with self.assertRaises(TypeError):
            replace(self.head,product='VCBS')
        with self.assertRaises(TypeError):
            replace(self.key,product='SSI')

    def test_no_zero_age_or_future_expiry_override(self):
        with self.assertRaises(CustodyRejected):
            self.mkhead(expires_at_utc=NOW-timedelta(minutes=1),
                        issued_at_utc=NOW-timedelta(minutes=1))


if __name__ == '__main__':
    unittest.main()
