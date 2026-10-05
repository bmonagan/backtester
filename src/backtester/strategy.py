# strategy.py
from abc import ABC, abstractmethod
from typing import NamedTuple, TypedDict

class Order(TypedDict):
    symbol: str
    action: str
    quantity: float
    last_slow: float | None

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
    def __init__(self):
        self.last_fast = None
        self.last_slow = None
    def on_bar(self, bar, history, portfolio) -> BarResult:
        fast_period = self.params["fast_window"]
        slow_period = self.params["slow_window"]
        quantity = self.params["quantity"]
        if not (fast_period and slow_period and quantity):
            raise ValueError("Must include both fast/slow window parameters and the quantity parameter.")

        validate_periods(fast_period=fast_period, slow_period=slow_period)
        # Check to see if enough data for both SMAS
        if len(history) < slow_period:
            return None
        
        fast_ma = sum(b.close for b in history[-fast_period:]) / fast_period
        slow_ma = sum(b.close for b in history[-slow_period:]) / slow_period
        
        if (not last_fast and not last_slow):
            return BarResult(None, fast_ma, slow_ma)
        # Golden Cross (Bullish)
        if ((fast_ma > slow_ma) and (last_fast <= last_slow)):
            #order = Order(bar.symbol, "buy", quantity)
            order = Order(symbol="AAPL", action="buy", quantity=quantity)
            return BarResult(order, fast_ma, slow_ma)
        # Death Cross (Bearish)
        if ((fast_ma < slow_ma) and (last_fast >= last_slow)):
            #order = Order(bar.symbol, "sell", quantity)
            order = Order(symbol="AAPL", action="sell", quantity=-quantity)
            return BarResult(order,fast_ma, slow_ma)

        return BarResult(None, fast_ma, slow_ma)




def validate_periods(fast_period: int, slow_period: int) -> None:
    # 1. Ensure both are strictly integers (bool is a subclass of int in Python, so exclude it)
    if not isinstance(fast_period, int) or isinstance(fast_period, bool):
        raise TypeError(f"fast_period must be an int, got {type(fast_period).__name__}")
    if not isinstance(slow_period, int) or isinstance(slow_period, bool):
        raise TypeError(f"slow_period must be an int, got {type(slow_period).__name__}")

    # 2. Check for positive non-zero periods (standard for moving averages)
    if fast_period <= 0:
        raise ValueError(f"fast_period must be positive, got {fast_period}")
    if slow_period <= 0:
        raise ValueError(f"slow_period must be positive, got {slow_period}")

    # 3. Ensure fast is strictly smaller than slow
    if fast_period >= slow_period:
        raise ValueError(
            f"fast_period ({fast_period}) must be strictly less than slow_period ({slow_period})"
        )
