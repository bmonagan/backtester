import math

from portfolio import Portfolio, Position
from datafeed import Bar


def test_initial_state():
    p = Portfolio(starting_cash=1000.0)
    assert p.cash == 1000.0
    assert p.positions == {}
    assert p.trade_log == []
    assert p.history == []


def test_buy_creates_position():
    p = Portfolio(starting_cash=1000.0)
    ok = p.execute_order(timestamp="t0", symbol="AAPL", quantity=10, fill_price=5.0)
    assert ok is True
    assert p.cash == 950.0
    pos = p.positions["AAPL"]
    assert pos.quantity == 10
    assert pos.avg_price == 5.0
    assert len(p.trade_log) == 1


def test_second_buy_updates_avg_price():
    p = Portfolio(starting_cash=1000.0)
    p.execute_order(timestamp="t0", symbol="AAPL", quantity=10, fill_price=5.0)
    p.execute_order(timestamp="t1", symbol="AAPL", quantity=10, fill_price=15.0)
    pos = p.positions["AAPL"]
    assert pos.quantity == 20
    assert pos.avg_price == 10.0  # (10*5 + 10*15) / 20
    assert p.cash == 1000.0 - 50.0 - 150.0


def test_full_sell_removes_position():
    p = Portfolio(starting_cash=1000.0)
    p.execute_order(timestamp="t0", symbol="AAPL", quantity=10, fill_price=5.0)
    ok = p.execute_order(timestamp="t1", symbol="AAPL", quantity=-10, fill_price=7.0)
    assert ok is True
    assert "AAPL" not in p.positions
    assert p.cash == 1000.0 - 50.0 + 70.0


def test_partial_sell_keeps_avg_price():
    p = Portfolio(starting_cash=1000.0)
    p.execute_order(timestamp="t0", symbol="AAPL", quantity=10, fill_price=5.0)
    ok = p.execute_order(timestamp="t1", symbol="AAPL", quantity=-4, fill_price=9.0)
    assert ok is True
    pos = p.positions["AAPL"]
    assert pos.quantity == 6
    assert pos.avg_price == 5.0  # cost basis unchanged on partial sale
    assert p.cash == 1000.0 - 50.0 + 36.0


def test_oversell_is_rejected():
    p = Portfolio(starting_cash=1000.0)
    p.execute_order(timestamp="t0", symbol="AAPL", quantity=3, fill_price=5.0)
    ok = p.execute_order(timestamp="t1", symbol="AAPL", quantity=-10, fill_price=5.0)
    assert ok is False
    assert p.positions["AAPL"].quantity == 3
    assert p.cash == 1000.0 - 15.0
    assert len(p.trade_log) == 1  # rejected order not logged


def test_selling_unknown_symbol_is_rejected():
    p = Portfolio(starting_cash=1000.0)
    ok = p.execute_order(timestamp="t1", symbol="MSFT", quantity=-5, fill_price=5.0)
    assert ok is False
    assert p.cash == 1000.0
    assert p.trade_log == []


def test_overspend_is_rejected():
    p = Portfolio(starting_cash=100.0)
    ok = p.execute_order(timestamp="t0", symbol="AAPL", quantity=100, fill_price=5.0)
    assert ok is False
    assert p.cash == 100.0
    assert p.positions == {}
    assert p.trade_log == []


def test_zero_quantity_is_noop():
    p = Portfolio(starting_cash=100.0)
    ok = p.execute_order(timestamp="t0", symbol="AAPL", quantity=0, fill_price=5.0)
    assert ok is False
    assert p.trade_log == []


def test_trade_log_records_balance():
    p = Portfolio(starting_cash=1000.0)
    p.execute_order(timestamp="t0", symbol="AAPL", quantity=10, fill_price=5.0)
    entry = p.trade_log[0]
    assert entry["timestamp"] == "t0"
    assert entry["symbol"] == "AAPL"
    assert entry["quantity"] == 10
    assert entry["fill_price"] == 5.0
    assert entry["cash_balance"] == 950.0


def test_mark_to_market_snapshot():
    p = Portfolio(starting_cash=1000.0)
    p.execute_order(timestamp="t0", symbol="AAPL", quantity=10, fill_price=5.0)
    bar = Bar(timestamp="t1", symbol="AAPL", open=6.0, high=6.5, low=5.5, close=6.0, volume=1)
    snap = p.mark_to_market("t1", [bar])
    # holdings_value = 10 * 6.0 ; cost basis = 10 * 5.0
    assert snap.cash == 950.0
    assert math.isclose(snap.holdings_value, 60.0)
    assert math.isclose(snap.total_equity, 1010.0)
    assert math.isclose(snap.unrealized_pnl, 10.0)
    assert len(p.history) == 1


def test_mark_to_market_flat_when_no_positions():
    p = Portfolio(starting_cash=1000.0)
    bar = Bar(timestamp="t1", symbol="AAPL", open=6.0, high=6.5, low=5.5, close=6.0, volume=1)
    snap = p.mark_to_market("t1", [bar])
    assert snap.holdings_value == 0.0
    assert snap.total_equity == 1000.0
    assert snap.unrealized_pnl == 0.0
