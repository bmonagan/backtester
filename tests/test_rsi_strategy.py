import pytest

from backtester.datafeed import Bar
from backtester.strategy import RsiMomentumStrategy


def _bars(closes, symbol="AAPL"):
    return [
        Bar(timestamp=i, symbol=symbol, open=c, high=c, low=c, close=c, volume=1)
        for i, c in enumerate(closes)
    ]


def test_rejects_bad_period():
    with pytest.raises(TypeError):
        RsiMomentumStrategy(period=True)
    with pytest.raises(TypeError):
        RsiMomentumStrategy(period=2.5)
    with pytest.raises(ValueError):
        RsiMomentumStrategy(period=0)


def test_rejects_bad_thresholds():
    with pytest.raises(ValueError):
        RsiMomentumStrategy(oversold=70, overbought=30)
    with pytest.raises(ValueError):
        RsiMomentumStrategy(oversold=30, overbought=30)
    with pytest.raises(ValueError):
        RsiMomentumStrategy(oversold=-5, overbought=70)
    with pytest.raises(ValueError):
        RsiMomentumStrategy(oversold=30, overbought=150)
    with pytest.raises(TypeError):
        RsiMomentumStrategy(oversold="30")


def test_rejects_bad_quantity():
    with pytest.raises(ValueError):
        RsiMomentumStrategy(quantity=0)
    with pytest.raises(TypeError):
        RsiMomentumStrategy(quantity="100")


def test_needs_period_plus_one_bars():
    s = RsiMomentumStrategy(period=3)
    bars = _bars([10, 9, 8])
    assert s.on_bar(bar=bars[-1], history=bars, portfolio=None) is None


def test_first_evaluation_seeds_state():
    s = RsiMomentumStrategy(period=2)
    bars = _bars([10, 9, 8])
    assert s.on_bar(bar=bars[-1], history=bars, portfolio=None) is None
    assert "AAPL" in s._state
    assert s._state["AAPL"]["prev_rsi"] == pytest.approx(0.0)


def test_oversold_cross_emits_single_buy():
    s = RsiMomentumStrategy(period=2, oversold=30, overbought=70, quantity=10)
    closes = [10, 9, 8, 7, 8, 9, 10, 10, 10]
    bars = _bars(closes)
    orders = []
    for i in range(len(bars)):
        o = s.on_bar(bar=bars[i], history=bars[: i + 1], portfolio=None)
        if o:
            orders.append((i, o))
    buys = [o for _, o in orders if o["action"] == "buy"]
    assert len(buys) == 1
    assert buys[0]["quantity"] == 10


def test_overbought_cross_emits_single_sell():
    s = RsiMomentumStrategy(period=2, oversold=30, overbought=70, quantity=10)
    closes = [1, 2, 3, 4, 3, 2, 1, 1, 1]
    bars = _bars(closes)
    orders = []
    for i in range(len(bars)):
        o = s.on_bar(bar=bars[i], history=bars[: i + 1], portfolio=None)
        if o:
            orders.append((i, o))
    sells = [o for _, o in orders if o["action"] == "sell"]
    assert len(sells) == 1
    assert sells[0]["quantity"] == -10


def test_flat_market_no_signal():
    s = RsiMomentumStrategy(period=2)
    bars = _bars([5, 5, 5, 5, 5, 5])
    for i in range(len(bars)):
        assert s.on_bar(bar=bars[i], history=bars[: i + 1], portfolio=None) is None
