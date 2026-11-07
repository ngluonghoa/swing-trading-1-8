"""Synthetic VCBS capability and nonactionable RAW D1 reference tests."""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import unittest

from swing_trading.vcbs_source_contract import (
    VcbsFeed, VcbsFetchScope, VcbsSourceContract, VcbsRawDailyReference,
    vcbs_capability, inspect_vcbs_raw_daily_row,
)

STAMP = datetime(2026, 11, 7, 1, 30, tzinfo=timezone.utc)


def row():
    # ALL SYNTHETIC. No real VCBS price, volume, or saved market payload.
    return {
        "tradingDate": "2026-11-06", "openPrice": 100, "highPrice": 108,
        "lowPrice": 98, "closePrice": 105, "price": 105,
        "adjClosePrice": 101, "volume": 900, "priceBasis": "raw",
        "price_unit": "VND", "volumeScope": "matched",
    }


class VcbsContractTests(unittest.TestCase):
    def test_six_surfaces_explicit(self):
        self.assertEqual(len(VcbsFeed), 6)
        self.assertEqual({s.feed for s in map(vcbs_capability, VcbsFeed)}, set(VcbsFeed))

    def test_daily_history_range_is_not_revision_delta(self):
        a = vcbs_capability(VcbsFeed.DAILY_HISTORY)
        self.assertIs(a.fetch_scope, VcbsFetchScope.DATE_WINDOW)
        self.assertTrue(a.raw_ohlcv_candidate)
        self.assertFalse(a.has_change_cursor)
        self.assertFalse(a.source_freshness_verified)
        self.assertFalse(a.authorized_for_retention)

    def test_intraday_price_only_never_1m_ohlcv(self):
        a = vcbs_capability(VcbsFeed.SESSION_PRICE_SERIES)
        self.assertIs(a.fetch_scope, VcbsFetchScope.CURRENT_SESSION_ONLY)
        self.assertFalse(a.full_minute_ohlcv)
        self.assertFalse(a.raw_ohlcv_candidate)

    def test_wm_aggregated_unqualified(self):
        self.assertFalse(vcbs_capability(VcbsFeed.WEEKLY_MONTHLY_HISTORY).raw_ohlcv_candidate)

    def test_quote_batch_not_daily_candle(self):
        self.assertFalse(vcbs_capability(VcbsFeed.QUOTE_BATCH).raw_ohlcv_candidate)

    def test_third_party_indicators_not_canonical_indicator(self):
        a = vcbs_capability(VcbsFeed.TECHNICAL_REFERENCE)
        self.assertIs(a.fetch_scope, VcbsFetchScope.REFERENCE)
        self.assertFalse(a.eligible_for_actionable_signal)

    def test_corporate_actions_not_trusted_adjustment_manifest(self):
        a = vcbs_capability(VcbsFeed.CORPORATE_ACTION_REFERENCE)
        self.assertFalse(a.provider_revision_verified)

    def test_refuse_fake_rights(self):
        a = vcbs_capability(VcbsFeed.DAILY_HISTORY)
        with self.assertRaises(ValueError):
            replace(a, authorized_for_retention=True)
        with self.assertRaises(ValueError):
            replace(a, eligible_for_actionable_signal=True)
        with self.assertRaises(ValueError):
            replace(a, full_minute_ohlcv=True)

    def test_unknown_endpoint_no_fallback(self):
        with self.assertRaises(TypeError):
            vcbs_capability("vcbs_get_history.D")

    def test_raw_d1_reference_synthetic(self):
        x = inspect_vcbs_raw_daily_row(row(), symbol="SYNX", retrieved_at_utc=STAMP)
        self.assertEqual((x.provider,x.price_basis,x.close_vnd,x.volume_shares),
                         ("VCBS", "RAW", Decimal(105), 900))
        self.assertFalse(x.rights_verified or x.actionable or x.indicators_allowed)
        self.assertFalse(x.lifecycle_closed_verified)

    def test_nontrading_provisional_retains_provisional_flag(self):
        r=row(); r["provisional"]=True
        x=inspect_vcbs_raw_daily_row(r,symbol="SYNX",retrieved_at_utc=STAMP)
        self.assertTrue(x.provisional)
        self.assertFalse(x.lifecycle_closed_verified)

    def test_adjusted_close_never_mixes_with_raw_ohlc(self):
        for kind in ("adjusted", "unknown", None):
            with self.subTest(kind=kind):
                r=row(); r["priceBasis"]=kind
                with self.assertRaises(ValueError):
                    inspect_vcbs_raw_daily_row(r,symbol="SYNX",retrieved_at_utc=STAMP)
        r=row(); r["price"]=101
        with self.assertRaises(ValueError):
            inspect_vcbs_raw_daily_row(r,symbol="SYNX",retrieved_at_utc=STAMP)

    def test_quote_unit_thousands_cannot_pass_as_vnd(self):
        r=row();r["price_unit"]="VND/1000"
        with self.assertRaises(ValueError):
            inspect_vcbs_raw_daily_row(r,symbol="SYNX",retrieved_at_utc=STAMP)

    def test_volume_scope_cannot_silently_mix_put_through(self):
        r=row();r["volumeScope"]="total"
        with self.assertRaises(ValueError):
            inspect_vcbs_raw_daily_row(r,symbol="SYNX",retrieved_at_utc=STAMP)

    def test_no_missing_volume_substituted_with_zero(self):
        r=row();del r["volume"]
        with self.assertRaises(ValueError):
            inspect_vcbs_raw_daily_row(r,symbol="SYNX",retrieved_at_utc=STAMP)

    def test_invalid_number_rejected(self):
        for bad in (-1, "NaN", "Infinity", "not-a-price", None, True):
            with self.subTest(bad=bad):
                r=row();r["closePrice"]=bad
                with self.assertRaises(ValueError):
                    inspect_vcbs_raw_daily_row(r,symbol="SYNX",retrieved_at_utc=STAMP)

    def test_low_high_invariant(self):
        r=row();r["lowPrice"]=106
        with self.assertRaises(ValueError):
            inspect_vcbs_raw_daily_row(r,symbol="SYNX",retrieved_at_utc=STAMP)

    def test_date_format_not_guessed(self):
        r=row();r["tradingDate"]="06/11/2026"
        with self.assertRaises(ValueError):
            inspect_vcbs_raw_daily_row(r,symbol="SYNX",retrieved_at_utc=STAMP)

    def test_missing_price_basis_fails(self):
        r=row();r.pop("priceBasis")
        with self.assertRaises(ValueError):
            inspect_vcbs_raw_daily_row(r,symbol="SYNX",retrieved_at_utc=STAMP)

    def test_reference_cannot_self_approve(self):
        x=inspect_vcbs_raw_daily_row(row(),symbol="SYNX",retrieved_at_utc=STAMP)
        for flag in ("quality_verified", "lifecycle_closed_verified", "rights_verified",
                     "retention_allowed", "indicators_allowed", "backtest_allowed", "actionable"):
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                replace(x, **{flag: True})

    def test_symbol_validation(self):
        for v in ("", "abc", " S", "A/B"):
            with self.subTest(v=v), self.assertRaises(ValueError):
                inspect_vcbs_raw_daily_row(row(),symbol=v,retrieved_at_utc=STAMP)

    def test_clock_requires_utc(self):
        with self.assertRaises(ValueError):
            inspect_vcbs_raw_daily_row(row(),symbol="SYNX",retrieved_at_utc=datetime(2026,11,7))

    def test_wrong_provider_rejected(self):
        x=inspect_vcbs_raw_daily_row(row(),symbol="SYNX",retrieved_at_utc=STAMP)
        with self.assertRaises(ValueError):
            replace(x,provider="SSI")

    def test_unknown_or_invalid_provisional_status_fails(self):
        r=row();r["provisional"]="false"
        with self.assertRaises(ValueError):
            inspect_vcbs_raw_daily_row(r,symbol="SYNX",retrieved_at_utc=STAMP)


if __name__=="__main__": unittest.main()
