# strategy.py
from abc import ABC, abstractmethod
from typing import NamedTuple, TypedDict

class Order(TypedDict):
    symbol: str
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
    def on_bar(self, bar, history, portfolio, last_fast, last_slow) -> Dict, Float, Float:
        fast_period = self.params["fast_window"]
        slow_period = self.params["slow_window"]
        if len(history) < slow:
            return None
        fast_ma = sum(b.close for b in history[-fast_period:]) / fast_period
        slow_ma = sum(b.close for b in history[-slow_period:]) / slow_period
        
        if (not last_fast and not last_slow):
        return None, 
        # Golden Cross (Bullish)
        if (fast_ma > slow_ma and )

        # Death Cross (Bearish)
        if (

