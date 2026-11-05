"""Typed instrument metadata used by strict simulation modes."""

from dataclasses import dataclass
from math import isfinite
from typing import Literal

AssetClass = Literal["equity", "future", "crypto"]
CostScenario = Literal["base", "adverse", "severe"]


@dataclass(frozen=True)
class ExecutionCostModel:
    """Conservative per-fill execution assumptions; not a calibrated forecast."""

    half_spread_bps: float = 0.0
    slippage_bps: float = 0.0
    impact_bps_at_full_participation: float = 0.0
    max_participation_rate: float | None = None
    scenario: CostScenario = "base"

    def __post_init__(self) -> None:
        for name in (
            "half_spread_bps",
            "slippage_bps",
            "impact_bps_at_full_participation",
        ):
            _validate_nonnegative(name, getattr(self, name))
        if self.max_participation_rate is not None and (
            isinstance(self.max_participation_rate, bool)
            or not isinstance(self.max_participation_rate, (int, float))
            or not isfinite(self.max_participation_rate)
            or not 0 < self.max_participation_rate <= 1
        ):
            raise ValueError("max_participation_rate must be in (0, 1]")
        if self.scenario not in ("base", "adverse", "severe"):
            raise ValueError("scenario must be base, adverse, or severe")

    @property
    def scenario_multiplier(self) -> float:
        return {"base": 1.0, "adverse": 1.5, "severe": 2.5}[self.scenario]

    def impact_bps(self, participation_rate: float) -> float:
        if (
            isinstance(participation_rate, bool)
            or not isinstance(participation_rate, (int, float))
            or not isfinite(participation_rate)
            or participation_rate < 0
        ):
            raise ValueError("participation_rate must be finite and nonnegative")
        return (
            self.impact_bps_at_full_participation
            * min(participation_rate, 1.0)
            * self.scenario_multiplier
        )


def _validate_positive(name: str, value: float | None) -> None:
    if value is not None and (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
        or value <= 0
    ):
        raise ValueError(f"{name} must be a finite number greater than zero")


def _validate_nonnegative(name: str, value: float) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
        or value < 0
    ):
        raise ValueError(f"{name} must be a finite number greater than or equal to zero")


def _validate_currency(currency: str) -> None:
    if (
        not isinstance(currency, str)
        or len(currency) != 3
        or not currency.isascii()
        or not currency.isalpha()
        or currency.upper() != currency
    ):
        raise ValueError("currency must be a three-letter uppercase code")


@dataclass(frozen=True)
class FeeSchedule:
    """Explicit fee amounts in currency units, with rate charged on notional."""

    currency: str
    per_unit: float = 0.0
    notional_rate: float = 0.0
    minimum: float = 0.0
    exchange_per_contract: float = 0.0

    def __post_init__(self) -> None:
        _validate_currency(self.currency)
        for name in (
            "per_unit",
            "notional_rate",
            "minimum",
            "exchange_per_contract",
        ):
            _validate_nonnegative(name, getattr(self, name))


@dataclass(frozen=True)
class MarginSchedule:
    """Initial and maintenance margin per traded unit, in the stated currency."""

    currency: str
    initial: float
    maintenance: float

    def __post_init__(self) -> None:
        _validate_currency(self.currency)
        _validate_positive("initial", self.initial)
        _validate_positive("maintenance", self.maintenance)
        if self.maintenance > self.initial:
            raise ValueError("maintenance margin must not exceed initial margin")


@dataclass(frozen=True)
class InstrumentSpec:
    """Contract and market conventions for one symbol.

    ``multiplier`` converts a one-unit quoted price change into P&L in the
    quote currency. ``contract_size`` records underlying units per traded
    contract; it is descriptive and is not an additional P&L multiplier.
    """

    symbol: str
    asset_class: AssetClass
    quote_currency: str
    tick_size: float | None = None
    quantity_increment: float | None = None
    multiplier: float | None = None
    contract_size: float | None = None
    calendar: str | None = None
    timezone: str | None = None
    fee_schedule: FeeSchedule | None = None
    margin_schedule: MarginSchedule | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("symbol must not be empty")
        if self.asset_class not in ("equity", "future", "crypto"):
            raise ValueError(f"unsupported asset_class: {self.asset_class}")
        _validate_currency(self.quote_currency)
        _validate_positive("tick_size", self.tick_size)
        _validate_positive("quantity_increment", self.quantity_increment)
        _validate_positive("multiplier", self.multiplier)
        _validate_positive("contract_size", self.contract_size)
        if self.calendar is not None and (
            not isinstance(self.calendar, str) or not self.calendar.strip()
        ):
            raise ValueError("calendar must not be empty when provided")
        if self.timezone is not None and (
            not isinstance(self.timezone, str) or not self.timezone.strip()
        ):
            raise ValueError("timezone must not be empty when provided")
        if (
            self.fee_schedule is not None
            and self.fee_schedule.currency != self.quote_currency
        ):
            raise ValueError("fee schedule currency must match quote_currency")
        if (
            self.margin_schedule is not None
            and self.margin_schedule.currency != self.quote_currency
        ):
            raise ValueError("margin schedule currency must match quote_currency")

    @property
    def metadata_complete(self) -> bool:
        required = (
            self.tick_size,
            self.quantity_increment,
            self.multiplier,
            self.calendar,
            self.timezone,
            self.fee_schedule,
        )
        if any(value is None for value in required):
            return False
        if self.asset_class == "future":
            return self.contract_size is not None and self.margin_schedule is not None
        return True

    @property
    def tick_value(self) -> float | None:
        if self.tick_size is None or self.multiplier is None:
            return None
        return self.tick_size * self.multiplier
