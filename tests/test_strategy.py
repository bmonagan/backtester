import pytest

from backtester.strategy import SmaCrossoverStrategy
from backtester.datafeed import Bar


def _bars(closes, symbol="AAPL"):
    return [
        Bar(timestamp=i, symbol=symbol, open=c, high=c, low=c, close=c, volume=1)
        for i, c in enumerate(closes)
    ]


def test_rejects_non_int_periods():
    with pytest.raises(TypeError):
        SmaCrossoverStrategy(fast_period=10.5)
    with pytest.raises(TypeError):
        SmaCrossoverStrategy(slow_period="30")


def test_rejects_bool_periods():
    with pytest.raises(TypeError):
        SmaCrossoverStrategy(fast_period=True)
    with pytest.raises(TypeError):
        SmaCrossoverStrategy(slow_period=False)


def test_rejects_non_positive_periods():
    with pytest.raises(ValueError):
        SmaCrossoverStrategy(fast_period=0, slow_period=30)
    with pytest.raises(ValueError):
        SmaCrossoverStrategy(fast_period=10, slow_period=-1)


def test_rejects_fast_not_less_than_slow():
    with pytest.raises(ValueError):
        SmaCrossoverStrategy(fast_period=30, slow_period=30)
    with pytest.raises(ValueError):
        SmaCrossoverStrategy(fast_period=40, slow_period=30)


def test_returns_none_until_slow_period_met():
    strat = SmaCrossoverStrategy(fast_period=2, slow_period=4)
    bars = _bars([1, 2, 3])
    for i in range(3):
        assert strat.on_bar(bar=bars[i], history=bars[: i + 1], portfolio=None) is None


def test_first_evaluation_seeds_state():
    strat = SmaCrossoverStrategy(fast_period=2, slow_period=3)
    bars = _bars([1, 2, 3])
    assert strat.on_bar(bar=bars[2], history=bars, portfolio=None) is None
    assert strat.last_fast == pytest.approx((2 + 3) / 2)
    assert strat.last_slow == pytest.approx((1 + 2 + 3) / 3)


def test_golden_cross_emits_buy():
    strat = SmaCrossoverStrategy(fast_period=2, slow_period=3, quantity=100)
    strat.last_fast = 1.0
    strat.last_slow = 2.0
    bars = _bars([1, 1, 10])
    order = strat.on_bar(bar=bars[-1], history=bars, portfolio=None)
    assert order is not None
    assert order["symbol"] == "AAPL"
    assert order["action"] == "buy"
    assert order["quantity"] == 100


def test_death_cross_emits_sell():
    strat = SmaCrossoverStrategy(fast_period=2, slow_period=3, quantity=100)
    strat.last_fast = 5.0
    strat.last_slow = 4.0
    bars = _bars([10, 10, 1])
    order = strat.on_bar(bar=bars[-1], history=bars, portfolio=None)
    assert order is not None
    assert order["symbol"] == "AAPL"
    assert order["action"] == "sell"
    assert order["quantity"] == -100


def test_no_cross_returns_none():
    strat = SmaCrossoverStrategy(fast_period=2, slow_period=3)
    strat.last_fast = 5.0
    strat.last_slow = 4.0
    bars = _bars([1, 2, 10])
    assert strat.on_bar(bar=bars[-1], history=bars, portfolio=None) is None
