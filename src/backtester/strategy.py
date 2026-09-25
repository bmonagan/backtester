# strategy.py
from abc import ABC, abstractmethod

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
    def on_bar(self, bar, history, portfolio):
        fast = self.params["fast_window"]
        slow = self.params["slow_window"]
        if len(history) < slow:
            return None
        fast_ma = sum(b.close for b in history[-fast:]) / fast
        slow_ma = sum(b.close for b in history[-slow:]) / slow
        # crossover logic → return buy/sell/None
        ...
