# engine.py
from collections import defaultdict
from typing import Dict, List, Optional
from portfolio import Portfolio


class BacktestEngine:
    def __init__(self, feed: "DataFeed", strategy: "Strategy", starting_cash: float):
        self.feed = feed
        self.strategy = strategy
        self.portfolio = Portfolio(starting_cash)
        
        # History segregated per symbol for clean multi-asset support
        self.history: Dict[str, List["Bar"]] = defaultdict(list)
        self.latest_prices: Dict[str, float] = {}
        self.pending_orders: List[dict] = []

    def run(self) -> Portfolio:
        for bar in self.feed:
            # 1. Execute orders queued from previous bar at current bar's Open
            self._fill_pending_orders(bar)

            # 2. Update price references and symbol history
            self.history[bar.symbol].append(bar)
            self.latest_prices[bar.symbol] = bar.close

            # 3. Mark portfolio to market with current prices
            self.portfolio.mark_to_market(bar.timestamp, self.latest_prices)

            # 4. Generate orders for next bar (strategy manages its own internal state)
            order = self.strategy.on_bar(
                bar=bar,
                history=self.history[bar.symbol],
                portfolio=self.portfolio
            )
            
            if order:
                self.pending_orders.append(order)

        return self.portfolio

    def _fill_pending_orders(self, current_bar: "Bar") -> None:
        remaining_orders = []
        for order in self.pending_orders:
            if order["symbol"] == current_bar.symbol:
                # Fills at current open price without needing peek_next
                self.portfolio.execute_order(
                    timestamp=current_bar.timestamp,
                    symbol=order["symbol"],
                    quantity=order["quantity"],
                    price=current_bar.open,
                )
            else:
                # Keep orders for other symbols active until their bar arrives
                remaining_orders.append(order)
        self.pending_orders = remaining_orders
