"""P0.29 conditional head must bind a genuine P0.28 *synthetic* prefix.

All keys generated from throwaway deterministic bytes; no provider data or rights.
"""
import base64
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from swing_trading.native_minute_bar_source_plan import BarProduct
from swing_trading.provider_rights_review import RightsScope
from swing_trading.provider_signed_event_chain import (
    SignedRightsEvent, ClaimedExternalLedgerPin, EventKind, RightsChainRejected,
)
from swing_trading.provider_head_custody import (
    ClaimedCustodianKey, ClaimedMonotonicFloor, CustodyProduct,
    SignedCustodyHead, CustodyRejected, audit_conditional_custody_head,
)

NOW = datetime(2026, 11, 7, 4, 0, tzinfo=timezone.utc)
PLACEHOLDER = base64.b64encode(bytes(64)).decode('ascii')
EVENT_ID = 'KEY-EVENTKEY01'
CUST_ID = 'KEY-CUSTODIAN01'
HEAD_ID = 'HEAD-2026CHAIN001'


class P029Integration(unittest.TestCase):
    def setUp(self):
        self.event_key = Ed25519PrivateKey.from_private_bytes(b'\xa1' * 32)
        self.cust_key = Ed25519PrivateKey.from_private_bytes(b'\xa2' * 32)
        self.event_pub = self.event_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.cust_pub = self.cust_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.key = ClaimedCustodianKey(
            CustodyProduct.SSI_FASTCONNECT_OHLC,CUST_ID,1,self.cust_pub,
            sha256(self.cust_pub).hexdigest(),'EVID-2026CUSTODY01')

    def event(self, kind, *, index=1, prev='0'*64, at=None, expiry=None):
        signed_at = at or (NOW-timedelta(minutes=2)+timedelta(seconds=index))
        proto=SignedRightsEvent(
            BarProduct.SSI_FASTCONNECT_INTRADAY_OHLC,index,prev,
            'EVNT-2026P029%04d' % index,'EVID-2026RIGHT1',
            kind,EVENT_ID,('%032x'%index),signed_at,signed_at,
            expiry if kind is EventKind.GRANT_CANDIDATE else None,
            (RightsScope.READ_HISTORICAL,) if kind is EventKind.GRANT_CANDIDATE else (),
            PLACEHOLDER)
        return replace(proto,signature_base64=base64.b64encode(self.event_key.sign(proto.signing_bytes())).decode())

    def signed_chain(self, kinds=(EventKind.GRANT_CANDIDATE,)):
        events=[]
        for index,kind in enumerate(kinds,start=1):
            events.append(self.event(kind,index=index,prev=events[-1].chain_hash() if events else '0'*64,
                                      expiry=NOW+timedelta(hours=1)))
        return tuple(events)

    def environment(self, *, events=None, source=CustodyProduct.SSI_FASTCONNECT_OHLC):
        events=events or self.signed_chain()
        pin=ClaimedExternalLedgerPin(
            BarProduct.SSI_FASTCONNECT_INTRADAY_OHLC,HEAD_ID,EVENT_ID,self.event_pub,
            sha256(self.event_pub).hexdigest(),len(events),events[-1].chain_hash(),
            NOW-timedelta(seconds=30))
        unsigned=SignedCustodyHead(source,HEAD_ID,CUST_ID,1,EVENT_ID,
            sha256(self.event_pub).hexdigest(),len(events),events[-1].chain_hash(),
            'c'*64,NOW-timedelta(seconds=30),NOW+timedelta(minutes=3),PLACEHOLDER)
        head=replace(unsigned,signature_base64=base64.b64encode(self.cust_key.sign(unsigned.signing_bytes())).decode())
        floor=ClaimedMonotonicFloor(source,CUST_ID,self.key.public_key_sha256,1,1,
            events[0].chain_hash(),'c'*64,NOW-timedelta(minutes=2),NOW-timedelta(minutes=1),
            'EVID-2026FLOOR001')
        return events,pin,head,floor

    def verify(self, *, events=None,pin=None,head=None,floor=None):
        e,p,h,f=self.environment()
        return audit_conditional_custody_head(head or h,self.key,floor or f,
            checked_at_utc=NOW,event_pin=pin or p,events=e if events is None else events)

    def test_valid_one_candidate_cryptographically_binds_but_never_grants(self):
        x=self.verify()
        self.assertTrue(x.conditional_event_chain_integrity)
        self.assertEqual(x.event_chain_state,'SIGNED_CANDIDATE_UNAUTHORIZED')
        self.assertFalse(x.rights_to_read_or_cache)
        self.assertFalse(x.fresh_revocation_stream_authenticated)

    def test_signed_sticky_revocation_remains_not_approved(self):
        events=self.signed_chain((EventKind.GRANT_CANDIDATE, EventKind.PROVIDER_REVOKE,
                                  EventKind.GRANT_CANDIDATE))
        e,p,h,f=self.environment(events=events)
        report=audit_conditional_custody_head(h,self.key,f,checked_at_utc=NOW,event_pin=p,events=e)
        self.assertTrue(report.conditional_event_chain_integrity)
        self.assertEqual(report.event_chain_state,'SIGNED_HOLD_UNAUTHORIZED')
        self.assertFalse(report.rights_to_read_or_cache)

    def test_dropped_signed_event_cannot_masquerade_as_complete_head(self):
        e,p,h,f=self.environment(events=self.signed_chain((EventKind.GRANT_CANDIDATE,EventKind.PROVIDER_REVOKE)))
        with self.assertRaises(RightsChainRejected):
            audit_conditional_custody_head(h,self.key,f,checked_at_utc=NOW,event_pin=p,events=e[:-1])

    def test_pin_tail_other_than_custody_signed_head_rejected(self):
        e,p,h,f=self.environment()
        with self.assertRaisesRegex(CustodyRejected,'not exactly bound'):
            audit_conditional_custody_head(h,self.key,f,checked_at_utc=NOW,
                event_pin=replace(p,expected_tail_sha256='e'*64),events=e)

    def test_event_key_mismatch_rejected_before_p028_verification(self):
        e,p,h,f=self.environment()
        with self.assertRaisesRegex(CustodyRejected,'not exactly bound'):
            audit_conditional_custody_head(h,self.key,f,checked_at_utc=NOW,
                event_pin=replace(p,key_id='KEY-BADKEY1234'),events=e)

    def test_tampered_signed_event_rejected(self):
        e,p,h,f=self.environment()
        bad=(replace(e[0],signature_base64=PLACEHOLDER),)
        with self.assertRaises(RightsChainRejected):
            audit_conditional_custody_head(h,self.key,f,checked_at_utc=NOW,event_pin=p,events=bad)

    def test_older_event_pin_is_rejected_even_with_valid_signatures(self):
        e,p,h,f=self.environment()
        with self.assertRaisesRegex(CustodyRejected,'not exactly bound'):
            audit_conditional_custody_head(h,self.key,f,checked_at_utc=NOW,
                event_pin=replace(p,pinned_at_utc=p.pinned_at_utc-timedelta(seconds=1)),events=e)

    def test_forking_prefix_after_floor_cannot_pass_even_if_resigned(self):
        # Build a valid but different first event, then re-sign later events and
        # pin to that new head; P0.28 alone accepts its self-consistent history,
        # whereas P0.29 must enforce the original high-watermark prefix.
        old,p,h,f = self.environment()
        new_first=self.event(EventKind.GRANT_CANDIDATE,index=1,
                             at=NOW-timedelta(minutes=3),expiry=NOW+timedelta(hours=1))
        new_second=self.event(EventKind.PROVIDER_REVOKE,index=2,prev=new_first.chain_hash(),
                              at=NOW-timedelta(seconds=90))
        newer,newpin,newhead,_=self.environment(events=(new_first,new_second))
        with self.assertRaisesRegex(CustodyRejected,'forked'):
            audit_conditional_custody_head(newhead,self.key,f,checked_at_utc=NOW,
                                           event_pin=newpin,events=newer)

    def test_vcbs_not_in_p028_enum_cannot_inherit_ssi_event_chain(self):
        e,p,h,f=self.environment(source=CustodyProduct.VCBS_MCP_D1)
        # This intentionally fails: VCBS P0.28 event product is not enrolled.
        with self.assertRaises(CustodyRejected):
            audit_conditional_custody_head(h,self.key,f,checked_at_utc=NOW,event_pin=p,events=e)


if __name__ == '__main__':
    unittest.main()
