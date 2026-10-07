# strategy.py
from abc import ABC, abstractmethod
from typing import Any, Literal, NotRequired, Optional, TypedDict, cast


class Order(TypedDict):
    symbol: str
    action: str
    # Exactly one magnitude key must be set. quantity is share count
    # (legacy default), notional is signed dollars, fraction sizes off
    # live equity (buys) or current position value (sells).
    quantity: NotRequired[float | None]
    notional: NotRequired[float | None]
    fraction: NotRequired[float | None]
    order_type: NotRequired[Literal["market", "limit", "stop"]]
    price: NotRequired[float | None]


def _validate_sizing(quantity=None, notional=None, fraction=None) -> dict:
    """Exactly one magnitude; unset means the legacy 100-share default."""
    given = [
        k for k, v in
        (("quantity", quantity), ("notional", notional), ("fraction", fraction))
        if v is not None
    ]
    if len(given) > 1:
        raise ValueError(
            f"only one of quantity, notional, fraction may be set, got {given}"
        )
    if notional is not None:
        if isinstance(notional, bool) or not isinstance(notional, (int, float)):
            raise TypeError("notional must be a number")
        if notional <= 0:
            raise ValueError("notional must be greater than 0")
        return {"notional": notional}
    if fraction is not None:
        if isinstance(fraction, bool) or not isinstance(fraction, (int, float)):
            raise TypeError("fraction must be a number")
        if not 0 < fraction <= 1:
            raise ValueError("fraction must be in (0, 1]")
        return {"fraction": fraction}
    q = 100 if quantity is None else quantity
    if isinstance(q, bool) or not isinstance(q, (int, float)):
        raise TypeError("quantity must be a number")
    if q <= 0:
        raise ValueError("quantity must be greater than 0")
    return {"quantity": q}


def _sized_order(sizing: dict, symbol: str, action: str) -> Order:
    if "quantity" in sizing:
        q = sizing["quantity"]
        return Order(symbol=symbol, action=action, quantity=q if action == "buy" else -q)
    if "notional" in sizing:
        n = sizing["notional"]
        return Order(symbol=symbol, action=action, notional=n if action == "buy" else -n)
    return Order(symbol=symbol, action=action, fraction=sizing["fraction"])

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


class OrderTypeOverride(Strategy):
    """Wrap any strategy and stamp one order type + resting price onto its
    orders. Applies a single price to every order, so it demos limit/stop
    mechanics rather than per-order risk logic."""

    def __init__(self, inner: Strategy, order_type: str, price=None):
        if order_type not in ("market", "limit", "stop"):
            raise ValueError("order_type must be market, limit or stop")
        if order_type in ("limit", "stop"):
            if isinstance(price, bool) or not isinstance(price, (int, float)):
                raise TypeError("price must be a number for limit/stop orders")
            if price <= 0:
                raise ValueError("price must be greater than 0")
        self.inner = inner
        self.order_type: Literal["market", "limit", "stop"] = cast(
            Literal["market", "limit", "stop"], order_type
        )
        self.price = price

    def on_bar(self, bar, history, portfolio) -> Optional[Order]:
        order = self.inner.on_bar(bar, history, portfolio)
        if order is None:
            return None
        stamped = cast(Order, dict(order))
        stamped["order_type"] = self.order_type
        if self.order_type == "market":
            stamped.pop("price", None)
        else:
            stamped["price"] = self.price
        return stamped

class SmaCrossoverStrategy(Strategy):
    def __init__(
        self, fast_period: int = 10, slow_period: int = 30,
        quantity=None, notional=None, fraction=None,
    ):
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

        # Strategy-specific state
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.sizing = _validate_sizing(quantity, notional, fraction)
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
            return _sized_order(self.sizing, bar.symbol, "buy")

        if is_death:
            return _sized_order(self.sizing, bar.symbol, "sell")

        return None


class BuyAndHoldStrategy(Strategy):
    def __init__(self, quantity=None, notional=None, fraction=None):
        self.sizing = _validate_sizing(quantity, notional, fraction)
        self.bought: set[str] = set()

    def on_bar(self, bar, history, portfolio) -> Optional[Order]:
        if bar.symbol in self.bought:
            return None
        self.bought.add(bar.symbol)
        return _sized_order(self.sizing, bar.symbol, "buy")


class RsiMomentumStrategy(Strategy):
    """Wilder's RSI crossover. Buy when RSI crosses up through oversold,
    sell when it crosses down through overbought. Long-only."""

    def __init__(
        self, period: int = 14, oversold: float = 30,
        overbought: float = 70, quantity=None, notional=None,
        fraction=None,
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
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.sizing = _validate_sizing(quantity, notional, fraction)
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
            return _sized_order(self.sizing, bar.symbol, "buy")
        if prev >= self.overbought > rsi:
            return _sized_order(self.sizing, bar.symbol, "sell")
        return None


class BollingerMeanReversionStrategy(Strategy):
    """Buy when close crosses below the lower band, sell the position
    when close crosses above the upper band. Long-only, one position
    per symbol at a time."""

    def __init__(
        self, period: int = 20, num_std: float = 2.0, quantity=None,
        notional=None, fraction=None,
    ):
        if isinstance(period, bool) or not isinstance(period, int):
            raise TypeError("period must be an integer")
        if period < 2:
            raise ValueError("period must be at least 2")
        if isinstance(num_std, bool) or not isinstance(num_std, (int, float)):
            raise TypeError("num_std must be a number")
        if num_std <= 0:
            raise ValueError("num_std must be greater than 0")
        self.period = period
        self.num_std = num_std
        self.sizing = _validate_sizing(quantity, notional, fraction)
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
                return _sized_order(self.sizing, bar.symbol, "buy")
            return None

        if prev_close <= prev_upper and close > upper:
            self.in_position.discard(bar.symbol)
            return _sized_order(self.sizing, bar.symbol, "sell")
        return None


class DonchianBreakoutStrategy(Strategy):
    """Buy on close above the prior entry_period highest high,
    sell on close below the prior exit_period lowest low.
    Long-only, one position per symbol at a time."""

    def __init__(
        self, entry_period: int = 20, exit_period: int = 10,
        quantity=None, notional=None, fraction=None,
    ):
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
        self.entry_period = entry_period
        self.exit_period = exit_period
        self.sizing = _validate_sizing(quantity, notional, fraction)
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
                return _sized_order(self.sizing, bar.symbol, "buy")
            return None

        if close < lowest:
            self.in_position.discard(bar.symbol)
            return _sized_order(self.sizing, bar.symbol, "sell")
        return None
