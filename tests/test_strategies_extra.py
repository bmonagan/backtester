import pytest

from datafeed import Bar
from strategy import BuyAndHoldStrategy, SmaCrossoverStrategy


def _bars(closes, symbol="AAPL"):
    return [
        Bar(timestamp=i, symbol=symbol, open=c, high=c, low=c, close=c, volume=1)
        for i, c in enumerate(closes)
    ]


def test_buy_and_hold_fires_once():
    s = BuyAndHoldStrategy(quantity=5)
    bars = _bars([10, 11, 12])
    o0 = s.on_bar(bar=bars[0], history=bars[:1], portfolio=None)
    assert o0 is not None and o0["quantity"] == 5
    assert s.on_bar(bar=bars[1], history=bars[:2], portfolio=None) is None
    assert s.on_bar(bar=bars[2], history=bars[:3], portfolio=None) is None


def test_buy_and_hold_buys_each_symbol_once():
    s = BuyAndHoldStrategy(quantity=5)
    a = _bars([10, 11], symbol="AAPL")
    m = _bars([20, 21], symbol="MSFT")
    assert s.on_bar(bar=a[0], history=a[:1], portfolio=None) is not None
    assert s.on_bar(bar=m[0], history=m[:1], portfolio=None) is not None
    assert s.on_bar(bar=a[1], history=a, portfolio=None) is None


def test_quantity_validation():
    with pytest.raises(ValueError):
        SmaCrossoverStrategy(quantity=0)
    with pytest.raises(ValueError):
        SmaCrossoverStrategy(quantity=-5)
    with pytest.raises(TypeError):
        SmaCrossoverStrategy(quantity="100")
    with pytest.raises(ValueError):
        BuyAndHoldStrategy(quantity=0)
    with pytest.raises(TypeError):
        BuyAndHoldStrategy(quantity=None)
