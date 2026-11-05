import pytest

from backtester.datafeed import Bar
from backtester.engine import BacktestEngine
from backtester.instruments import ExecutionCostModel
from backtester.strategy import BuyAndHoldStrategy


def _bar(timestamp, open_price, high, low, close, volume=10.0, symbol="AAPL"):
    return Bar(
        timestamp=timestamp,
        symbol=symbol,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


class Scripted:
    def __init__(self, orders):
        self.orders = iter(orders)

    def on_bar(self, bar, history, portfolio):
        return next(self.orders, None)


def test_cost_free_execution_model_preserves_documented_market_fill():
    bars = [_bar(0, 100, 101, 99, 100), _bar(1, 102, 103, 101, 102)]
    strategy = Scripted([{"symbol": "AAPL", "action": "buy", "quantity": 2}, None])
    engine = BacktestEngine(
        bars,
        strategy=strategy,
        starting_cash=1000.0,
        execution_models={"AAPL": ExecutionCostModel()},
    )
    portfolio = engine.run()

    assert portfolio.positions["AAPL"].avg_price == pytest.approx(102.0)
    assert portfolio.cash == pytest.approx(796.0)
    assert engine.n_fills == 1
    assert portfolio.cost_totals == {
        "commission": 0.0,
        "spread": 0.0,
        "slippage": 0.0,
        "impact": 0.0,
    }


def test_participation_limit_splits_fill_and_attributes_modeled_costs():
    bars = [
        _bar(0, 100, 101, 99, 100),
        _bar(1, 100, 101, 99, 100),
        _bar(2, 100, 101, 99, 100),
    ]
    strategy = Scripted(
        [{"symbol": "AAPL", "action": "buy", "quantity": 10}, None, None]
    )
    model = ExecutionCostModel(
        half_spread_bps=2.0,
        slippage_bps=3.0,
        impact_bps_at_full_participation=20.0,
        max_participation_rate=0.5,
    )
    engine = BacktestEngine(
        bars,
        strategy=strategy,
        starting_cash=10_000.0,
        execution_models={"AAPL": model},
    )
    portfolio = engine.run()

    assert portfolio.positions["AAPL"].quantity == 10
    assert [event["status"] for event in engine.order_events] == [
        "pending",
        "partial_fill",
        "filled",
    ]
    assert [event["quantity"] for event in engine.order_events[1:]] == [5, 5]
    assert [trade["effective_price"] for trade in portfolio.trade_log] == pytest.approx(
        [100.15, 100.15]
    )
    assert portfolio.cash == pytest.approx(8_998.5)
    assert portfolio.cost_totals == pytest.approx(
        {"commission": 0.0, "spread": 0.2, "slippage": 0.3, "impact": 1.0}
    )


def test_adverse_scenario_applies_costs_to_stop_gap_open_fill():
    bars = [
        _bar(0, 100, 101, 99, 100),
        _bar(1, 110, 115, 109, 112),
    ]
    order = {
        "symbol": "AAPL",
        "action": "buy",
        "quantity": 1,
        "order_type": "stop",
        "price": 105,
    }
    strategy = Scripted([order, None])
    engine = BacktestEngine(
        bars,
        strategy=strategy,
        starting_cash=1000.0,
        execution_models={
            "AAPL": ExecutionCostModel(
                half_spread_bps=5.0,
                slippage_bps=10.0,
                scenario="adverse",
            )
        },
    )
    portfolio = engine.run()

    assert engine.order_events[-1]["fill_price"] == 110.0
    assert portfolio.positions["AAPL"].avg_price == pytest.approx(110.2475)
    assert portfolio.cost_totals["spread"] == pytest.approx(0.0825)
    assert portfolio.cost_totals["slippage"] == pytest.approx(0.165)


def test_unfilled_order_expires_after_configured_symbol_bars():
    bars = [
        _bar(0, 100, 101, 99, 100),
        _bar(1, 100, 101, 99, 100),
        _bar(2, 100, 101, 99, 100),
    ]
    order = {
        "symbol": "AAPL",
        "action": "buy",
        "quantity": 1,
        "order_type": "limit",
        "price": 50,
        "max_wait_bars": 2,
    }
    engine = BacktestEngine(
        bars,
        strategy=Scripted([order, None, None]),
        starting_cash=1000.0,
    )
    engine.run()

    assert [event["status"] for event in engine.order_events] == ["pending", "expired"]
    assert engine.order_events[-1]["reason"] == "max_wait_bars"
    assert engine.pending_orders == []


def test_partial_expiry_keeps_strategy_state_in_sync_with_actual_position():
    bars = [
        _bar(0, 100, 101, 99, 100),
        _bar(1, 100, 101, 99, 100),
        _bar(2, 100, 101, 99, 100),
    ]
    class ExpiringBuyAndHold(BuyAndHoldStrategy):
        def on_bar(self, bar, history, portfolio):
            if bar.symbol in self.bought:
                return None
            order = super().on_bar(bar, history, portfolio)
            return {**order, "max_wait_bars": 1}

    strategy = ExpiringBuyAndHold(quantity=10)
    engine = BacktestEngine(
        bars,
        strategy=strategy,
        starting_cash=10_000.0,
        execution_models={
            "AAPL": ExecutionCostModel(max_participation_rate=0.5)
        },
    )
    engine.run()

    assert [event["status"] for event in engine.order_events] == [
        "pending",
        "partial_fill",
        "expired",
    ]
    assert engine.portfolio.positions["AAPL"].quantity == 5
    assert strategy.bought == {"AAPL"}


@pytest.mark.parametrize("max_wait_bars", [0, -1, 1.5, True])
def test_invalid_order_expiration_is_rejected(max_wait_bars):
    bars = [_bar(0, 100, 101, 99, 100)]
    order = {
        "symbol": "AAPL",
        "action": "buy",
        "quantity": 1,
        "max_wait_bars": max_wait_bars,
    }
    engine = BacktestEngine(
        bars,
        strategy=Scripted([order]),
        starting_cash=1000.0,
    )
    engine.run()

    assert engine.n_rejected == 1
    assert engine.order_events[-1]["reason"] == "invalid_expiration"
