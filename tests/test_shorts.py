import pytest

from backtester.datafeed import Bar
from backtester.engine import BacktestEngine
from backtester.metrics import win_rate
from backtester.portfolio import Portfolio


def test_shorts_rejected_by_default():
    p = Portfolio(starting_cash=1000.0)
    assert p.execute_order("t0", "AAPL", -10, 50.0) is False
    assert p.positions == {}
    assert p.cash == 1000.0
    assert p.trade_log == []


def test_open_short_credits_cash():
    p = Portfolio(starting_cash=1000.0, allow_shorts=True)
    assert p.execute_order("t0", "AAPL", -10, 50.0) is True
    assert p.cash == pytest.approx(1500.0)
    pos = p.positions["AAPL"]
    assert pos.quantity == -10
    assert pos.avg_price == pytest.approx(50.0)
    assert p.trade_log[0]["realized_pnl"] == pytest.approx(0.0)


def test_short_unrealized_tracks_adverse_move():
    p = Portfolio(starting_cash=1000.0, allow_shorts=True)
    p.execute_order("t0", "AAPL", -10, 50.0)
    snap = p.mark_to_market("t1", {"AAPL": 60.0})
    assert snap.holdings_value == pytest.approx(-600.0)
    assert snap.total_equity == pytest.approx(900.0)
    assert snap.unrealized_pnl == pytest.approx(-100.0)


def test_cover_short_locks_profit():
    p = Portfolio(starting_cash=1000.0, allow_shorts=True)
    p.execute_order("t0", "AAPL", -10, 50.0)
    assert p.execute_order("t1", "AAPL", 10, 40.0) is True
    assert p.cash == pytest.approx(1100.0)
    assert "AAPL" not in p.positions
    assert p.trade_log[-1]["realized_pnl"] == pytest.approx(100.0)
    assert p.realized_pnl == pytest.approx(100.0)


def test_cover_short_at_loss():
    p = Portfolio(starting_cash=1000.0, allow_shorts=True)
    p.execute_order("t0", "AAPL", -10, 50.0)
    p.execute_order("t1", "AAPL", 10, 70.0)
    assert p.cash == pytest.approx(800.0)
    assert p.realized_pnl == pytest.approx(-200.0)


def test_partial_cover_keeps_basis():
    p = Portfolio(starting_cash=1000.0, allow_shorts=True)
    p.execute_order("t0", "AAPL", -10, 50.0)
    p.execute_order("t1", "AAPL", 4, 40.0)
    pos = p.positions["AAPL"]
    assert pos.quantity == -6
    assert pos.avg_price == pytest.approx(50.0)
    assert p.realized_pnl == pytest.approx(40.0)


def test_extending_short_averages_credit():
    p = Portfolio(starting_cash=1000.0, allow_shorts=True)
    p.execute_order("t0", "AAPL", -10, 50.0)
    p.execute_order("t1", "AAPL", -5, 60.0)
    pos = p.positions["AAPL"]
    assert pos.quantity == -15
    assert pos.avg_price == pytest.approx((10 * 50.0 + 5 * 60.0) / 15)
    assert p.cash == pytest.approx(1800.0)


def test_buy_flips_short_to_long():
    p = Portfolio(starting_cash=1000.0, allow_shorts=True)
    p.execute_order("t0", "AAPL", -10, 50.0)
    assert p.execute_order("t1", "AAPL", 15, 40.0) is True
    pos = p.positions["AAPL"]
    assert pos.quantity == 5
    assert pos.avg_price == pytest.approx(40.0)
    assert p.cash == pytest.approx(900.0)
    assert p.realized_pnl == pytest.approx(100.0)


def test_sell_flips_long_to_short():
    p = Portfolio(starting_cash=1000.0, allow_shorts=True)
    p.execute_order("t0", "AAPL", 10, 50.0)
    assert p.execute_order("t1", "AAPL", -15, 60.0) is True
    pos = p.positions["AAPL"]
    assert pos.quantity == -5
    assert pos.avg_price == pytest.approx(60.0)
    assert p.cash == pytest.approx(1400.0)
    # closed long: (60-50)*10 = +100
    assert p.realized_pnl == pytest.approx(100.0)


def test_short_with_commission():
    p = Portfolio(starting_cash=1000.0, allow_shorts=True, commission=5.0)
    p.execute_order("t0", "AAPL", -10, 50.0)
    assert p.cash == pytest.approx(1495.0)
    p.execute_order("t1", "AAPL", 10, 40.0)
    assert p.cash == pytest.approx(1495.0 - 405.0)
    assert p.realized_pnl == pytest.approx(90.0)


def test_cover_beyond_cash_rejected():
    p = Portfolio(starting_cash=100.0, allow_shorts=True)
    p.execute_order("t0", "AAPL", -5, 50.0)  # cash 350
    assert p.execute_order("t1", "AAPL", 5, 1000.0) is False
    assert p.positions["AAPL"].quantity == -5


def test_short_equity_and_missing_price():
    p = Portfolio(starting_cash=1000.0, allow_shorts=True)
    p.execute_order("t0", "AAPL", -10, 50.0)
    assert p.current_equity({"AAPL": 40.0}) == pytest.approx(1100.0)
    with pytest.raises(KeyError):
        p.current_equity({"MSFT": 1.0})
    with pytest.raises(KeyError):
        p.mark_to_market("t1", {"MSFT": 1.0})


def test_engine_short_roundtrip():
    bars = [
        Bar(timestamp=i, symbol="AAPL", open=c, high=c, low=c, close=c, volume=1)
        for i, c in enumerate([50, 50, 40, 40])
    ]

    class ShortThenCover:
        def __init__(self):
            self.n = 0

        def on_bar(self, bar, history, portfolio):
            self.n += 1
            if self.n == 1:
                return {"symbol": "AAPL", "action": "sell", "quantity": -10}
            if self.n == 3:
                return {"symbol": "AAPL", "action": "buy", "quantity": 10}
            return None

    eng = BacktestEngine(
        feed=bars, strategy=ShortThenCover(), starting_cash=1000.0,
        allow_shorts=True,
    )
    pf = eng.run()
    assert "AAPL" not in pf.positions
    assert pf.realized_pnl == pytest.approx(100.0)


def test_win_rate_counts_shorts():
    log = [
        {"symbol": "AAPL", "quantity": -10, "fill_price": 50.0},
        {"symbol": "AAPL", "quantity": 10, "fill_price": 40.0},
    ]
    assert win_rate(log) == pytest.approx(1.0)

    log = [
        {"symbol": "AAPL", "quantity": -10, "fill_price": 50.0},
        {"symbol": "AAPL", "quantity": 10, "fill_price": 60.0},
    ]
    assert win_rate(log) == pytest.approx(0.0)

    log = [
        {"symbol": "AAPL", "quantity": 10, "fill_price": 5.0},
        {"symbol": "AAPL", "quantity": -10, "fill_price": 7.0},
        {"symbol": "AAPL", "quantity": -10, "fill_price": 50.0},
        {"symbol": "AAPL", "quantity": 10, "fill_price": 60.0},
    ]
    assert win_rate(log) == pytest.approx(0.5)
