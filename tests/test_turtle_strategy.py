from backtester.datafeed import Bar
from backtester.strategy import DonchianBreakoutStrategy, TurtleTradingStrategy


def _bars(closes, symbol="AAPL"):
    return [
        Bar(timestamp=i, symbol=symbol, open=c, high=c, low=c, close=c, volume=1)
        for i, c in enumerate(closes)
    ]


def test_defaults_match_turtle_system_one_channels():
    strategy = TurtleTradingStrategy()
    assert strategy.entry_period == 20
    assert strategy.exit_period == 10


def test_turtle_uses_breakout_and_exit_signals():
    strategy = TurtleTradingStrategy(entry_period=3, exit_period=2, quantity=4)
    bars = _bars([10, 10, 10, 11, 12, 13, 5, 5])
    orders = [
        strategy.on_bar(bar, bars[:index + 1], portfolio=None)
        for index, bar in enumerate(bars)
    ]
    assert [order["action"] for order in orders if order] == ["buy", "sell"]
    assert orders[3]["quantity"] == 4
    assert orders[6]["quantity"] == -4


def test_turtle_reuses_donchian_signals():
    closes = [10, 10, 10, 11, 12, 13, 5, 5]
    turtle_bars = _bars(closes)
    donchian_bars = _bars(closes)
    turtle = TurtleTradingStrategy(entry_period=3, exit_period=2, quantity=4)
    donchian = DonchianBreakoutStrategy(entry_period=3, exit_period=2, quantity=4)
    turtle_orders = [
        turtle.on_bar(bar, turtle_bars[:index + 1], None)
        for index, bar in enumerate(turtle_bars)
    ]
    donchian_orders = [
        donchian.on_bar(bar, donchian_bars[:index + 1], None)
        for index, bar in enumerate(donchian_bars)
    ]
    assert turtle_orders == donchian_orders
