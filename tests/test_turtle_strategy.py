from backtester.datafeed import Bar
from backtester.strategy import DonchianBreakoutStrategy, TurtleTradingStrategy


def _bars(closes, symbol="AAPL"):
    return [
        Bar(timestamp=i, symbol=symbol, open=c, high=c, low=c, close=c, volume=1)
        for i, c in enumerate(closes)
    ]


def _run(strategy, bars):
    orders = []
    for index, bar in enumerate(bars):
        order = strategy.on_bar(bar, bars[:index + 1], portfolio=None)
        orders.append(order)
        if order:
            event = {
                "order_id": index,
                "symbol": order["symbol"],
                "action": order["action"],
            }
            strategy.on_order_update({**event, "status": "pending"})
            strategy.on_order_update({**event, "status": "filled"})
    return orders


def test_defaults_match_turtle_system_one_channels():
    strategy = TurtleTradingStrategy()
    assert strategy.entry_period == 20
    assert strategy.exit_period == 10


def test_turtle_uses_breakout_and_exit_signals():
    strategy = TurtleTradingStrategy(entry_period=3, exit_period=2, quantity=4)
    bars = _bars([10, 10, 10, 11, 12, 13, 5, 5])
    orders = _run(strategy, bars)
    assert [order["action"] for order in orders if order] == ["buy", "sell"]
    assert orders[3]["quantity"] == 4
    assert orders[6]["quantity"] == -4


def test_turtle_reuses_donchian_signals():
    closes = [10, 10, 10, 11, 12, 13, 5, 5]
    turtle_bars = _bars(closes)
    donchian_bars = _bars(closes)
    turtle = TurtleTradingStrategy(entry_period=3, exit_period=2, quantity=4)
    donchian = DonchianBreakoutStrategy(entry_period=3, exit_period=2, quantity=4)
    turtle_orders = _run(turtle, turtle_bars)
    donchian_orders = _run(donchian, donchian_bars)
    assert turtle_orders == donchian_orders
