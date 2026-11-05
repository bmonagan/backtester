import pytest

from backtester.datafeed import Bar
from backtester.engine import BacktestEngine
from backtester.instruments import FeeSchedule, InstrumentSpec, MarginSchedule
from backtester.portfolio import Portfolio


def _equity_spec(symbol="EQ"):
    return InstrumentSpec(
        symbol=symbol,
        asset_class="equity",
        quote_currency="USD",
        tick_size=0.01,
        quantity_increment=1.0,
        multiplier=10.0,
        calendar="XNYS",
        timezone="America/New_York",
        fee_schedule=FeeSchedule(currency="USD", per_unit=0.5, minimum=2.0),
    )


def _future_spec(symbol="FUT"):
    return InstrumentSpec(
        symbol=symbol,
        asset_class="future",
        quote_currency="USD",
        tick_size=0.25,
        quantity_increment=1.0,
        multiplier=50.0,
        contract_size=1.0,
        calendar="CME",
        timezone="America/Chicago",
        fee_schedule=FeeSchedule(currency="USD", exchange_per_contract=2.0),
        margin_schedule=MarginSchedule(
            currency="USD", initial=1000.0, maintenance=600.0
        ),
    )


def test_cash_instrument_multiplier_and_fee_schedule_drive_ledger():
    portfolio = Portfolio(10_000.0, instrument_specs={"EQ": _equity_spec()})

    assert portfolio.execute_order("t0", "EQ", 2, 100.0)
    assert portfolio.cash == pytest.approx(7_998.0)
    assert portfolio.positions["EQ"].avg_price == pytest.approx(100.1)
    assert portfolio.mark_to_market("t1", {"EQ": 120.0}).total_equity == pytest.approx(
        10_398.0
    )

    assert portfolio.execute_order("t2", "EQ", -2, 110.0)
    assert portfolio.cash == pytest.approx(10_196.0)
    assert portfolio.realized_pnl == pytest.approx(196.0)


def test_futures_variation_margin_multiplier_and_margin_are_accounted():
    portfolio = Portfolio(10_000.0, instrument_specs={"FUT": _future_spec()})
    assert portfolio.execute_order("t0", "FUT", 1, 100.0)
    assert portfolio.cash == pytest.approx(9_998.0)
    assert portfolio.mark_to_market("t1", {"FUT": 102.0}).total_equity == pytest.approx(
        10_098.0
    )
    assert portfolio.cash == pytest.approx(10_098.0)
    assert portfolio.history[-1].margin_used == pytest.approx(1000.0)

    assert portfolio.execute_order("t2", "FUT", -1, 103.0)
    assert portfolio.cash == pytest.approx(10_146.0)
    assert portfolio.realized_pnl == pytest.approx(150.0)
    assert portfolio.positions == {}


def test_future_order_rejects_insufficient_initial_margin_without_mutation():
    portfolio = Portfolio(999.0, instrument_specs={"FUT": _future_spec()})

    assert not portfolio.execute_order("t0", "FUT", 1, 100.0)
    assert portfolio.cash == 999.0
    assert portfolio.positions == {}
    assert portfolio.trade_log == []


def test_futures_cannot_open_shorts_when_shorts_are_disabled():
    portfolio = Portfolio(10_000.0, instrument_specs={"FUT": _future_spec()})

    assert not portfolio.execute_order("t0", "FUT", -1, 100.0)
    assert portfolio.cash == 10_000.0
    assert portfolio.positions == {}
    assert portfolio.trade_log == []


def test_split_and_dividend_preserve_and_reconcile_equity():
    spec = InstrumentSpec(
        symbol="EQ",
        asset_class="equity",
        quote_currency="USD",
        multiplier=1.0,
    )
    portfolio = Portfolio(10_000.0, instrument_specs={"EQ": spec})
    assert portfolio.execute_order("t0", "EQ", 10, 100.0)
    pre_split_equity = portfolio.current_equity({"EQ": 100.0})

    portfolio.apply_split("EQ", 2.0)
    assert portfolio.positions["EQ"].quantity == 20
    assert portfolio.positions["EQ"].avg_price == pytest.approx(50.0)
    assert portfolio.current_equity({"EQ": 50.0}) == pytest.approx(pre_split_equity)
    assert portfolio.apply_cash_dividend("EQ", 1.0) == pytest.approx(20.0)

    assert portfolio.execute_order("t1", "EQ", -20, 55.0)
    assert portfolio.cash == pytest.approx(10_120.0)
    assert portfolio.realized_pnl == pytest.approx(120.0)


@pytest.mark.parametrize("ratio", [0.0, -1.0, float("nan")])
def test_split_rejects_invalid_ratio(ratio):
    portfolio = Portfolio(1000.0)

    with pytest.raises(ValueError, match="split ratio"):
        portfolio.apply_split("EQ", ratio)


@pytest.mark.parametrize("dividend", [-1.0, float("inf")])
def test_dividend_rejects_invalid_amount(dividend):
    portfolio = Portfolio(1000.0)

    with pytest.raises(ValueError, match="dividend amount"):
        portfolio.apply_cash_dividend("EQ", dividend)


def test_fractional_quantity_increment_is_rejected():
    portfolio = Portfolio(10_000.0, instrument_specs={"EQ": _equity_spec()})

    assert not portfolio.execute_order("t0", "EQ", 0.5, 100.0)
    assert portfolio.cash == 10_000.0
    assert portfolio.positions == {}


def test_gross_leverage_cap_rejects_exposure_increase_but_allows_exit():
    spec = InstrumentSpec(
        symbol="EQ",
        asset_class="equity",
        quote_currency="USD",
        multiplier=1.0,
    )
    portfolio = Portfolio(
        2_000.0,
        instrument_specs={"EQ": spec},
        max_gross_leverage=0.5,
    )

    assert portfolio.execute_order("t0", "EQ", 10, 100.0)
    assert not portfolio.execute_order("t1", "EQ", 1, 100.0)
    assert portfolio.execute_order("t2", "EQ", -10, 100.0)
    assert portfolio.cash == pytest.approx(2_000.0)


@pytest.mark.parametrize("leverage", [0.0, -1.0, float("inf"), float("nan"), True])
def test_gross_leverage_cap_rejects_invalid_values(leverage):
    with pytest.raises(ValueError, match="max_gross_leverage"):
        Portfolio(1_000.0, max_gross_leverage=leverage)


def test_instrument_specs_must_share_cash_currency():
    usd = _equity_spec("USD_EQ")
    eur = InstrumentSpec(
        symbol="EUR_EQ",
        asset_class="equity",
        quote_currency="EUR",
    )

    with pytest.raises(ValueError, match="quote currencies"):
        Portfolio(10_000.0, instrument_specs={"USD_EQ": usd, "EUR_EQ": eur})


def test_strict_engine_requires_complete_metadata():
    bars = [Bar(0, "EQ", 10.0, 10.0, 10.0, 10.0, 100.0)]
    incomplete = InstrumentSpec("EQ", "equity", "USD")

    engine = BacktestEngine(
        bars,
        strategy=type("Quiet", (), {"on_bar": lambda *args, **kwargs: None})(),
        starting_cash=1000.0,
        instrument_specs={"EQ": incomplete},
        strict_instruments=True,
    )
    with pytest.raises(ValueError, match="Incomplete instrument metadata"):
        engine.run()


def test_strict_engine_requires_metadata_for_every_symbol():
    bars = [Bar(0, "EQ", 10.0, 10.0, 10.0, 10.0, 100.0)]
    engine = BacktestEngine(
        bars,
        strategy=type("Quiet", (), {"on_bar": lambda *args, **kwargs: None})(),
        starting_cash=1000.0,
        strict_instruments=True,
    )

    with pytest.raises(ValueError, match="Missing instrument metadata"):
        engine.run()


def test_engine_notional_sizing_uses_futures_multiplier():
    bars = [
        Bar(0, "FUT", 100.0, 100.0, 100.0, 100.0, 100.0),
        Bar(1, "FUT", 100.0, 100.0, 100.0, 100.0, 100.0),
    ]

    class BuyOnce:
        fired = False

        def on_bar(self, bar, history, portfolio):
            if self.fired:
                return None
            self.fired = True
            return {"symbol": "FUT", "action": "buy", "notional": 5000.0}

    engine = BacktestEngine(
        bars,
        strategy=BuyOnce(),
        starting_cash=10_000.0,
        instrument_specs={"FUT": _future_spec()},
        strict_instruments=True,
    )
    portfolio = engine.run()

    assert portfolio.positions["FUT"].quantity == 1
    assert engine.n_fills == 1
