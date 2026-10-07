# engine.py
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List

from backtester.portfolio import Portfolio

if TYPE_CHECKING:
    from backtester.datafeed import Bar


class BacktestEngine:
    def __init__(
        self, feed: Any, strategy: Any, starting_cash: float,
        commission: float = 0.0, slippage_bps: float = 0.0,
        allow_shorts: bool = False,
    ):
        self.feed = feed
        self.strategy = strategy
        self.portfolio = Portfolio(
            starting_cash, commission=commission,
            slippage_bps=slippage_bps, allow_shorts=allow_shorts,
        )

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

    @staticmethod
    def _trigger_price(order, bar) -> float | str | None:
        """Fill price if the order triggers on this bar, else None.

        Market fills at the open. Limits rest until touched and fill at
        the trigger or better (open gaps through are honored). Stops
        trigger on touch and fill at the open if it gapped through.
        """
        kind = order.get("order_type", "market")
        qty = order["quantity"]
        if kind == "market":
            return bar.open
        if kind not in ("limit", "stop"):
            return "reject"
        trigger = order.get("price")
        if not isinstance(trigger, (int, float)) or isinstance(trigger, bool):
            return "reject"
        if kind == "limit":
            if qty > 0:
                return min(bar.open, trigger) if bar.low <= trigger else None
            return max(bar.open, trigger) if bar.high >= trigger else None
        if qty > 0:
            return max(bar.open, trigger) if bar.high >= trigger else None
        return min(bar.open, trigger) if bar.low <= trigger else None

    def _fill_pending_orders(self, current_bar: "Bar") -> None:
        remaining_orders = []
        for order in self.pending_orders:
            if order["symbol"] != current_bar.symbol:
                # Keep orders for other symbols until their bar arrives
                remaining_orders.append(order)
                continue
            fill = self._trigger_price(order, current_bar)
            if isinstance(fill, str):
                self.n_rejected += 1
                continue
            if fill is None:
                # resting limit/stop, not touched yet
                remaining_orders.append(order)
                continue
            ok = self.portfolio.execute_order(
                timestamp=current_bar.timestamp,
                symbol=order["symbol"],
                quantity=order["quantity"],
                fill_price=fill,
            )
            if ok:
                self.n_fills += 1
            else:
                self.n_rejected += 1
        self.pending_orders = remaining_orders
