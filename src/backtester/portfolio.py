# portfolio.py
from dataclasses import dataclass, field
from datafeed import Bar

@dataclass
class Position:
    symbol: str
    quantity: float = 0.0
    avg_price: float = 0.0

    def __repr__(self):
        return f"Position(symbol='{self.symbol}', quantity={self.quantity}, avg_price={self.avg_price:.2f})"

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
        """Record current equity given latest prices per symbol."""
        positions_value = 0.0
        total_cost_basis = 0.0

        for ticker, pos in self.positions.items():
            if pos.quantity == 0:
                continue
            if ticker not in prices or prices[ticker] is None:
                raise KeyError(f"Missing price for active position in {ticker} at {timestamp}")
            price = prices[ticker]

            positions_value += pos.quantity * price
            total_cost_basis += pos.quantity * self.positions[ticker].avg_price

        
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

            

    def execute_order(self, timestamp, symbol: str, quantity: float, fill_price: float) -> bool:
        """Update cash/positions, append to trade_log."""
        if quantity == 0:
            return False

        trade_cost = quantity * fill_price

        # 1. Buying
        if quantity > 0:
            if trade_cost > self.cash:
                #print(f"[{timestamp}] Insufficient funds for {quantity} {symbol} @ {fill_price}")
                return False

            self.cash -= trade_cost

            if symbol not in self.positions:
                self.positions[symbol] = Position(symbol=symbol, quantity=quantity, avg_price=fill_price)
            else:
                pos = self.positions[symbol]
                new_qty = pos.quantity + quantity
                total_basis = (pos.quantity * pos.avg_price) + trade_cost
                self.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=new_qty,
                    avg_price=total_basis / new_qty
                )

        # 2. Selling
        else:
            sell_qty = abs(quantity)
            current_pos = self.positions.get(symbol)

            if not current_pos or current_pos.quantity < sell_qty:
                #print(f"[{timestamp}] Cannot sell {sell_qty} {symbol}: insufficient holdings.")
                return False

            self.cash += sell_qty * fill_price
            remaining_qty = current_pos.quantity - sell_qty

            if remaining_qty == 0:
                del self.positions[symbol]
            else:
                # Average cost basis remains unchanged on partial sales
                self.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=remaining_qty,
                    avg_price=current_pos.avg_price
                )

        # 3. Log trade execution
        self.trade_log.append({
            "timestamp": timestamp,
            "symbol": symbol,
            "quantity": quantity,
            "fill_price": fill_price,
            "cash_balance": self.cash,
        })
        return True


    def current_equity(self, prices: dict[str, float]) -> float:
        total_equity = 0.0
        for symb,pos in self.positions.items():
            pos_val = prices[symb] * pos.quantity
            total_equity += pos_val

        return total_equity


    def __str__(self):
        return f"Portfolio: Cash: {self.cash:.2f} Positions: {self.positions}"
