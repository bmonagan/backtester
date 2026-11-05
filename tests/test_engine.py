import pytest

from backtester.datafeed import Bar
from backtester.engine import BacktestEngine


def _bars(symbol="AAPL"):
    raw = [(10.0, 11.0), (11.0, 12.0), (12.0, 13.0), (13.0, 14.0)]
    return [
        Bar(timestamp=i, symbol=symbol, open=o, high=c, low=o, close=c, volume=1)
        for i, (o, c) in enumerate(raw)
    ]


class QuietStrategy:
    def __init__(self):
        self.calls = 0

    def on_bar(self, bar, history, portfolio):
        self.calls += 1
        return None


class BuyOnceStrategy:
    def __init__(self, quantity=10):
        self.quantity = quantity
        self.fired = False

    def on_bar(self, bar, history, portfolio):
        if not self.fired:
            self.fired = True
            return {"symbol": bar.symbol, "action": "buy", "quantity": self.quantity}
        return None


def test_init_starts_empty():
    eng = BacktestEngine(feed=[], strategy=QuietStrategy(), starting_cash=1000.0)
    assert eng.portfolio.cash == 1000.0
    assert eng.pending_orders == []
    assert eng.latest_prices == {}


def test_quiet_run_marks_every_bar():
    bars = _bars()
    strat = QuietStrategy()
    eng = BacktestEngine(feed=bars, strategy=strat, starting_cash=1000.0)
    portfolio = eng.run()
    assert strat.calls == len(bars)
    assert len(portfolio.history) == len(bars)
    assert portfolio.cash == 1000.0
    assert eng.pending_orders == []


def test_order_fills_at_next_bar_open():
    bars = _bars()
    eng = BacktestEngine(feed=bars, strategy=BuyOnceStrategy(quantity=10), starting_cash=10000.0)
    portfolio = eng.run()
    assert "AAPL" in portfolio.positions
    assert portfolio.positions["AAPL"].quantity == 10
    # fill happens at second bar's open (11.0)
    assert portfolio.cash == pytest.approx(10000.0 - 10 * 11.0)
    assert len(portfolio.trade_log) == 1


def test_history_tracks_symbol_prices():
    bars = _bars()
    eng = BacktestEngine(feed=bars, strategy=QuietStrategy(), starting_cash=1000.0)
    eng.run()
    assert eng.latest_prices["AAPL"] == bars[-1].close
    assert len(eng.history["AAPL"]) == len(bars)


def test_order_events_record_pending_then_filled():
    eng = BacktestEngine(
        feed=_bars(),
        strategy=BuyOnceStrategy(quantity=1),
        starting_cash=1000.0,
    )
    eng.run()

    assert [event["status"] for event in eng.order_events] == ["pending", "filled"]
    assert eng.order_events[0]["order_id"] == eng.order_events[1]["order_id"]
    assert eng.order_events[-1]["quantity"] == 1
    assert eng.order_events[-1]["fill_price"] == 11.0


def test_rejected_buy_is_retried_by_buy_and_hold():
    from backtester.strategy import BuyAndHoldStrategy

    strategy = BuyAndHoldStrategy(quantity=1)
    eng = BacktestEngine(feed=_bars(), strategy=strategy, starting_cash=1.0)
    eng.run()

    assert eng.n_rejected == 3
    assert len(eng.pending_orders) == 1
    assert strategy.bought == {"AAPL"}
    assert [event["status"] for event in eng.order_events] == [
        "pending",
        "rejected",
        "pending",
        "rejected",
        "pending",
        "rejected",
        "pending",
    ]


def test_duplicate_pending_order_is_rejected_without_replacing_resting_order():
    class RepeatedLimit:
        def on_bar(self, bar, history, portfolio):
            return {
                "symbol": bar.symbol,
                "action": "buy",
                "quantity": 1,
                "order_type": "limit",
                "price": 1.0,
            }

    eng = BacktestEngine(feed=_bars(), strategy=RepeatedLimit(), starting_cash=1000.0)
    eng.run()

    assert len(eng.pending_orders) == 1
    assert eng.pending_orders[0]["order_id"] == 1
    assert [event["status"] for event in eng.order_events] == [
        "pending",
        "rejected",
        "rejected",
        "rejected",
    ]
    assert all(
        event["reason"] == "duplicate_pending_order"
        for event in eng.order_events[1:]
    )


def test_cancel_order_records_terminal_event():
    class RestingLimit:
        def on_bar(self, bar, history, portfolio):
            if len(history) == 1:
                return {
                    "symbol": bar.symbol,
                    "action": "buy",
                    "quantity": 1,
                    "order_type": "limit",
                    "price": 1.0,
                }
            return None

    eng = BacktestEngine(feed=_bars(), strategy=RestingLimit(), starting_cash=1000.0)
    eng.run()

    assert eng.cancel_order(1)
    assert not eng.cancel_order(1)
    assert eng.pending_orders == []
    assert [event["status"] for event in eng.order_events] == ["pending", "cancelled"]


def test_malformed_order_is_rejected_with_event():
    class Malformed:
        def on_bar(self, bar, history, portfolio):
            return {"symbol": "", "action": "buy", "quantity": 1}

    eng = BacktestEngine(feed=_bars()[:1], strategy=Malformed(), starting_cash=1000.0)
    eng.run()

    assert eng.n_rejected == 1
    assert eng.order_events[0]["status"] == "rejected"
    assert eng.order_events[0]["reason"] == "malformed_order"
