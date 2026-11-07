"""GĐ4/C4B: no-lookahead, Vietnam cash equity reference economics only."""
import unittest
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from decimal import Decimal as D
from swing_trading.vn_backtest_execution_fixture import (
    VNSyntheticFill,VNSyntheticRules,VNAction,VNBarVerdict,
    calculate_fixture_vn_trade,inspect_fixture_vn_long_exit_bar,
    require_vn_backtest_release,
)

T=datetime(2026,11,5,3,tzinfo=timezone.utc)
RULES=VNSyntheticRules("HOSE",100,D("0.1"),D("8.0"),D("20.0"),
                       D("0.001"),D("0.001"),D("0.001"))
ENTRY=VNSyntheticFill("FAKE001","HOSE",VNAction.BUY,100,D("10.0"),
                       T,T+timedelta(seconds=2),1)
EXIT=VNSyntheticFill("FAKE001","HOSE",VNAction.EXIT_LONG_SELL,100,D("12.0"),
                      T+timedelta(days=4),T+timedelta(days=4,seconds=2),4)
ASOF=T+timedelta(days=5)

class VNFixtureExecutionTests(unittest.TestCase):
    def evaluate(self,entry=ENTRY,exit=EXIT,rules=RULES,release=3,asof=ASOF):
        return calculate_fixture_vn_trade(entry,exit,rules,
                 exit_allowed_from_session=release,as_of_utc=asof)

    def test_fees_and_sell_tax_net_pnl(self):
        r=self.evaluate()
        self.assertEqual(r.gross_pnl,D("200.0"))
        self.assertEqual(r.buy_cost,D("1.0000"))
        self.assertEqual(r.sell_cost,D("2.4000"))
        self.assertEqual(r.net_pnl,D("196.6000"))
        self.assertEqual(r.net_return_on_entry,D("196.6000")/D("1001.0000"))
        self.assertFalse(r.externally_verified_fill)
        self.assertFalse(r.validated_backtest)
        self.assertFalse(r.live_action_eligible)

    def test_zero_cost_fixture(self):
        rates=replace(RULES,buy_fee_rate=D("0"),sell_fee_rate=D("0"),sell_tax_rate=D("0"))
        self.assertEqual(self.evaluate(rules=rates).net_pnl,D("200.0"))

    def test_same_session_unsettled_blocked(self):
        with self.assertRaises(ValueError):
            self.evaluate(exit=replace(EXIT,session_index=2),release=3)

    def test_manually_verified_session_release_supported(self):
        with self.assertRaises(ValueError):
            self.evaluate(release=5)
        self.assertEqual(self.evaluate(release=4).gross_pnl,D("200.0"))

    def test_short_not_supported(self):
        with self.assertRaises(ValueError):
            self.evaluate(entry=replace(ENTRY,action=VNAction.EXIT_LONG_SELL))

    def test_wrong_exit_intent(self):
        with self.assertRaises(ValueError):
            self.evaluate(exit=replace(EXIT,action=VNAction.BUY))

    def test_symbol_mismatch_blocked(self):
        with self.assertRaises(ValueError):
            self.evaluate(exit=replace(EXIT,symbol="FAKE002"))

    def test_venue_mismatch_blocked(self):
        with self.assertRaises(ValueError):
            self.evaluate(exit=replace(EXIT,venue="HNX"))

    def test_oversell_or_share_mismatch_blocked(self):
        with self.assertRaises(ValueError):
            self.evaluate(exit=replace(EXIT,shares=200))

    def test_lot_violation_blocked(self):
        with self.assertRaises(ValueError):
            self.evaluate(entry=replace(ENTRY,shares=105),
                          exit=replace(EXIT,shares=105))

    def test_tick_violation_blocked(self):
        with self.assertRaises(ValueError):
            self.evaluate(entry=replace(ENTRY,price=D("10.05")))

    def test_band_violation_blocked(self):
        with self.assertRaises(ValueError):
            self.evaluate(exit=replace(EXIT,price=D("21")))

    def test_future_known_fill_blocked(self):
        with self.assertRaises(ValueError):
            self.evaluate(asof=T+timedelta(days=2))

    def test_fill_cannot_be_known_before_event(self):
        with self.assertRaises(ValueError):
            replace(ENTRY,first_known_utc=T-timedelta(seconds=1))

    def test_future_sale_cannot_precede_purchase(self):
        with self.assertRaises(ValueError):
            self.evaluate(exit=replace(EXIT,exchange_event_utc=T,
                              first_known_utc=T+timedelta(seconds=2)))

    def test_real_receipt_or_exchange_rules_never_certified(self):
        with self.assertRaises(PermissionError):
            replace(ENTRY,synthetic_receipt=False)
        with self.assertRaises(PermissionError):
            replace(RULES,synthetic_only=False)

    def test_negative_tax_rate_blocked(self):
        with self.assertRaises(ValueError):
            replace(RULES,sell_tax_rate=D("-0.01"))

    def test_unknown_t_plus_is_not_automatic(self):
        with self.assertRaises(TypeError):
            self.evaluate(release=None)

    def test_ambiguous_same_bar_touch(self):
        self.assertEqual(self.inspect(D("9"),D("11")),
                         VNBarVerdict.AMBIGUOUS_BOTH)

    def inspect(self,low,high,known=None):
        return inspect_fixture_vn_long_exit_bar(entry=D("10"),stop=D("9"),
               target=D("11"),low=low,high=high,bar_closed_utc=T,
               bar_known_utc=known or T+timedelta(seconds=2),decision_utc=T+timedelta(hours=1))

    def test_only_stop_touch(self):
        self.assertEqual(self.inspect(D("8.9"),D("10.5")),VNBarVerdict.STOP_ONLY)

    def test_only_target_touch(self):
        self.assertEqual(self.inspect(D("9.5"),D("11.1")),VNBarVerdict.TARGET_ONLY)

    def test_neither_touch(self):
        self.assertEqual(self.inspect(D("9.5"),D("10.5")),VNBarVerdict.NO_LEVEL_TOUCH)

    def test_bar_first_known_after_decision_blocked(self):
        with self.assertRaises(ValueError):
            self.inspect(D("9"),D("11"),known=T+timedelta(hours=2))

    def test_invalid_stop_target_levels_blocked(self):
        with self.assertRaises(ValueError):
            inspect_fixture_vn_long_exit_bar(entry=D("10"),stop=D("11"),
                 target=D("9"),low=D("8"),high=D("12"),bar_closed_utc=T,
                 bar_known_utc=T,decision_utc=T)

    def test_authorization_always_denied(self):
        with self.assertRaises(PermissionError):
            require_vn_backtest_release()

if __name__=="__main__":
    unittest.main()
