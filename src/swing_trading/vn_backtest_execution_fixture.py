"""GĐ4/C4B — synthetic-only VN equity execution and OHLC ambiguity reference.

This module is NOT a historical backtester, trade detector, settlement rules
authority, exchange tariff, broker fill receipt or real return estimate.
All prices/fees/lots/bands/settlement indices are explicitly supplied FABRICATED
fixtures. No provider entitlement, orders, live-trading permission or OOS score.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum


def _d(x: Decimal, *, allow_zero: bool = False) -> Decimal:
    if not isinstance(x, Decimal) or not x.is_finite() or (x < 0 if allow_zero else x <= 0):
        raise ValueError("Positive finite Decimal required" if not allow_zero else "Nonnegative finite Decimal required")
    return x


def _utc(x: datetime) -> None:
    if not isinstance(x,datetime) or x.tzinfo is None or x.utcoffset() != timedelta(0):
        raise ValueError("UTC aware timestamp required")


class VNAction(str,Enum):
    BUY="BUY"
    EXIT_LONG_SELL="EXIT_LONG_SELL"


class VNBarVerdict(str,Enum):
    NO_LEVEL_TOUCH="NO_LEVEL_TOUCH"
    STOP_ONLY="STOP_ONLY"
    TARGET_ONLY="TARGET_ONLY"
    AMBIGUOUS_BOTH="AMBIGUOUS_BOTH"


@dataclass(frozen=True)
class VNSyntheticRules:
    venue: str
    board_lot: int
    tick: Decimal
    lower_band: Decimal
    upper_band: Decimal
    buy_fee_rate: Decimal
    sell_fee_rate: Decimal
    sell_tax_rate: Decimal
    synthetic_only: bool=True

    def __post_init__(self):
        if self.venue not in {"HOSE","HNX","UPCOM"}:
            raise ValueError("Unsupported explicit fixture venue")
        if type(self.board_lot) is not int or self.board_lot < 1:
            raise ValueError("Explicit fixture board-lot required")
        for x in (self.tick,self.lower_band,self.upper_band):
            _d(x)
        if self.lower_band>self.upper_band:
            raise ValueError("Invalid synthetic price band")
        for rate in (self.buy_fee_rate,self.sell_fee_rate,self.sell_tax_rate):
            _d(rate,allow_zero=True)
            if rate>=1:
                raise ValueError("Unrealistic fee ratio for synthetic scenario")
        if self.synthetic_only is not True:
            raise PermissionError("No real exchange/broker parameters certified")


@dataclass(frozen=True)
class VNSyntheticFill:
    symbol: str
    venue: str
    action: VNAction
    shares: int
    price: Decimal
    exchange_event_utc: datetime
    first_known_utc: datetime
    session_index: int
    synthetic_receipt: bool=True

    def __post_init__(self):
        if not isinstance(self.symbol,str) or not self.symbol.strip():
            raise ValueError("Synthetic ticker required")
        if self.venue not in {"HOSE","HNX","UPCOM"}:
            raise ValueError("Venue ID required")
        if not isinstance(self.action,VNAction):
            raise TypeError("Explicit buy/sell intent")
        if type(self.shares) is not int or self.shares<=0:
            raise ValueError("Positive whole share quantity required")
        _d(self.price)
        _utc(self.exchange_event_utc)
        _utc(self.first_known_utc)
        if self.first_known_utc<self.exchange_event_utc:
            raise ValueError("Fill may not be known before event time")
        if type(self.session_index) is not int or self.session_index<0:
            raise ValueError("Externally provided synthetic session index required")
        if self.synthetic_receipt is not True:
            raise PermissionError("Never assert real fill verification from a fixture")


@dataclass(frozen=True)
class VNSyntheticTradeMetric:
    gross_pnl: Decimal
    buy_cost: Decimal
    sell_cost: Decimal
    net_pnl: Decimal
    cash_at_risk: Decimal
    net_return_on_entry: Decimal
    fixture_only: bool=True
    externally_verified_fill: bool=False
    validated_backtest: bool=False
    live_action_eligible: bool=False


def calculate_fixture_vn_trade(entry: VNSyntheticFill, exit: VNSyntheticFill,
                               rules: VNSyntheticRules, *,
                               exit_allowed_from_session: int,
                               as_of_utc: datetime) -> VNSyntheticTradeMetric:
    """Only value independently injected SYNTHETIC receipts; never infer fills from OHLC.

    Settlement eligibility is an externally specified session index, NOT an
    assumed Vietnamese T+ settlement rule or certified real exchange calendar.
    """
    _utc(as_of_utc)
    if not all((isinstance(entry,VNSyntheticFill),isinstance(exit,VNSyntheticFill),
                isinstance(rules,VNSyntheticRules))):
        raise TypeError("Typed independent synthetic receipts/rules required")
    if (entry.action is not VNAction.BUY or exit.action is not VNAction.EXIT_LONG_SELL
            or entry.symbol!=exit.symbol or entry.venue!=exit.venue or entry.venue!=rules.venue):
        raise ValueError("VN equity trade must be the same held cash equity")
    if entry.shares!=exit.shares or entry.shares % rules.board_lot:
        raise ValueError("No synthetic short/oversell or unapproved odd lot")
    if type(exit_allowed_from_session) is not int or exit_allowed_from_session<entry.session_index:
        raise ValueError("Externally provided settlement-release session required")
    if (exit.session_index<exit_allowed_from_session or
            exit.session_index<entry.session_index or
            exit.exchange_event_utc<=entry.exchange_event_utc):
        raise ValueError("Unsettled or reverse-time exit forbidden")
    if max(entry.first_known_utc,exit.first_known_utc)>as_of_utc:
        raise ValueError("Cannot score a future-known synthetic fill")
    for receipt in (entry,exit):
        if (not rules.lower_band<=receipt.price<=rules.upper_band
                or receipt.price%rules.tick!=0):
            raise ValueError("Tick / supplied synthetic price band disallows fill scenario")
    principal=entry.price*entry.shares
    proceeds=exit.price*exit.shares
    buy_cost=principal*rules.buy_fee_rate
    sell_cost=proceeds*(rules.sell_fee_rate+rules.sell_tax_rate)
    gross=proceeds-principal
    net=gross-buy_cost-sell_cost
    capital=principal+buy_cost
    return VNSyntheticTradeMetric(gross,buy_cost,sell_cost,net,capital,net/capital)


def inspect_fixture_vn_long_exit_bar(*, entry: Decimal, stop: Decimal,
                                     target: Decimal, low: Decimal, high: Decimal,
                                     bar_closed_utc: datetime,
                                     bar_known_utc: datetime,
                                     decision_utc: datetime) -> VNBarVerdict:
    """Signal reachability only. A high/low level touch is NOT a verified fill.

    Both stop and TP touched in one bar => AMBIGUOUS_BOTH, no assumed order.
    Gaps, queues, price limits, volume and broker execution remain unmodelled.
    """
    for x in (entry,stop,target,low,high):
        _d(x)
    if not stop<entry<target or low>high:
        raise ValueError("Invalid long stop/entry/target levels or bar range")
    for t in (bar_closed_utc,bar_known_utc,decision_utc):
        _utc(t)
    if bar_known_utc<bar_closed_utc or bar_known_utc>decision_utc:
        raise ValueError("Look-ahead or OPEN bar detected")
    hit_stop=low<=stop
    hit_target=high>=target
    if hit_stop and hit_target:
        return VNBarVerdict.AMBIGUOUS_BOTH
    if hit_stop:
        return VNBarVerdict.STOP_ONLY
    if hit_target:
        return VNBarVerdict.TARGET_ONLY
    return VNBarVerdict.NO_LEVEL_TOUCH


def require_vn_backtest_release(*_args:object,**_kwargs:object)->None:
    raise PermissionError("No approved VN calendar/broker fills, OOS run or trading release")
