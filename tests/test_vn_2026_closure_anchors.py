"""2026 HOSE/HNX announcement date anchors: NOT an official full calendar."""
import unittest
from datetime import date, datetime, timedelta, timezone

from swing_trading.d1_atr_reconciliation import (
    D1ExpectedSession, D1SessionInventory,
)
from swing_trading.vn_2026_closure_anchors import (
    ClosureAuditState, audit_2026_notice_closure_collisions,
    known_2026_nontrading_dates, official_notice_urls,
)

UTC=timezone.utc


def inventory(*days):
    slots=tuple(
        D1ExpectedSession(
            f"fixture-{d.isoformat()}",
            datetime(d.year,d.month,d.day,2,0,tzinfo=UTC),
            datetime(d.year,d.month,d.day,8,0,tzinfo=UTC),
        ) for d in days
    )
    return D1SessionInventory(
        "synthetic-date-list", "external-calendar-unapproved",
        "fixture-v1", datetime(2025,12,1,tzinfo=UTC), slots,
    )


class KnownClosureEvidenceTests(unittest.TestCase):
    def test_hose_published_holiday_must_not_be_in_expected_inventory(self):
        for day in (
            date(2026,1,2),date(2026,2,16),date(2026,4,27),
            date(2026,4,30),date(2026,8,31),date(2026,9,2),
        ):
            with self.subTest(day=day):
                result=audit_2026_notice_closure_collisions(
                    inventory(day), exchange="HOSE")
                self.assertEqual(result.state,ClosureAuditState.BLOCKED)
                self.assertEqual(result.reason,
                                 "SESSION_ON_PUBLISHED_EXCHANGE_CLOSURE")
                self.assertEqual(result.conflicting_session_ids,
                                 (f"fixture-{day.isoformat()}",))
                self.assertFalse(result.full_calendar_certified)

    def test_hnx_jan_2_amendment_is_honored(self):
        result=audit_2026_notice_closure_collisions(
            inventory(date(2026,1,2)),exchange="HNX")
        self.assertEqual(result.state,ClosureAuditState.BLOCKED)
        self.assertEqual(len(result.notice_urls),2)

    def test_government_make_up_saturdays_still_have_no_stock_trading(self):
        for exchange in ("HOSE","HNX"):
            for d in (date(2026,1,10),date(2026,8,22)):
                with self.subTest(exchange=exchange,date=d):
                    out=audit_2026_notice_closure_collisions(
                        inventory(d),exchange=exchange)
                    self.assertEqual(out.state,ClosureAuditState.BLOCKED)

    def test_not_on_announced_closures_still_uncertified(self):
        obj=inventory(date(2026,1,5),date(2026,1,6))
        for exchange in ("HOSE","HNX"):
            result=audit_2026_notice_closure_collisions(obj,exchange=exchange)
            self.assertEqual(result.state,
                             ClosureAuditState.NO_KNOWN_COLLISION_UNCERTIFIED)
            self.assertFalse(result.full_calendar_certified)
            self.assertFalse(result.actionable)

    def test_year_outside_notice_scope_rejected(self):
        result=audit_2026_notice_closure_collisions(
            inventory(date(2027,1,5)),exchange="HOSE")
        self.assertEqual(result.state,ClosureAuditState.BLOCKED)
        self.assertEqual(result.reason,"YEAR_OUTSIDE_2026_NOTICE_SCOPE")

    def test_upcom_not_inferred_from_hnx_announcement(self):
        with self.assertRaises(ValueError):
            known_2026_nontrading_dates("UPCOM")
        with self.assertRaises(ValueError):
            audit_2026_notice_closure_collisions(
                inventory(date(2026,1,2)),exchange="UPCOM")

    def test_official_links_are_explicit(self):
        self.assertIn("hsx.vn",official_notice_urls("HOSE")[0])
        self.assertTrue(all("hnx.vn" in x for x in official_notice_urls("HNX")))
        self.assertIn(date(2026,2,19),known_2026_nontrading_dates("HOSE"))

    def test_input_must_be_typed_inventory(self):
        with self.assertRaises(TypeError):
            audit_2026_notice_closure_collisions(
                ("date-string",),exchange="HOSE")


if __name__=="__main__":
    unittest.main()
