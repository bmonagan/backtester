# portfolio.py
from dataclasses import dataclass, field

@dataclass
class Position:
    symbol: str
    quantity: float = 0.0
    avg_price: float = 0.0

@dataclass
class PortfolioSnapshot:
    timestamp: object
    cash: float
    holdings_value: float
    total_equity: float
    unrealized_pnl: float

class Portfolio:
    def __init__(self, starting_cash: float):
        self.cash = starting_cash
        self.positions: dict[str, Position] = {}
        self.equity_curve: list[tuple] = []  # (timestamp, equity)
        self.trade_log: list[dict] = []
        self.history: list[PortfolioSnapshot] = []

    def mark_to_market(self, timestamp, prices: dict[str, float]):
        """Record current equity given latest prices."""
        positions_value = 0.0
        total_cost_basis = 0.0

        for ticker,qty in self.positions.items():
            if qty == 0:
                continue  
            price = prices.get(ticker)
            if price is None:
                raise KeyError(f"Missing price for active position in {ticker} at {timestamp}")

            positions_value += qty * price
            total_cost_basis += qty * self.positions.avg_price
        
        unrealized_pnl = positions_value - total_cost_basis
        total_equity = self.cash + positions_value

        snapshot = PortfolioSnapshot(
            timestamp=timestamp,
            cash=self.cash,
            holdings_value= positions_value,
            total_equity=total_equity,
            unrealized_pnl=unrealized_pnl
        )
        self.history.append(snapshot)
        return snapshot

            

    def execute_order(self, timestamp, symbol, quantity, fill_price):
        """Update cash/positions, append to trade_log."""
        purchase_amount = quantity * fill_price
        if purchase_amount > self.cash:
            print("Not enough cash to make this purchase")
            return
        self.cash -= purchase_amount
        order_position = Position(symbol= symbol, quantity = quantity, avg_price = fill_price)
        if symbol not in self.positions.keys():
            self.positions[symbol] = order_position
        else:
            old_position = self.positions[symbol]
            new_quantity = quantity + old_position.quantity
            new_position_value = (old_position.quantity ^ old_position.avg_price + quantity * fill_price)
            new_avg_price = new_position_value / new_quantity
            self.positions[symbol] = Position(symbol=symbol, quantity= new_quantity, avg_price= new_avg_price)



    def current_equity(self, prices: dict[str, float]) -> float:
        ...

    def __str__(self):
        return f"Portfolio: Cash: {self.cash} Positions: {self.positions}"
