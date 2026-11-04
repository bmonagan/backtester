"""Additional long-only daily-bar strategy families."""

from typing import Optional

from backtester.strategy import (
    Order,
    Strategy,
    _sized_order,
    _validate_sizing,
)


def _positive_period(name: str, value: int, minimum: int = 1) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")


def _number(name: str, value: float, *, positive: bool = False) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    if positive and value <= 0:
        raise ValueError(f"{name} must be greater than 0")


def _ema(values: list[float], period: int) -> list[float]:
    alpha = 2.0 / (period + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append(alpha * value + (1 - alpha) * result[-1])
    return result


def _true_ranges(history) -> list[float]:
    return [
        max(
            bar.high - bar.low,
            abs(bar.high - previous.close),
            abs(bar.low - previous.close),
        )
        for previous, bar in zip(history[:-1], history[1:])
    ]


class _LongOnlySignalStrategy(Strategy):
    def __init__(self, quantity=None, notional=None, fraction=None):
        self.sizing = _validate_sizing(quantity, notional, fraction)
        self.in_position: set[str] = set()

    def _order(self, symbol: str, entering: bool) -> Order:
        if entering:
            self.in_position.add(symbol)
            return _sized_order(self.sizing, symbol, "buy")
        self.in_position.discard(symbol)
        return _sized_order(self.sizing, symbol, "sell")


class EmaCrossoverStrategy(_LongOnlySignalStrategy):
    """Buy when the fast EMA crosses above the slow EMA; exit on a cross below."""

    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        quantity=None,
        notional=None,
        fraction=None,
    ):
        _positive_period("fast_period", fast_period)
        _positive_period("slow_period", slow_period)
        if fast_period >= slow_period:
            raise ValueError("fast_period must be less than slow_period")
        self.fast_period = fast_period
        self.slow_period = slow_period
        super().__init__(quantity, notional, fraction)

    def on_bar(self, bar, history, portfolio) -> Optional[Order]:
        if len(history) < self.slow_period + 1:
            return None
        closes = [item.close for item in history]
        previous = closes[:-1]
        fast = _ema(closes, self.fast_period)
        slow = _ema(closes, self.slow_period)
        prev_fast = _ema(previous, self.fast_period)[-1]
        prev_slow = _ema(previous, self.slow_period)[-1]
        crossed_up = prev_fast <= prev_slow and fast[-1] > slow[-1]
        crossed_down = prev_fast >= prev_slow and fast[-1] < slow[-1]
        if bar.symbol not in self.in_position and crossed_up:
            return self._order(bar.symbol, True)
        if bar.symbol in self.in_position and crossed_down:
            return self._order(bar.symbol, False)
        return None


class MacdStrategy(_LongOnlySignalStrategy):
    """Buy on a MACD/signal-line bullish cross; exit on its bearish cross."""

    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        quantity=None,
        notional=None,
        fraction=None,
    ):
        for name, value in (
            ("fast_period", fast_period),
            ("slow_period", slow_period),
            ("signal_period", signal_period),
        ):
            _positive_period(name, value)
        if fast_period >= slow_period:
            raise ValueError("fast_period must be less than slow_period")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        super().__init__(quantity, notional, fraction)

    def _lines(self, closes: list[float]) -> tuple[list[float], list[float]]:
        fast = _ema(closes, self.fast_period)
        slow = _ema(closes, self.slow_period)
        macd = [a - b for a, b in zip(fast, slow)]
        return macd, _ema(macd, self.signal_period)

    def on_bar(self, bar, history, portfolio) -> Optional[Order]:
        if len(history) < self.slow_period + self.signal_period + 1:
            return None
        closes = [item.close for item in history]
        macd, signal = self._lines(closes)
        prev_macd, prev_signal = self._lines(closes[:-1])
        crossed_up = prev_macd[-1] <= prev_signal[-1] and macd[-1] > signal[-1]
        crossed_down = prev_macd[-1] >= prev_signal[-1] and macd[-1] < signal[-1]
        if bar.symbol not in self.in_position and crossed_up:
            return self._order(bar.symbol, True)
        if bar.symbol in self.in_position and crossed_down:
            return self._order(bar.symbol, False)
        return None


class RateOfChangeStrategy(_LongOnlySignalStrategy):
    """Buy when N-bar rate of change crosses above entry; exit below exit."""

    def __init__(
        self,
        period: int = 20,
        entry_threshold: float = 0.0,
        exit_threshold: float = 0.0,
        quantity=None,
        notional=None,
        fraction=None,
    ):
        _positive_period("period", period)
        _number("entry_threshold", entry_threshold)
        _number("exit_threshold", exit_threshold)
        if exit_threshold > entry_threshold:
            raise ValueError("exit_threshold must be less than or equal to entry_threshold")
        self.period = period
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        super().__init__(quantity, notional, fraction)

    def on_bar(self, bar, history, portfolio) -> Optional[Order]:
        if len(history) < self.period + 2:
            return None
        closes = [item.close for item in history]
        current_base = closes[-self.period - 1]
        previous_base = closes[-self.period - 2]
        if current_base <= 0 or previous_base <= 0:
            return None
        current = closes[-1] / current_base - 1
        previous = closes[-2] / previous_base - 1
        crossed_up = previous <= self.entry_threshold < current
        crossed_down = previous >= self.exit_threshold > current
        if bar.symbol not in self.in_position and crossed_up:
            return self._order(bar.symbol, True)
        if bar.symbol in self.in_position and crossed_down:
            return self._order(bar.symbol, False)
        return None


class StochasticOscillatorStrategy(_LongOnlySignalStrategy):
    """Buy when %K crosses up through oversold; exit down through overbought."""

    def __init__(
        self,
        period: int = 14,
        oversold: float = 20,
        overbought: float = 80,
        quantity=None,
        notional=None,
        fraction=None,
    ):
        _positive_period("period", period)
        _number("oversold", oversold)
        _number("overbought", overbought)
        if not 0 <= oversold < overbought <= 100:
            raise ValueError("require 0 <= oversold < overbought <= 100")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        super().__init__(quantity, notional, fraction)

    def _percent_k(self, history) -> float:
        window = history[-self.period :]
        high = max(item.high for item in window)
        low = min(item.low for item in window)
        return 50.0 if high == low else 100 * (history[-1].close - low) / (high - low)

    def on_bar(self, bar, history, portfolio) -> Optional[Order]:
        if len(history) < self.period + 1:
            return None
        previous = self._percent_k(history[:-1])
        current = self._percent_k(history)
        crossed_up = previous <= self.oversold < current
        crossed_down = previous >= self.overbought > current
        if bar.symbol not in self.in_position and crossed_up:
            return self._order(bar.symbol, True)
        if bar.symbol in self.in_position and crossed_down:
            return self._order(bar.symbol, False)
        return None


class WilliamsRStrategy(_LongOnlySignalStrategy):
    """Buy when Williams %R crosses up through oversold; exit below overbought."""

    def __init__(
        self,
        period: int = 14,
        oversold: float = -80,
        overbought: float = -20,
        quantity=None,
        notional=None,
        fraction=None,
    ):
        _positive_period("period", period)
        _number("oversold", oversold)
        _number("overbought", overbought)
        if not -100 <= oversold < overbought <= 0:
            raise ValueError("require -100 <= oversold < overbought <= 0")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        super().__init__(quantity, notional, fraction)

    def _percent_r(self, history) -> float:
        window = history[-self.period :]
        high = max(item.high for item in window)
        low = min(item.low for item in window)
        return -50.0 if high == low else -100 * (high - history[-1].close) / (high - low)

    def on_bar(self, bar, history, portfolio) -> Optional[Order]:
        if len(history) < self.period + 1:
            return None
        previous = self._percent_r(history[:-1])
        current = self._percent_r(history)
        crossed_up = previous <= self.oversold < current
        crossed_down = previous >= self.overbought > current
        if bar.symbol not in self.in_position and crossed_up:
            return self._order(bar.symbol, True)
        if bar.symbol in self.in_position and crossed_down:
            return self._order(bar.symbol, False)
        return None


class CciStrategy(_LongOnlySignalStrategy):
    """Buy on a CCI cross above the negative entry level; exit above positive level."""

    def __init__(
        self,
        period: int = 20,
        entry_level: float = -100,
        exit_level: float = 100,
        quantity=None,
        notional=None,
        fraction=None,
    ):
        _positive_period("period", period)
        _number("entry_level", entry_level)
        _number("exit_level", exit_level)
        if entry_level >= exit_level:
            raise ValueError("entry_level must be less than exit_level")
        self.period = period
        self.entry_level = entry_level
        self.exit_level = exit_level
        super().__init__(quantity, notional, fraction)

    def _cci(self, history) -> float:
        typical = [(item.high + item.low + item.close) / 3 for item in history[-self.period :]]
        mean = sum(typical) / self.period
        deviation = sum(abs(value - mean) for value in typical) / self.period
        if deviation == 0:
            return 0.0
        return (typical[-1] - mean) / (0.015 * deviation)

    def on_bar(self, bar, history, portfolio) -> Optional[Order]:
        if len(history) < self.period + 1:
            return None
        previous = self._cci(history[:-1])
        current = self._cci(history)
        crossed_up = previous <= self.entry_level < current
        crossed_down = previous >= self.exit_level > current
        if bar.symbol not in self.in_position and crossed_up:
            return self._order(bar.symbol, True)
        if bar.symbol in self.in_position and crossed_down:
            return self._order(bar.symbol, False)
        return None


class KeltnerChannelStrategy(_LongOnlySignalStrategy):
    """Buy above the prior EMA/ATR upper channel; exit below the lower channel."""

    def __init__(
        self,
        period: int = 20,
        atr_period: int = 10,
        multiplier: float = 2.0,
        quantity=None,
        notional=None,
        fraction=None,
    ):
        _positive_period("period", period)
        _positive_period("atr_period", atr_period)
        _number("multiplier", multiplier, positive=True)
        self.period = period
        self.atr_period = atr_period
        self.multiplier = multiplier
        super().__init__(quantity, notional, fraction)

    def _channel(self, history) -> tuple[float, float]:
        center = _ema([item.close for item in history], self.period)[-1]
        atr_values = _true_ranges(history)[-self.atr_period :]
        atr = sum(atr_values) / self.atr_period
        return center - self.multiplier * atr, center + self.multiplier * atr

    def on_bar(self, bar, history, portfolio) -> Optional[Order]:
        if len(history) < max(self.period, self.atr_period) + 2:
            return None
        prior_lower, prior_upper = self._channel(history[:-1])
        lower, _ = self._channel(history)
        previous_close = history[-2].close
        close = history[-1].close
        if bar.symbol not in self.in_position and close > prior_upper:
            return self._order(bar.symbol, True)
        if bar.symbol in self.in_position and previous_close >= prior_lower and close < lower:
            return self._order(bar.symbol, False)
        return None


class AtrTrailingBreakoutStrategy(_LongOnlySignalStrategy):
    """Enter on an N-bar high breakout; exit at a highest-high minus ATR trail."""

    def __init__(
        self,
        entry_period: int = 20,
        atr_period: int = 14,
        atr_multiplier: float = 3.0,
        quantity=None,
        notional=None,
        fraction=None,
    ):
        _positive_period("entry_period", entry_period)
        _positive_period("atr_period", atr_period)
        _number("atr_multiplier", atr_multiplier, positive=True)
        self.entry_period = entry_period
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self._trailing_high: dict[str, float] = {}
        super().__init__(quantity, notional, fraction)

    def on_bar(self, bar, history, portfolio) -> Optional[Order]:
        if len(history) <= self.entry_period:
            return None
        close = history[-1].close
        if bar.symbol not in self.in_position:
            prior_high = max(item.high for item in history[-self.entry_period - 1 : -1])
            if close > prior_high:
                self._trailing_high[bar.symbol] = history[-1].high
                return self._order(bar.symbol, True)
            return None
        self._trailing_high[bar.symbol] = max(self._trailing_high[bar.symbol], history[-1].high)
        ranges = _true_ranges(history)
        if len(ranges) < self.atr_period:
            return None
        atr = sum(ranges[-self.atr_period :]) / self.atr_period
        stop = self._trailing_high[bar.symbol] - self.atr_multiplier * atr
        if close < stop:
            self._trailing_high.pop(bar.symbol)
            return self._order(bar.symbol, False)
        return None


class IchimokuCloudStrategy(_LongOnlySignalStrategy):
    """Buy above the lag-safe Ichimoku cloud with bullish conversion/base lines."""

    def __init__(
        self,
        conversion_period: int = 9,
        base_period: int = 26,
        span_b_period: int = 52,
        displacement: int = 26,
        quantity=None,
        notional=None,
        fraction=None,
    ):
        for name, value in (
            ("conversion_period", conversion_period),
            ("base_period", base_period),
            ("span_b_period", span_b_period),
            ("displacement", displacement),
        ):
            _positive_period(name, value)
        if conversion_period >= base_period or base_period >= span_b_period:
            raise ValueError("require conversion_period < base_period < span_b_period")
        self.conversion_period = conversion_period
        self.base_period = base_period
        self.span_b_period = span_b_period
        self.displacement = displacement
        super().__init__(quantity, notional, fraction)

    @staticmethod
    def _midpoint(history, period: int) -> float:
        window = history[-period:]
        return (max(item.high for item in window) + min(item.low for item in window)) / 2

    def on_bar(self, bar, history, portfolio) -> Optional[Order]:
        required = self.span_b_period + self.displacement
        if len(history) < required:
            return None
        cloud_history = history[: -self.displacement]
        conversion = self._midpoint(history, self.conversion_period)
        base = self._midpoint(history, self.base_period)
        span_a = (
            self._midpoint(cloud_history, self.conversion_period)
            + self._midpoint(cloud_history, self.base_period)
        ) / 2
        span_b = self._midpoint(cloud_history, self.span_b_period)
        cloud_top = max(span_a, span_b)
        cloud_bottom = min(span_a, span_b)
        close = history[-1].close
        if bar.symbol not in self.in_position and close > cloud_top and conversion > base:
            return self._order(bar.symbol, True)
        if bar.symbol in self.in_position and close < cloud_bottom:
            return self._order(bar.symbol, False)
        return None


class VwapMeanReversionStrategy(_LongOnlySignalStrategy):
    """Buy below rolling volume-weighted price bands; exit on recovery to VWAP."""

    def __init__(
        self,
        period: int = 20,
        num_std: float = 1.5,
        quantity=None,
        notional=None,
        fraction=None,
    ):
        _positive_period("period", period, minimum=2)
        _number("num_std", num_std, positive=True)
        self.period = period
        self.num_std = num_std
        super().__init__(quantity, notional, fraction)

    def _bands(self, history) -> tuple[float, float]:
        window = history[-self.period :]
        typical = [(item.high + item.low + item.close) / 3 for item in window]
        volume = [item.volume for item in window]
        volume_sum = sum(volume)
        if volume_sum <= 0:
            return 0.0, 0.0
        vwap = sum(price * amount for price, amount in zip(typical, volume)) / volume_sum
        variance = (
            sum(amount * (price - vwap) ** 2 for price, amount in zip(typical, volume)) / volume_sum
        )
        return vwap - self.num_std * variance**0.5, vwap

    def on_bar(self, bar, history, portfolio) -> Optional[Order]:
        if len(history) < self.period + 1:
            return None
        _, prior_vwap = self._bands(history[:-1])
        lower, vwap = self._bands(history)
        if lower == 0.0 or vwap == 0.0:
            return None
        close = history[-1].close
        if bar.symbol not in self.in_position and close < lower:
            return self._order(bar.symbol, True)
        if bar.symbol in self.in_position and history[-2].close <= prior_vwap < close:
            return self._order(bar.symbol, False)
        return None
