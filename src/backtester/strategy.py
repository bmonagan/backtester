# strategy.py
from abc import ABC, abstractmethod
from typing import NamedTuple, TypedDict

class Order(TypedDict):
    symbol: str
    action: str
    quantity: float

class Strategy(ABC):
    def __init__(self, **params):
        self.params = params

    @abstractmethod
    def on_bar(self, bar, history: list, portfolio: Portfolio) -> Optional[dict]:
        """
        Called once per bar. Return an order dict like
        {"symbol": ..., "action": "buy"/"sell", "quantity": ...}
        or None to do nothing. `history` gives access to prior bars
        for computing indicators. 
        """
        ...

class SmaCrossoverStrategy(Strategy):
    def __init__(self, fast_period: int = 10, slow_period: int = 30, quantity: int = 100):
        # 1. Validation checks
        if not isinstance(fast_period, int) or isinstance(fast_period, bool):
            raise TypeError("fast_period must be an integer")
        if not isinstance(slow_period, int) or isinstance(slow_period, bool):
            raise TypeError("slow_period must be an integer")
        if fast_period <= 0 or slow_period <= 0:
            raise ValueError("Periods must be greater than 0")
        if fast_period >= slow_period:
            raise ValueError(f"fast_period ({fast_period}) must be less than slow_period ({slow_period})")

        # 2. Let the parent class store params
        super().__init__(fast_period=fast_period, slow_period=slow_period, **params)

        # 3. Strategy-specific state
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.quantity    = quantity
        self.last_fast   = None
        self.last_slow   = None

    def on_bar(self, bar, history, portfolio) -> Order | None: 
        # Check to see if enough data for both SMAS
        if len(history) < slow_period:
            return None
        
        fast_ma = sum(b.close for b in history[-self.fast_period:]) / self.fast_period
        slow_ma = sum(b.close for b in history[-self.slow_period:]) / self.slow_period
        
        if (not self.last_fast and not self.last_slow):
            self.last_fast = fast_ma
            self.last_slow = slow_ma
            return None
        
        # Golden Cross (Bullish)
        if ((fast_ma > slow_ma) and (self.last_fast <= self.last_slow)):
            order = Order(symbol=bar.symbol, action="buy", quantity=self.quantity)
            return order

        # Death Cross (Bearish)
        if ((fast_ma < slow_ma) and (self.last_fast >= self.last_slow)):
            order = Order(symbol=bar.symbol, action="sell", quantity=-self.quantity)
            return order

        return None
