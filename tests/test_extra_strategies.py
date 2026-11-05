import pytest

from backtester.datafeed import Bar
from backtester.extra_strategies import (
    AtrTrailingBreakoutStrategy,
    CciStrategy,
    EmaCrossoverStrategy,
    IchimokuCloudStrategy,
    KeltnerChannelStrategy,
    MacdStrategy,
    RateOfChangeStrategy,
    StochasticOscillatorStrategy,
    VwapMeanReversionStrategy,
    WilliamsRStrategy,
)

STRATEGY_FACTORIES = [
    lambda: EmaCrossoverStrategy(fast_period=2, slow_period=4, quantity=3),
    lambda: MacdStrategy(fast_period=2, slow_period=4, signal_period=2, quantity=3),
    lambda: RateOfChangeStrategy(period=3, quantity=3),
    lambda: StochasticOscillatorStrategy(
        period=4,
        oversold=30,
        overbought=70,
        quantity=3,
    ),
    lambda: WilliamsRStrategy(period=4, oversold=-70, overbought=-30, quantity=3),
    lambda: CciStrategy(period=4, entry_level=-50, exit_level=50, quantity=3),
    lambda: KeltnerChannelStrategy(
        period=3,
        atr_period=3,
        multiplier=0.5,
        quantity=3,
    ),
    lambda: AtrTrailingBreakoutStrategy(
        entry_period=3,
        atr_period=3,
        atr_multiplier=1,
        quantity=3,
    ),
    lambda: IchimokuCloudStrategy(
        conversion_period=2,
        base_period=3,
        span_b_period=4,
        displacement=2,
        quantity=3,
    ),
    lambda: VwapMeanReversionStrategy(period=4, num_std=0.5, quantity=3),
]


def _bars(closes, symbol="TEST", volume=100):
    return [
        Bar(
            timestamp=index,
            symbol=symbol,
            open=close,
            high=close + 1,
            low=close - 1,
            close=close,
            volume=volume,
        )
        for index, close in enumerate(closes)
    ]


def _accept(strategy, order, order_id):
    if order is not None and hasattr(strategy, "on_order_update"):
        event = {
            "order_id": order_id,
            "symbol": order["symbol"],
            "action": order["action"],
        }
        strategy.on_order_update({**event, "status": "pending"})
        strategy.on_order_update({**event, "status": "filled"})
    return order


def test_each_strategy_generates_long_entry_and_exit():
    closes = [
        10,
        9,
        8,
        7,
        8,
        9,
        11,
        13,
        15,
        14,
        12,
        10,
        8,
        7,
        9,
        12,
        15,
        18,
        16,
        13,
        10,
        8,
        9,
        12,
        16,
        20,
        18,
        14,
        10,
        7,
        8,
        11,
        15,
        20,
    ]
    bars = _bars(closes)
    for factory in STRATEGY_FACTORIES:
        strategy = factory()
        orders = []
        for index, bar in enumerate(bars):
            order = strategy.on_bar(bar, bars[: index + 1], portfolio=None)
            orders.append(order)
            _accept(strategy, order, index)
        emitted = [order for order in orders if order]
        assert [order["action"] for order in emitted[:2]] == ["buy", "sell"]
        assert emitted[0]["quantity"] == 3
        assert emitted[1]["quantity"] == -3


def test_additional_strategy_restores_position_after_rejected_exit():
    strategy = EmaCrossoverStrategy(fast_period=2, slow_period=4)
    strategy.in_position.add("TEST")

    strategy.on_order_update(
        {"order_id": 1, "status": "pending", "action": "sell", "symbol": "TEST"}
    )
    assert strategy.in_position == set()
    strategy.on_order_update(
        {
            "order_id": 1,
            "status": "rejected",
            "action": "sell",
            "symbol": "TEST",
            "reason": "portfolio_rejected",
        }
    )

    assert strategy.in_position == {"TEST"}


def test_flat_prices_do_not_generate_orders():
    bars = _bars([100] * 100)
    for factory in STRATEGY_FACTORIES:
        strategy = factory()
        assert all(
            strategy.on_bar(bar, bars[: index + 1], portfolio=None) is None
            for index, bar in enumerate(bars)
        )


@pytest.mark.parametrize(
    "factory",
    [
        lambda: EmaCrossoverStrategy(fast_period=4, slow_period=4),
        lambda: MacdStrategy(fast_period=26, slow_period=12),
        lambda: RateOfChangeStrategy(period=0),
        lambda: StochasticOscillatorStrategy(oversold=80, overbought=20),
        lambda: WilliamsRStrategy(oversold=-20, overbought=-80),
        lambda: CciStrategy(entry_level=100, exit_level=-100),
        lambda: KeltnerChannelStrategy(multiplier=0),
        lambda: AtrTrailingBreakoutStrategy(atr_multiplier=0),
        lambda: IchimokuCloudStrategy(
            conversion_period=26,
            base_period=9,
            span_b_period=52,
        ),
        lambda: VwapMeanReversionStrategy(period=1),
    ],
)
def test_invalid_parameters_are_rejected(factory):
    with pytest.raises((TypeError, ValueError)):
        factory()


def test_strategies_keep_position_state_per_symbol():
    strategy = EmaCrossoverStrategy(fast_period=2, slow_period=4, quantity=1)
    bars_a = _bars([10, 9, 8, 7, 8, 9], symbol="A")
    orders = [
        strategy.on_bar(bar, bars_a[: index + 1], portfolio=None)
        for index, bar in enumerate(bars_a)
    ]
    assert orders[-1]["action"] == "buy"
    _accept(strategy, orders[-1], 10)
    assert strategy.on_bar(bars_a[-1], bars_a, portfolio=None) is None
    bars_b = _bars([10, 9, 8, 7, 8, 9], symbol="B")
    assert strategy.on_bar(bars_b[-1], bars_b, portfolio=None)["action"] == "buy"


def test_vwap_skips_window_with_no_traded_volume():
    strategy = VwapMeanReversionStrategy(period=2)
    bars = _bars([10, 9, 8, 7], volume=0)
    assert all(
        strategy.on_bar(bar, bars[: index + 1], portfolio=None) is None
        for index, bar in enumerate(bars)
    )


def test_atr_breakout_waits_for_atr_history_before_trailing_exit():
    strategy = AtrTrailingBreakoutStrategy(
        entry_period=2,
        atr_period=5,
        atr_multiplier=1,
        quantity=1,
    )
    bars = _bars([10, 10, 11, 13, 16])
    assert strategy.on_bar(bars[2], bars[:3], None) is None
    entry = strategy.on_bar(bars[3], bars[:4], None)
    assert entry["action"] == "buy"
    _accept(strategy, entry, 1)
    assert strategy.on_bar(bars[4], bars, None) is None
