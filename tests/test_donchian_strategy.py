import pytest

from backtester.datafeed import Bar
from backtester.strategy import DonchianBreakoutStrategy


def _bars(closes, symbol="AAPL"):
    return [
        Bar(timestamp=i, symbol=symbol, open=c, high=c, low=c, close=c, volume=1)
        for i, c in enumerate(closes)
    ]


def test_rejects_bad_params():
    with pytest.raises(TypeError):
        DonchianBreakoutStrategy(entry_period=20.5)
    with pytest.raises(ValueError):
        DonchianBreakoutStrategy(entry_period=0)
    with pytest.raises(ValueError):
        DonchianBreakoutStrategy(entry_period=10, exit_period=10)
    with pytest.raises(ValueError):
        DonchianBreakoutStrategy(entry_period=10, exit_period=20)
    with pytest.raises(ValueError):
        DonchianBreakoutStrategy(quantity=0)


def test_flat_series_no_signal():
    s = DonchianBreakoutStrategy(entry_period=5, exit_period=3)
    bars = _bars([10] * 12)
    for i in range(len(bars)):
        assert s.on_bar(bar=bars[i], history=bars[: i + 1], portfolio=None) is None


def test_staircase_breakout_emits_single_buy():
    s = DonchianBreakoutStrategy(entry_period=3, exit_period=2, quantity=4)
    closes = [10, 10, 10, 11, 12, 13, 13, 13]
    bars = _bars(closes)
    orders = []
    for i in range(len(bars)):
        o = s.on_bar(bar=bars[i], history=bars[: i + 1], portfolio=None)
        if o:
            orders.append((i, o))
    buys = [o for _, o in orders if o["action"] == "buy"]
    assert len(buys) == 1
    assert buys[0]["quantity"] == 4


def test_breakdown_after_entry_exits():
    s = DonchianBreakoutStrategy(entry_period=3, exit_period=2, quantity=4)
    closes = [10, 10, 10, 11, 12, 13, 5, 5]
    bars = _bars(closes)
    orders = []
    for i in range(len(bars)):
        o = s.on_bar(bar=bars[i], history=bars[: i + 1], portfolio=None)
        if o:
            orders.append((i, o))
    assert [o["action"] for _, o in orders] == ["buy", "sell"]
    assert orders[-1][1]["quantity"] == -4
