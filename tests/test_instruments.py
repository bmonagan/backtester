import pytest

from backtester.instruments import (
    ExecutionCostModel,
    FeeSchedule,
    InstrumentSpec,
    MarginSchedule,
)


def _complete_future(**overrides):
    values = {
        "symbol": "ES=F",
        "asset_class": "future",
        "quote_currency": "USD",
        "tick_size": 0.25,
        "quantity_increment": 1.0,
        "multiplier": 50.0,
        "contract_size": 1.0,
        "calendar": "CME",
        "timezone": "America/Chicago",
        "fee_schedule": FeeSchedule(currency="USD", exchange_per_contract=2.5),
        "margin_schedule": MarginSchedule(
            currency="USD", initial=12000.0, maintenance=11000.0
        ),
    }
    values.update(overrides)
    return InstrumentSpec(**values)


def test_complete_future_metadata_is_complete():
    spec = _complete_future()

    assert spec.metadata_complete
    assert spec.multiplier == 50.0
    assert spec.contract_size == 1.0
    assert spec.tick_value == pytest.approx(12.5)
    assert spec.margin_schedule.initial == 12000.0


def test_missing_market_conventions_are_incomplete():
    spec = InstrumentSpec(
        symbol="AAPL",
        asset_class="equity",
        quote_currency="USD",
    )

    assert not spec.metadata_complete


@pytest.mark.parametrize(
    "field,value",
    [
        ("tick_size", 0.0),
        ("quantity_increment", -1.0),
        ("multiplier", float("inf")),
        ("contract_size", True),
    ],
)
def test_instrument_rejects_invalid_positive_metadata(field, value):
    with pytest.raises(ValueError):
        _complete_future(**{field: value})


def test_instrument_rejects_unknown_asset_class():
    with pytest.raises(ValueError, match="unsupported asset_class"):
        InstrumentSpec("XYZ", "other", "USD")


def test_instrument_rejects_mismatched_fee_currency():
    with pytest.raises(ValueError, match="fee schedule currency"):
        _complete_future(fee_schedule=FeeSchedule(currency="EUR"))


def test_future_requires_margin_for_complete_metadata():
    spec = _complete_future(margin_schedule=None)

    assert not spec.metadata_complete


def test_tick_value_is_unknown_when_either_input_is_missing():
    spec = InstrumentSpec("AAPL", "equity", "USD", tick_size=0.01)

    assert spec.tick_value is None


def test_future_metadata_rejects_invalid_margin_schedule():
    with pytest.raises(ValueError, match="maintenance margin"):
        MarginSchedule(currency="USD", initial=1000.0, maintenance=1200.0)


@pytest.mark.parametrize("value", [-1.0, float("nan")])
def test_fee_schedule_rejects_invalid_fees(value):
    with pytest.raises(ValueError):
        FeeSchedule(currency="USD", per_unit=value)


def test_execution_cost_scenario_scales_spread_and_impact():
    model = ExecutionCostModel(
        half_spread_bps=2.0,
        slippage_bps=3.0,
        impact_bps_at_full_participation=20.0,
        scenario="adverse",
    )

    assert model.scenario_multiplier == 1.5
    assert model.impact_bps(0.25) == pytest.approx(7.5)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"half_spread_bps": -1},
        {"slippage_bps": float("nan")},
        {"impact_bps_at_full_participation": float("inf")},
        {"max_participation_rate": 0},
        {"max_participation_rate": 1.1},
        {"scenario": "optimistic"},
    ],
)
def test_execution_cost_model_rejects_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        ExecutionCostModel(**kwargs)


def test_execution_impact_rejects_invalid_participation():
    with pytest.raises(ValueError, match="participation_rate"):
        ExecutionCostModel().impact_bps(float("nan"))
