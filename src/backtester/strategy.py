# strategy.py
from abc import ABC, abstractmethod
from typing import Any, Optional, TypedDict


class Order(TypedDict):
    symbol: str
    action: str
    quantity: float

class Strategy(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def on_bar(self, bar, history: list, portfolio: Any) -> Optional[Order]:
        """
        Called once per bar. Return an order dict like
        {"symbol": ..., "action": "buy"/"sell", "quantity": ...}
        or None to do nothing. `history` gives access to prior bars
        for computing indicators.
        """
        ...

class SmaCrossoverStrategy(Strategy):
    def __init__(self, fast_period: int = 10, slow_period: int = 30, quantity: int = 100):
        # Validation checks
        if not isinstance(fast_period, int) or isinstance(fast_period, bool):
            raise TypeError("fast_period must be an integer")
        if not isinstance(slow_period, int) or isinstance(slow_period, bool):
            raise TypeError("slow_period must be an integer")
        if fast_period <= 0 or slow_period <= 0:
            raise ValueError("Periods must be greater than 0")
        if fast_period >= slow_period:
            raise ValueError(
                f"fast_period ({fast_period}) must be less than "
                f"slow_period ({slow_period})"
            )

        if isinstance(quantity, bool) or not isinstance(quantity, (int, float)):
            raise TypeError("quantity must be a number")
        if quantity <= 0:
            raise ValueError("quantity must be greater than 0")

        # Strategy-specific state
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.quantity    = quantity
        self.last_fast   = None
        self.last_slow   = None

    def on_bar(self, bar, history, portfolio) -> Optional[Order]:
        # Check to see if enough data for both SMAS
        if len(history) < self.slow_period:
            return None

        fast_ma = sum(b.close for b in history[-self.fast_period:]) / self.fast_period
        slow_ma = sum(b.close for b in history[-self.slow_period:]) / self.slow_period

        if self.last_fast is None or self.last_slow is None:
            self.last_fast = fast_ma
            self.last_slow = slow_ma
            return None

        # Golden Cross (Bullish)
        is_golden = (fast_ma > slow_ma) and (self.last_fast <= self.last_slow)
        # Death Cross (Bearish)
        is_death = (fast_ma < slow_ma) and (self.last_fast >= self.last_slow)

        # Always advance state so signals fire once per cross, not every bar
        self.last_fast = fast_ma
        self.last_slow = slow_ma

        if is_golden:
            return Order(symbol=bar.symbol, action="buy", quantity=self.quantity)

        if is_death:
            return Order(symbol=bar.symbol, action="sell", quantity=-self.quantity)

        return None


class BuyAndHoldStrategy(Strategy):
    def __init__(self, quantity: int = 100):
        if isinstance(quantity, bool) or not isinstance(quantity, (int, float)):
            raise TypeError("quantity must be a number")
        if quantity <= 0:
            raise ValueError("quantity must be greater than 0")
        self.quantity = quantity
        self.bought: set[str] = set()

    def on_bar(self, bar, history, portfolio) -> Optional[Order]:
        if bar.symbol in self.bought:
            return None
        self.bought.add(bar.symbol)
        return Order(symbol=bar.symbol, action="buy", quantity=self.quantity)


class RsiMomentumStrategy(Strategy):
    """Wilder's RSI crossover. Buy when RSI crosses up through oversold,
    sell when it crosses down through overbought. Long-only."""

    def __init__(
        self, period: int = 14, oversold: float = 30,
        overbought: float = 70, quantity: int = 100,
    ):
        if isinstance(period, bool) or not isinstance(period, int):
            raise TypeError("period must be an integer")
        if period <= 0:
            raise ValueError("period must be greater than 0")
        for name, val in (("oversold", oversold), ("overbought", overbought)):
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                raise TypeError(f"{name} must be a number")
        if not 0 < oversold < overbought < 100:
            raise ValueError("require 0 < oversold < overbought < 100")
        if isinstance(quantity, bool) or not isinstance(quantity, (int, float)):
            raise TypeError("quantity must be a number")
        if quantity <= 0:
            raise ValueError("quantity must be greater than 0")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.quantity = quantity
        self._state: dict[str, dict] = {}

    @staticmethod
    def _rsi(avg_gain: float, avg_loss: float) -> float:
        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0
        rs = avg_gain / avg_loss
        return 100.0 - 100.0 / (1.0 + rs)

    def on_bar(self, bar, history, portfolio) -> Optional[Order]:
        if len(history) < self.period + 1:
            return None
        st = self._state.get(bar.symbol)
        if st is None:
            gains, losses = [], []
            for prev, cur in zip(history[-self.period - 1:-1], history[-self.period:]):
                delta = cur.close - prev.close
                gains.append(max(delta, 0.0))
                losses.append(max(-delta, 0.0))
            avg_gain = sum(gains) / self.period
            avg_loss = sum(losses) / self.period
            self._state[bar.symbol] = {
                "avg_gain": avg_gain,
                "avg_loss": avg_loss,
                "prev_rsi": self._rsi(avg_gain, avg_loss),
            }
            return None

        delta = history[-1].close - history[-2].close
        st["avg_gain"] = (st["avg_gain"] * (self.period - 1) + max(delta, 0.0)) / self.period
        st["avg_loss"] = (st["avg_loss"] * (self.period - 1) + max(-delta, 0.0)) / self.period
        rsi = self._rsi(st["avg_gain"], st["avg_loss"])
        prev = st["prev_rsi"]
        st["prev_rsi"] = rsi

        if prev <= self.oversold < rsi:
            return Order(symbol=bar.symbol, action="buy", quantity=self.quantity)
        if prev >= self.overbought > rsi:
            return Order(symbol=bar.symbol, action="sell", quantity=-self.quantity)
        return None


class BollingerMeanReversionStrategy(Strategy):
    """Buy when close crosses below the lower band, sell the position
    when close crosses above the upper band. Long-only, one position
    per symbol at a time."""

    def __init__(self, period: int = 20, num_std: float = 2.0, quantity: int = 100):
        if isinstance(period, bool) or not isinstance(period, int):
            raise TypeError("period must be an integer")
        if period < 2:
            raise ValueError("period must be at least 2")
        if isinstance(num_std, bool) or not isinstance(num_std, (int, float)):
            raise TypeError("num_std must be a number")
        if num_std <= 0:
            raise ValueError("num_std must be greater than 0")
        if isinstance(quantity, bool) or not isinstance(quantity, (int, float)):
            raise TypeError("quantity must be a number")
        if quantity <= 0:
            raise ValueError("quantity must be greater than 0")
        self.period = period
        self.num_std = num_std
        self.quantity = quantity
        self.in_position: set[str] = set()

    def _bands(self, history) -> tuple[float, float]:
        closes = [b.close for b in history[-self.period:]]
        mean = sum(closes) / self.period
        var = sum((c - mean) ** 2 for c in closes) / self.period
        width = self.num_std * (var ** 0.5)
        return mean - width, mean + width

    def on_bar(self, bar, history, portfolio) -> Optional[Order]:
        if len(history) < self.period + 1:
            return None
        prev_lower, prev_upper = self._bands(history[:-1])
        lower, upper = self._bands(history)
        prev_close = history[-2].close
        close = history[-1].close

        if bar.symbol not in self.in_position:
            if prev_close >= prev_lower and close < lower:
                self.in_position.add(bar.symbol)
                return Order(symbol=bar.symbol, action="buy", quantity=self.quantity)
            return None

        if prev_close <= prev_upper and close > upper:
            self.in_position.discard(bar.symbol)
            return Order(symbol=bar.symbol, action="sell", quantity=-self.quantity)
        return None


class DonchianBreakoutStrategy(Strategy):
    """Buy on close above the prior entry_period highest high,
    sell on close below the prior exit_period lowest low.
    Long-only, one position per symbol at a time."""

    def __init__(self, entry_period: int = 20, exit_period: int = 10, quantity: int = 100):
        for name, val in (("entry_period", entry_period), ("exit_period", exit_period)):
            if isinstance(val, bool) or not isinstance(val, int):
                raise TypeError(f"{name} must be an integer")
        if entry_period <= 0 or exit_period <= 0:
            raise ValueError("periods must be greater than 0")
        if exit_period >= entry_period:
            raise ValueError(
                f"exit_period ({exit_period}) must be less than "
                f"entry_period ({entry_period})"
            )
        if isinstance(quantity, bool) or not isinstance(quantity, (int, float)):
            raise TypeError("quantity must be a number")
        if quantity <= 0:
            raise ValueError("quantity must be greater than 0")
        self.entry_period = entry_period
        self.exit_period = exit_period
        self.quantity = quantity
        self.in_position: set[str] = set()

    def on_bar(self, bar, history, portfolio) -> Optional[Order]:
        if len(history) <= self.entry_period:
            return None
        # prior windows exclude the current bar to avoid lookahead
        prior = history[:-1]
        highest = max(b.high for b in prior[-self.entry_period:])
        lowest = min(b.low for b in prior[-self.exit_period:])
        close = history[-1].close

        if bar.symbol not in self.in_position:
            if close > highest:
                self.in_position.add(bar.symbol)
                return Order(symbol=bar.symbol, action="buy", quantity=self.quantity)
            return None

        if close < lowest:
            self.in_position.discard(bar.symbol)
            return Order(symbol=bar.symbol, action="sell", quantity=-self.quantity)
        return None
