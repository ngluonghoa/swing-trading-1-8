# GĐ4/C4B — Vietnam cash-equity execution-fixture safety reference

The user approved a higher common Backtest engineering standard while keeping **market-specific** fill/fees/settlement logic and source rights separate. This milestone adds `src/swing_trading/vn_backtest_execution_fixture.py` and `tests/test_vn_backtest_execution_fixture.py` for **fabricated** quote/fill inputs only, no historical P&L claim or actionable signal.

What is executable and testable:
- Explicit cash equity BUY then EXIT_LONG_SELL only; same symbol/venue/quantity, whole lot, synthetic venue price bands and tick, user-supplied test commission/sell tax; computes *only a math result on independently injected fake fill receipts*. No borrow/short is inferred; cannot assert actual broker fill or exchange rules.
- An explicit settlement-release *session index* from a verified future calendar authority must be provided (fixture test sets it manually). No automatic claim about current Vietnamese T+, lot sizes, tax, price bands or actual fee tariff.
- Both receipts carry exchange event UTC and first-known UTC. Future-known receipts cannot enter as-of evaluation. Incoherent order, oversell, tick/band or unsettled exit blocks.
- Independent OHLC long stop/target checker distinguishes no touch, stop only, TP only, and **AMBIGUOUS_BOTH** where a bar crosses both levels but intrabar event order is unknown. None of these states proves a fill, profit, broker slippage or liquidity.
- Outputs always `fixture_only=true, externally_verified_fill=false, validated_backtest=false, live_action_eligible=false`. No credential, market history, vendor cache, order routing, UI or source rights modified.

Relation to Swing `BacktestHarness`: replay and temporal purge/embargo already exist as separate fail-closed references; the new fixture arithmetic is **NOT yet connected to executable zone detectors or a portfolio/order simulation loop**. Next work needs a versioned event-to-order adapter, independent fill observations, realistic signed fees/taxes/T+ and venue rules, cash/position lifecycle, corporate actions, max drawdown and OOS walk-forward using entitled history. Do not confuse reference checks with a published benchmark or strategy profitability.
