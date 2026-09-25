# portfolio.py
from dataclasses import dataclass, field

@dataclass
class Position:
    symbol: str
    quantity: float = 0.0
    avg_price: float = 0.0

class Portfolio:
    def __init__(self, starting_cash: float):
        self.cash = starting_cash
        self.positions: dict[str, Position] = {}
        self.equity_curve: list[tuple] = []  # (timestamp, equity)
        self.trade_log: list[dict] = []

    def mark_to_market(self, timestamp, prices: dict[str, float]):
        """Record current equity given latest prices."""
        ...

    def execute_order(self, timestamp, symbol, quantity, fill_price):
        """Update cash/positions, append to trade_log."""
        ...

    def current_equity(self, prices: dict[str, float]) -> float:
        ...
