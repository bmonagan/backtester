import pytest

from backtester.datafeed import Bar
from backtester.engine import BacktestEngine
from backtester.strategy import BuyAndHoldStrategy, OrderTypeOverride


def _bar(ts, o, h, lo, c, symbol="AAPL"):
    return Bar(timestamp=ts, symbol=symbol, open=o, high=h, low=lo, close=c, volume=1)


def _hold(symbol="AAPL"):
    return [
        Bar(timestamp=i, symbol=symbol, open=10, high=10, low=10, close=10, volume=1)
        for i in range(2)
    ]


def test_rejects_bad_order_type():
    with pytest.raises(ValueError):
        OrderTypeOverride(BuyAndHoldStrategy(), "iceberg")


def test_limit_requires_numeric_price():
    with pytest.raises(TypeError):
        OrderTypeOverride(BuyAndHoldStrategy(), "limit")
    with pytest.raises(TypeError):
        OrderTypeOverride(BuyAndHoldStrategy(), "limit", "5")
    with pytest.raises(ValueError):
        OrderTypeOverride(BuyAndHoldStrategy(), "stop", 0)


def test_market_override_stamps_type_and_drops_price():
    s = OrderTypeOverride(BuyAndHoldStrategy(quantity=3), "market")
    bars = _hold()
    order = s.on_bar(bar=bars[0], history=bars[:1], portfolio=None)
    assert order is not None
    assert order["order_type"] == "market"
    assert "price" not in order
    assert order["quantity"] == 3


def test_limit_override_stamps_price():
    s = OrderTypeOverride(BuyAndHoldStrategy(quantity=3), "limit", 9.5)
    bars = _hold()
    order = s.on_bar(bar=bars[0], history=bars[:1], portfolio=None)
    assert order["order_type"] == "limit"
    assert order["price"] == 9.5


def test_override_returns_none_when_inner_none():
    class Quiet:
        def on_bar(self, bar, history, portfolio):
            return None

    s = OrderTypeOverride(Quiet(), "market")
    bars = _hold()
    assert s.on_bar(bar=bars[0], history=bars[:1], portfolio=None) is None


def test_limit_below_market_fills_via_engine():
    bars = [
        _bar(0, 100, 101, 99, 100),
        _bar(1, 100, 100, 90, 92),  # low 90 <= 95, fills at 95
    ]
    s = OrderTypeOverride(BuyAndHoldStrategy(quantity=10), "limit", 95.0)
    eng = BacktestEngine(feed=bars, strategy=s, starting_cash=10000.0)
    pf = eng.run()
    assert pf.positions["AAPL"].avg_price == pytest.approx(95.0)
    assert eng.n_fills == 1


def test_limit_above_market_never_fills():
    bars = [
        _bar(0, 100, 101, 99, 100),
        _bar(1, 100, 101, 99, 100),
    ]
    s = OrderTypeOverride(BuyAndHoldStrategy(quantity=10), "limit", 50.0)
    eng = BacktestEngine(feed=bars, strategy=s, starting_cash=10000.0)
    pf = eng.run()
    assert pf.positions == {}
    assert len(eng.pending_orders) == 1
