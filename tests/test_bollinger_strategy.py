import pytest

from backtester.datafeed import Bar
from backtester.strategy import BollingerMeanReversionStrategy


def _bars(closes, symbol="AAPL"):
    return [
        Bar(timestamp=i, symbol=symbol, open=c, high=c, low=c, close=c, volume=1)
        for i, c in enumerate(closes)
    ]


def test_rejects_bad_params():
    with pytest.raises(TypeError):
        BollingerMeanReversionStrategy(period=2.5)
    with pytest.raises(ValueError):
        BollingerMeanReversionStrategy(period=1)
    with pytest.raises(ValueError):
        BollingerMeanReversionStrategy(num_std=0)
    with pytest.raises(TypeError):
        BollingerMeanReversionStrategy(num_std="2")
    with pytest.raises(ValueError):
        BollingerMeanReversionStrategy(quantity=-1)


def test_flat_series_no_signal():
    s = BollingerMeanReversionStrategy(period=5)
    bars = _bars([10] * 12)
    for i in range(len(bars)):
        assert s.on_bar(bar=bars[i], history=bars[: i + 1], portfolio=None) is None


def test_dip_below_lower_emits_single_buy():
    s = BollingerMeanReversionStrategy(period=5, num_std=1.0, quantity=7)
    closes = [10, 10, 10, 10, 10, 4, 4, 4, 4, 4]
    bars = _bars(closes)
    orders = []
    for i in range(len(bars)):
        o = s.on_bar(bar=bars[i], history=bars[: i + 1], portfolio=None)
        if o:
            orders.append((i, o))
    buys = [o for _, o in orders if o["action"] == "buy"]
    assert len(buys) == 1
    assert buys[0]["quantity"] == 7


def test_rally_above_upper_exits_position():
    s = BollingerMeanReversionStrategy(period=5, num_std=1.0, quantity=7)
    closes = [10, 10, 10, 10, 10, 4, 4, 4, 4, 4, 20, 20]
    bars = _bars(closes)
    orders = []
    for i in range(len(bars)):
        o = s.on_bar(bar=bars[i], history=bars[: i + 1], portfolio=None)
        if o:
            orders.append((i, o))
    assert [o["action"] for _, o in orders] == ["buy", "sell"]
    assert orders[-1][1]["quantity"] == -7
