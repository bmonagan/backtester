import pytest

from backtester.datafeed import Bar
from backtester.engine import BacktestEngine


def _bar(ts, o, h, lo, c, symbol="AAPL"):
    return Bar(
        timestamp=ts, symbol=symbol, open=o, high=h,
        low=lo, close=c, volume=1,
    )


def _run(orders_by_bar, bars, **eng_kwargs):
    """orders_by_bar: list aligned to bars; each entry an order dict or None
    emitted when that bar is processed (filled from the next bar on)."""

    class Scripted:
        def __init__(self):
            self.i = -1

        def on_bar(self, bar, history, portfolio):
            self.i += 1
            if self.i < len(orders_by_bar):
                return orders_by_bar[self.i]
            return None

    eng = BacktestEngine(feed=bars, strategy=Scripted(), starting_cash=10000.0, **eng_kwargs)
    pf = eng.run()
    return eng, pf


def test_market_default_fills_at_open():
    bars = [_bar(0, 100, 101, 99, 100), _bar(1, 102, 103, 101, 102)]
    eng, pf = _run([{"symbol": "AAPL", "action": "buy", "quantity": 10}, None], bars)
    assert pf.positions["AAPL"].avg_price == pytest.approx(102.0)
    assert eng.n_fills == 1


def test_limit_buy_rests_then_fills():
    bars = [
        _bar(0, 100, 101, 99, 100),
        _bar(1, 100, 101, 99, 100),  # low 99 > 95, rests
        _bar(2, 100, 100, 90, 92),  # low 90 <= 95, fills at 95
    ]
    limit = {
        "symbol": "AAPL", "action": "buy", "quantity": 10,
        "order_type": "limit", "price": 95.0,
    }
    eng, pf = _run([limit, None, None], bars)
    assert pf.positions["AAPL"].avg_price == pytest.approx(95.0)
    assert pf.cash == pytest.approx(10000.0 - 950.0)
    assert eng.n_fills == 1


def test_limit_never_touched_stays_pending():
    bars = [_bar(0, 100, 101, 99, 100), _bar(1, 100, 101, 99, 100)]
    limit = {
        "symbol": "AAPL", "action": "buy", "quantity": 10,
        "order_type": "limit", "price": 50.0,
    }
    eng, pf = _run([limit, None], bars)
    assert pf.positions == {}
    assert len(eng.pending_orders) == 1
    assert eng.n_fills == 0


def test_limit_buy_gap_through_fills_at_open():
    bars = [_bar(0, 100, 101, 99, 100), _bar(1, 90, 91, 89, 90)]
    limit = {
        "symbol": "AAPL", "action": "buy", "quantity": 10,
        "order_type": "limit", "price": 95.0,
    }
    _, pf = _run([limit, None], bars)
    assert pf.positions["AAPL"].avg_price == pytest.approx(90.0)


def test_limit_sell_fills_at_trigger_or_better():
    bars = [
        _bar(0, 100, 101, 99, 100),
        _bar(1, 100, 101, 99, 100),  # market buy fills here at 100
        _bar(2, 119, 121, 118, 120),  # high 121 >= 120, fills at 120
    ]
    buy = {"symbol": "AAPL", "action": "buy", "quantity": 10}
    sell = {
        "symbol": "AAPL", "action": "sell", "quantity": -10,
        "order_type": "limit", "price": 120.0,
    }
    eng, pf = _run([buy, sell, None], bars)
    assert "AAPL" not in pf.positions
    assert pf.trade_log[-1]["effective_price"] == pytest.approx(120.0)
    assert pf.realized_pnl == pytest.approx(200.0)


def test_stop_buy_breakout_fills():
    bars = [
        _bar(0, 100, 101, 99, 100),
        _bar(1, 101, 106, 100, 105),  # high 106 >= 105, fills at 105
    ]
    stop = {
        "symbol": "AAPL", "action": "buy", "quantity": 10,
        "order_type": "stop", "price": 105.0,
    }
    _, pf = _run([stop, None], bars)
    assert pf.positions["AAPL"].avg_price == pytest.approx(105.0)


def test_stop_sell_protects_long():
    bars = [
        _bar(0, 100, 101, 99, 100),
        _bar(1, 110, 111, 109, 110),  # buy fills at 110
        _bar(2, 108, 109, 100, 101),  # low 100 <= 105, fills at 105
    ]
    buy = {"symbol": "AAPL", "action": "buy", "quantity": 10}
    stop = {
        "symbol": "AAPL", "action": "sell", "quantity": -10,
        "order_type": "stop", "price": 105.0,
    }
    _, pf = _run([buy, stop, None], bars)
    assert "AAPL" not in pf.positions
    assert pf.trade_log[-1]["effective_price"] == pytest.approx(105.0)
    assert pf.realized_pnl == pytest.approx(-50.0)


def test_stop_gap_through_fills_at_open():
    bars = [_bar(0, 100, 101, 99, 100), _bar(1, 80, 81, 79, 80)]
    stop = {
        "symbol": "AAPL", "action": "sell", "quantity": -10,
        "order_type": "stop", "price": 90.0,
    }
    eng = BacktestEngine(feed=bars, strategy=None, starting_cash=10000.0)
    assert eng._trigger_price(stop, bars[1]) == pytest.approx(80.0)


def test_limit_without_price_rejected():
    bars = [_bar(0, 100, 101, 99, 100), _bar(1, 100, 101, 99, 100)]
    bad = {"symbol": "AAPL", "action": "buy", "quantity": 10, "order_type": "limit"}
    eng, pf = _run([bad, None], bars)
    assert pf.positions == {}
    assert eng.n_rejected == 1
    assert eng.pending_orders == []


def test_unknown_order_type_rejected():
    bars = [_bar(0, 100, 101, 99, 100), _bar(1, 100, 101, 99, 100)]
    bad = {"symbol": "AAPL", "action": "buy", "quantity": 10, "order_type": "iceberg"}
    eng, pf = _run([bad, None], bars)
    assert pf.positions == {}
    assert eng.n_rejected == 1


def test_trigger_unit_matrix():
    eng = BacktestEngine(feed=[], strategy=None, starting_cash=1.0)
    bar = _bar(0, 100, 110, 90, 105)
    assert eng._trigger_price({"quantity": 1, "order_type": "market"}, bar) == 100
    assert eng._trigger_price({"quantity": 1}, bar) == 100  # default
    assert eng._trigger_price({"quantity": 1, "order_type": "limit", "price": 95}, bar) == 95
    assert eng._trigger_price({"quantity": -1, "order_type": "limit", "price": 105}, bar) == 105
    assert eng._trigger_price({"quantity": 1, "order_type": "limit", "price": 80}, bar) is None
    assert eng._trigger_price({"quantity": -1, "order_type": "limit", "price": 120}, bar) is None
    assert eng._trigger_price({"quantity": 1, "order_type": "stop", "price": 105}, bar) == 105
    assert eng._trigger_price({"quantity": -1, "order_type": "stop", "price": 95}, bar) == 95
    assert eng._trigger_price({"quantity": 1, "order_type": "stop", "price": 120}, bar) is None
    assert eng._trigger_price({"quantity": -1, "order_type": "stop", "price": 80}, bar) is None
