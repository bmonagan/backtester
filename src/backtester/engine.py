# engine.py
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from backtester.portfolio import Portfolio

if TYPE_CHECKING:
    from backtester.datafeed import Bar, DataFeed
    from backtester.strategy import Strategy


class BacktestEngine:
    def __init__(self, feed: Any, strategy: Any, starting_cash: float, commission: float = 0.0, slippage_bps: float = 0.0):
        self.feed = feed
        self.strategy = strategy
        self.portfolio = Portfolio(starting_cash, commission=commission, slippage_bps=slippage_bps)

        # History segregated per symbol for clean multi-asset support
        self.history: Dict[str, List["Bar"]] = defaultdict(list)
        self.latest_prices: Dict[str, float] = {}
        self.pending_orders: List[Any] = []
        self.n_fills: int = 0
        self.n_rejected: int = 0

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
                ok = self.portfolio.execute_order(
                    timestamp=current_bar.timestamp,
                    symbol=order["symbol"],
                    quantity=order["quantity"],
                    fill_price=current_bar.open,
                )
                if ok:
                    self.n_fills += 1
                else:
                    self.n_rejected += 1
            else:
                # Keep orders for other symbols active until their bar arrives
                remaining_orders.append(order)
        self.pending_orders = remaining_orders
