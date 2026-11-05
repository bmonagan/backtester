import pytest

from backtester.instruments import FeeSchedule, InstrumentSpec, MarginSchedule


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


def test_complete_future_metadata_is_execution_ready():
    spec = _complete_future()

    assert spec.execution_ready
    assert spec.multiplier == 50.0
    assert spec.contract_size == 1.0
    assert spec.margin_schedule.initial == 12000.0


def test_missing_market_conventions_are_not_execution_ready():
    spec = InstrumentSpec(
        symbol="AAPL",
        asset_class="equity",
        quote_currency="USD",
    )

    assert not spec.execution_ready


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


def test_future_requires_margin_for_execution_readiness():
    spec = _complete_future(margin_schedule=None)

    assert not spec.execution_ready


def test_future_metadata_rejects_invalid_margin_schedule():
    with pytest.raises(ValueError, match="maintenance margin"):
        MarginSchedule(currency="USD", initial=1000.0, maintenance=1200.0)


@pytest.mark.parametrize("value", [-1.0, float("nan")])
def test_fee_schedule_rejects_invalid_fees(value):
    with pytest.raises(ValueError):
        FeeSchedule(currency="USD", per_unit=value)
