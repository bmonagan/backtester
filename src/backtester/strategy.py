# strategy.py
from abc import ABC, abstractmethod
from typing import NamedTuple, TypedDict

class Order(TypedDict):
    symbol: str
    action: str
    quantity: float

class BarResult(NamedTuple):
    order: Order | None
    last_fast: float | None
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
    def on_bar(self, bar, history, portfolio, last_fast, last_slow) -> BarResult:
        fast_period = self.params["fast_window"]
        slow_period = self.params["slow_window"]
        quantity = self.params["quantity"]
        if not (fast_period and slow_period and quantity):
            raise ValueError("Must include both fast/slow window parameters and the quantity parameter.")
        
        if len(history) < slow:
            return None
        fast_ma = sum(b.close for b in history[-fast_period:]) / fast_period
        slow_ma = sum(b.close for b in history[-slow_period:]) / slow_period
        
        if (not last_fast and not last_slow):
            return BarResult(None, fast_ma, slow_ma)
        # Golden Cross (Bullish)
        if (fast_ma > slow_ma and last_fast <= last_slow):
            order = Order(bar.symbol, "buy", quantity_param)
            return BarResult(order, fast_ma, slow_ma)


        # Death Cross (Bearish)
        if (

