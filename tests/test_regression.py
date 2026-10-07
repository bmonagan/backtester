"""Regression tests for bugs found during project audit (step 2)."""

import pytest

from datafeed import Bar
from engine import BacktestEngine
from portfolio import Portfolio
from strategy import SmaCrossoverStrategy


def _bars(closes, symbol="AAPL"):
    return [
        Bar(timestamp=i, symbol=symbol, open=c, high=c, low=c, close=c, volume=1)
        for i, c in enumerate(closes)
    ]


def test_bar_symbol_annotation_is_str():
    assert Bar.__annotations__["symbol"] is str
    b = Bar(timestamp=0, symbol="AAPL", open=1, high=1, low=1, close=1, volume=1)
    assert b.symbol == "AAPL"


def test_current_equity_includes_cash():
    p = Portfolio(starting_cash=1000.0)
    p.execute_order(timestamp="t0", symbol="AAPL", quantity=10, fill_price=5.0)
    # cash 950 + holdings 10*6=60 -> 1010
    assert p.current_equity({"AAPL": 6.0}) == pytest.approx(1010.0)


def test_current_equity_no_positions_returns_cash():
    p = Portfolio(starting_cash=500.0)
    assert p.current_equity({}) == pytest.approx(500.0)


def test_current_equity_missing_price_raises():
    p = Portfolio(starting_cash=1000.0)
    p.execute_order(timestamp="t0", symbol="AAPL", quantity=10, fill_price=5.0)
    with pytest.raises(KeyError):
        p.current_equity({"MSFT": 1.0})


def test_equity_curve_populated():
    p = Portfolio(starting_cash=1000.0)
    p.mark_to_market("t1", {})
    assert len(p.equity_curve) == 1
    assert p.equity_curve[0][1] == pytest.approx(1000.0)


def test_strategy_updates_state_after_cross():
    # down then up: should emit exactly one buy, not one per bar
    strat = SmaCrossoverStrategy(fast_period=2, slow_period=3, quantity=10)
    closes = [10, 9, 8, 7, 8, 9, 10, 10, 10]
    bars = _bars(closes)
    orders = []
    for i in range(len(bars)):
        o = strat.on_bar(bar=bars[i], history=bars[: i + 1], portfolio=None)
        if o:
            orders.append((i, o))
    # exactly one golden-cross buy at index 5
    assert len(orders) == 1
    assert orders[0][0] == 5
    assert orders[0][1]["action"] == "buy"


def test_strategy_death_cross_fires_once():
    strat = SmaCrossoverStrategy(fast_period=2, slow_period=3, quantity=10)
    # up then down: seed bullish, then one death cross
    closes = [1, 2, 3, 10, 3, 2, 1, 1, 1]
    bars = _bars(closes)
    orders = []
    for i in range(len(bars)):
        o = strat.on_bar(bar=bars[i], history=bars[: i + 1], portfolio=None)
        if o:
            orders.append((i, o))
    sells = [o for _, o in orders if o["action"] == "sell"]
    assert len(sells) == 1
    assert sells[0]["quantity"] == -10


def test_engine_insufficient_funds_drops_gracefully():
    bars = [
        Bar(timestamp=i, symbol="AAPL", open=100.0, high=100.0, low=100.0, close=100.0, volume=1)
        for i in range(3)
    ]

    class BuyHuge:
        def on_bar(self, bar, history, portfolio):
            return {"symbol": "AAPL", "action": "buy", "quantity": 10**9}

    eng = BacktestEngine(feed=bars, strategy=BuyHuge(), starting_cash=10.0)
    pf = eng.run()
    # order cannot fill, portfolio stays flat, no crash
    assert pf.positions == {}
    assert pf.cash == pytest.approx(10.0)


def test_engine_multisymbol_keeps_pending_for_other_symbol():
    bars = [
        Bar(timestamp=0, symbol="AAPL", open=10, high=10, low=10, close=10, volume=1),
        Bar(timestamp=1, symbol="MSFT", open=20, high=20, low=20, close=20, volume=1),
        Bar(timestamp=2, symbol="AAPL", open=11, high=11, low=11, close=11, volume=1),
        Bar(timestamp=3, symbol="MSFT", open=21, high=21, low=21, close=21, volume=1),
    ]

    class BuyOnceAAPL:
        def __init__(self):
            self.fired = False

        def on_bar(self, bar, history, portfolio):
            if bar.symbol == "AAPL" and not self.fired:
                self.fired = True
                return {"symbol": "AAPL", "action": "buy", "quantity": 5}
            return None

    eng = BacktestEngine(feed=bars, strategy=BuyOnceAAPL(), starting_cash=10000.0)
    pf = eng.run()
    assert "AAPL" in pf.positions
    assert pf.positions["AAPL"].quantity == 5
