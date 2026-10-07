# engine.py
import math
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
    def _direction(order) -> int | None:
        """+1 for buys, -1 for sells, None when undeterminable."""
        qty = order.get("quantity")
        if qty is not None:
            if isinstance(qty, bool) or not isinstance(qty, (int, float)):
                return None
            if qty != 0:
                return 1 if qty > 0 else -1
        notional = order.get("notional")
        if notional is not None:
            if isinstance(notional, bool) or not isinstance(notional, (int, float)):
                return None
            if notional != 0:
                return 1 if notional > 0 else -1
        action = order.get("action")
        if action == "buy":
            return 1
        if action == "sell":
            return -1
        return None

    @staticmethod
    def _trigger_price(order, bar) -> float | str | None:
        """Fill price if the order triggers on this bar, else None.

        Market fills at the open. Limits rest until touched and fill at
        the trigger or better (open gaps through are honored). Stops
        trigger on touch and fill at the open if it gapped through.
        """
        kind = order.get("order_type", "market")
        if kind == "market":
            return bar.open
        if kind not in ("limit", "stop"):
            return "reject"
        side = BacktestEngine._direction(order)
        if side is None:
            return "reject"
        trigger = order.get("price")
        if not isinstance(trigger, (int, float)) or isinstance(trigger, bool):
            return "reject"
        if kind == "limit":
            if side > 0:
                return min(bar.open, trigger) if bar.low <= trigger else None
            return max(bar.open, trigger) if bar.high >= trigger else None
        if side > 0:
            return max(bar.open, trigger) if bar.high >= trigger else None
        return min(bar.open, trigger) if bar.low <= trigger else None

    @staticmethod
    def _resolve_shares(
        order, fill_price: float, equity: float, position_qty: float,
    ) -> float | str:
        """Turn an order's magnitude into signed share count.

        Exactly one of quantity / notional / fraction must be set.
        notional is signed dollars, fraction sizes buys off live equity
        and sells off current position value. Dust (under one share)
        returns "reject".
        """
        qty = order.get("quantity")
        notional = order.get("notional")
        fraction = order.get("fraction")
        modes = sum(v is not None for v in (qty, notional, fraction))
        if modes != 1:
            return "reject"
        if qty is not None:
            if isinstance(qty, bool) or not isinstance(qty, (int, float)):
                return "reject"
            return float(qty)
        if not isinstance(fill_price, (int, float)) or fill_price <= 0:
            return "reject"
        if notional is not None:
            if isinstance(notional, bool) or not isinstance(notional, (int, float)):
                return "reject"
            shares = math.trunc(notional / fill_price)
            return float(shares) if shares != 0 else "reject"
        if isinstance(fraction, bool) or not isinstance(fraction, (int, float)):
            return "reject"
        if not 0 < fraction <= 1:
            return "reject"
        action = order.get("action")
        if action == "buy":
            base = equity
        elif action == "sell":
            base = abs(position_qty) * fill_price
        else:
            return "reject"
        if base <= 0:
            return "reject"
        sign = 1 if action == "buy" else -1
        shares = math.trunc(sign * fraction * base / fill_price)
        return float(shares) if shares != 0 else "reject"

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
            try:
                equity = self.portfolio.current_equity(self.latest_prices)
            except KeyError:
                equity = self.portfolio.cash
            held = self.portfolio.positions.get(order["symbol"])
            position_qty = held.quantity if held else 0.0
            shares = self._resolve_shares(order, fill, equity, position_qty)
            if isinstance(shares, str):
                self.n_rejected += 1
                continue
            ok = self.portfolio.execute_order(
                timestamp=current_bar.timestamp,
                symbol=order["symbol"],
                quantity=shares,
                fill_price=fill,
            )
            if ok:
                self.n_fills += 1
            else:
                self.n_rejected += 1
        self.pending_orders = remaining_orders
