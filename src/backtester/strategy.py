# strategy.py
from abc import ABC, abstractmethod
from typing import Any, NamedTuple, Optional, TypedDict

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
            raise ValueError(f"fast_period ({fast_period}) must be less than slow_period ({slow_period})")

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
