import pytest

from backtester.datafeed import Bar
from backtester.engine import BacktestEngine
from backtester.strategy import (
    BollingerMeanReversionStrategy,
    BuyAndHoldStrategy,
    DonchianBreakoutStrategy,
    RsiMomentumStrategy,
    SmaCrossoverStrategy,
)


def _bar(ts, price, symbol="AAPL"):
    return Bar(
        timestamp=ts, symbol=symbol, open=price, high=price,
        low=price, close=price, volume=1,
    )


def _run_scripted(orders_by_bar, bars, cash=10000.0, **eng_kwargs):
    class Scripted:
        def __init__(self):
            self.i = -1

        def on_bar(self, bar, history, portfolio):
            self.i += 1
            if self.i < len(orders_by_bar):
                return orders_by_bar[self.i]
            return None

    eng = BacktestEngine(feed=bars, strategy=Scripted(), starting_cash=cash, **eng_kwargs)
    return eng, eng.run()


# --- _resolve_shares unit tests ---


def test_quantity_passes_through():
    assert BacktestEngine._resolve_shares({"quantity": 10}, 100.0, 10000.0, 0.0) == 10.0
    assert BacktestEngine._resolve_shares({"quantity": -4}, 100.0, 10000.0, 0.0) == -4.0


def _reject(order):
    return BacktestEngine._resolve_shares(order, 100.0, 10000.0, 0.0) == "reject"


def test_missing_or_doubled_magnitude_rejected():
    assert _reject({})
    assert _reject({"quantity": 10, "notional": 100})
    assert _reject({"notional": 100, "fraction": 0.5})
    assert _reject({"quantity": 10, "fraction": 0.5})


def test_bad_magnitude_types_rejected():
    assert BacktestEngine._resolve_shares({"quantity": "10"}, 100.0, 10000.0, 0.0) == "reject"
    assert BacktestEngine._resolve_shares({"quantity": True}, 100.0, 10000.0, 0.0) == "reject"
    assert BacktestEngine._resolve_shares({"notional": "x"}, 100.0, 10000.0, 0.0) == "reject"
    assert BacktestEngine._resolve_shares({"fraction": "0.5"}, 100.0, 10000.0, 0.0) == "reject"


def test_notional_truncates_toward_zero():
    assert BacktestEngine._resolve_shares({"notional": 1000}, 30.0, 999999.0, 0.0) == 33.0
    assert BacktestEngine._resolve_shares({"notional": -1000}, 30.0, 999999.0, 0.0) == -33.0
    # equity is irrelevant for notional
    assert BacktestEngine._resolve_shares({"notional": 1000}, 30.0, 1.0, 0.0) == 33.0


def test_notional_dust_rejected():
    assert BacktestEngine._resolve_shares({"notional": 10}, 100.0, 999999.0, 0.0) == "reject"
    assert BacktestEngine._resolve_shares({"notional": -10}, 100.0, 999999.0, 0.0) == "reject"


def test_bad_fill_price_rejected_for_sized_orders():
    assert BacktestEngine._resolve_shares({"notional": 100}, 0.0, 999999.0, 0.0) == "reject"
    assert BacktestEngine._resolve_shares({"notional": 100}, -5.0, 999999.0, 0.0) == "reject"


def test_fraction_out_of_range_rejected():
    for bad in (0, -0.5, 1.5, 2.0):
        o = {"action": "buy", "fraction": bad}
        assert BacktestEngine._resolve_shares(o, 100.0, 10000.0, 0.0) == "reject"


def test_fraction_buy_scales_with_equity():
    o = {"action": "buy", "fraction": 0.1}
    assert BacktestEngine._resolve_shares(o, 100.0, 10000.0, 0.0) == 10.0
    assert BacktestEngine._resolve_shares(o, 100.0, 20000.0, 0.0) == 20.0
    assert BacktestEngine._resolve_shares(o, 100.0, 5000.0, 0.0) == 5.0


def test_fraction_sell_closes_portion_of_position():
    o = {"action": "sell", "fraction": 0.5}
    assert BacktestEngine._resolve_shares(o, 100.0, 999999.0, 50.0) == -25.0
    full = {"action": "sell", "fraction": 1.0}
    assert BacktestEngine._resolve_shares(full, 100.0, 999999.0, 50.0) == -50.0


def test_fraction_sell_without_position_rejected():
    o = {"action": "sell", "fraction": 0.5}
    assert BacktestEngine._resolve_shares(o, 100.0, 999999.0, 0.0) == "reject"


def test_fraction_without_action_rejected():
    assert BacktestEngine._resolve_shares({"fraction": 0.5}, 100.0, 10000.0, 0.0) == "reject"


# --- strategy constructor tests ---


def test_strategy_sizing_defaults_to_100_shares():
    assert SmaCrossoverStrategy().sizing == {"quantity": 100}
    assert BuyAndHoldStrategy().sizing == {"quantity": 100}


def test_strategy_sizing_exclusivity():
    with pytest.raises(ValueError):
        SmaCrossoverStrategy(quantity=10, notional=100.0)
    with pytest.raises(ValueError):
        SmaCrossoverStrategy(notional=100.0, fraction=0.5)
    with pytest.raises(ValueError):
        BuyAndHoldStrategy(quantity=10, fraction=0.5)


def test_strategy_sizing_validation():
    with pytest.raises(TypeError):
        SmaCrossoverStrategy(notional="100")
    with pytest.raises(ValueError):
        SmaCrossoverStrategy(notional=0)
    with pytest.raises(ValueError):
        SmaCrossoverStrategy(notional=-5)
    with pytest.raises(TypeError):
        SmaCrossoverStrategy(fraction=True)
    with pytest.raises(ValueError):
        SmaCrossoverStrategy(fraction=0)
    with pytest.raises(ValueError):
        SmaCrossoverStrategy(fraction=1.5)


def test_all_strategies_accept_sizing():
    assert RsiMomentumStrategy(notional=1000.0).sizing == {"notional": 1000.0}
    assert BollingerMeanReversionStrategy(fraction=0.2).sizing == {"fraction": 0.2}
    assert DonchianBreakoutStrategy(notional=500.0).sizing == {"notional": 500.0}
    s = BuyAndHoldStrategy(notional=250.0)
    order = s.on_bar(
        bar=_bar(0, 50.0), history=[_bar(0, 50.0)], portfolio=None
    )
    assert order is not None
    assert order["notional"] == 250.0
    assert "quantity" not in order


# --- engine integration ---


def test_engine_notional_buy():
    bars = [_bar(0, 100.0), _bar(1, 100.0)]
    o = {"symbol": "AAPL", "action": "buy", "notional": 1000.0}
    eng, pf = _run_scripted([o, None], bars)
    assert pf.positions["AAPL"].quantity == 10
    assert pf.cash == pytest.approx(9000.0)
    assert eng.n_fills == 1


def test_engine_notional_dust_rejected():
    bars = [_bar(0, 100.0), _bar(1, 100.0)]
    o = {"symbol": "AAPL", "action": "buy", "notional": 10.0}
    eng, pf = _run_scripted([o, None], bars)
    assert pf.positions == {}
    assert eng.n_rejected == 1


def test_engine_fraction_buy_targets_exposure():
    bars = [_bar(0, 100.0), _bar(1, 100.0)]
    o = {"symbol": "AAPL", "action": "buy", "fraction": 0.1}
    _, pf = _run_scripted([o, None], bars, cash=10000.0)
    assert pf.positions["AAPL"].quantity == 10
    equity = pf.current_equity({"AAPL": 100.0})
    assert pf.positions["AAPL"].quantity * 100.0 / equity == pytest.approx(0.1)


def test_engine_fraction_sell_flattens():
    bars = [_bar(0, 100.0), _bar(1, 100.0), _bar(2, 100.0)]
    buy = {"symbol": "AAPL", "action": "buy", "quantity": 10}
    flat = {"symbol": "AAPL", "action": "sell", "fraction": 1.0}
    _, pf = _run_scripted([buy, flat, None], bars)
    assert "AAPL" not in pf.positions


def test_sized_strategy_end_to_end_exposure():
    bars = [_bar(i, 100.0 + i) for i in range(10)]

    class AggressiveBuyHold:
        def __init__(self):
            self.s = BuyAndHoldStrategy(fraction=0.5)
            self.fired = False

        def on_bar(self, bar, history, portfolio):
            if self.fired:
                return None
            self.fired = True
            return {
                "symbol": bar.symbol, "action": "buy",
                "fraction": self.s.sizing["fraction"],
            }

    eng = BacktestEngine(feed=bars, strategy=AggressiveBuyHold(), starting_cash=10000.0)
    pf = eng.run()
    pos = pf.positions["AAPL"]
    # fills at bar1 open of 101: trunc(0.5 * 10000 / 101) = 49
    assert pos.quantity == 49
    assert pos.quantity * 101.0 / 10000.0 == pytest.approx(0.4949, abs=1e-3)
