import pytest

from backtester.datafeed import Bar
from backtester.engine import BacktestEngine
from backtester.portfolio import Portfolio


def test_commission_reduces_cash():
    p = Portfolio(starting_cash=1000.0, commission=5.0)
    ok = p.execute_order(timestamp="t0", symbol="AAPL", quantity=10, fill_price=10.0)
    assert ok is True
    assert p.cash == pytest.approx(1000.0 - 100.0 - 5.0)
    assert p.trade_log[0]["commission"] == pytest.approx(5.0)


def test_slippage_buy_pays_more_sell_gets_less():
    p = Portfolio(starting_cash=10000.0, slippage_bps=100.0)  # 1%
    p.execute_order(timestamp="t0", symbol="AAPL", quantity=10, fill_price=100.0)
    # buy effective 101
    assert p.positions["AAPL"].avg_price == pytest.approx(101.0)
    p.execute_order(timestamp="t1", symbol="AAPL", quantity=-10, fill_price=100.0)
    # sell effective 99, proceeds 990, cost 1010 -> realized -20
    assert p.trade_log[-1]["realized_pnl"] == pytest.approx(-20.0)
    assert p.realized_pnl == pytest.approx(-20.0)


def test_realized_pnl_simple_roundtrip():
    p = Portfolio(starting_cash=1000.0)
    p.execute_order(timestamp="t0", symbol="AAPL", quantity=10, fill_price=5.0)
    p.execute_order(timestamp="t1", symbol="AAPL", quantity=-10, fill_price=7.0)
    assert p.trade_log[-1]["realized_pnl"] == pytest.approx(20.0)
    assert p.realized_pnl == pytest.approx(20.0)


def test_engine_counts_rejected():
    bars = [
        Bar(timestamp=i, symbol="AAPL", open=100.0, high=100.0, low=100.0, close=100.0, volume=1)
        for i in range(3)
    ]

    class BuyHuge:
        def on_bar(self, bar, history, portfolio):
            return {"symbol": "AAPL", "action": "buy", "quantity": 10**9}

    eng = BacktestEngine(feed=bars, strategy=BuyHuge(), starting_cash=10.0)
    eng.run()
    assert eng.n_fills == 0
    assert eng.n_rejected >= 1
