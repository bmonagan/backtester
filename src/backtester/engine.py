# engine.py
import math
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List, Literal

from backtester.instruments import ExecutionCostModel, InstrumentSpec
from backtester.portfolio import Portfolio
from backtester.strategy import OrderUpdate

if TYPE_CHECKING:
    from backtester.datafeed import Bar


class BacktestEngine:
    def __init__(
        self, feed: Any, strategy: Any, starting_cash: float,
        commission: float = 0.0, slippage_bps: float = 0.0,
        allow_shorts: bool = False,
        instrument_specs: dict[str, InstrumentSpec] | None = None,
        strict_instruments: bool = False,
        max_gross_leverage: float | None = None,
        execution_models: dict[str, ExecutionCostModel] | None = None,
        trade_start: object | None = None,
    ):
        self.feed = feed
        self.strategy = strategy
        self.portfolio = Portfolio(
            starting_cash, commission=commission,
            slippage_bps=slippage_bps, allow_shorts=allow_shorts,
            instrument_specs=instrument_specs,
            max_gross_leverage=max_gross_leverage,
        )
        self.instrument_specs = instrument_specs or {}
        self.execution_models = execution_models or {}
        self.strict_instruments = strict_instruments
        self.trade_start = trade_start

        # History segregated per symbol for clean multi-asset support
        self.history: Dict[str, List["Bar"]] = defaultdict(list)
        self.latest_prices: Dict[str, float] = {}
        self.pending_orders: List[Any] = []
        self.order_events: list[OrderUpdate] = []
        self.n_fills: int = 0
        self.n_rejected: int = 0
        self._next_order_id = 1
        self._current_timestamp: object | None = None

    def run(self) -> Portfolio:
        for bar in self.feed:
            self._current_timestamp = bar.timestamp
            if self.strict_instruments:
                spec = self.instrument_specs.get(bar.symbol)
                if spec is None:
                    raise ValueError(f"Missing instrument metadata for {bar.symbol}")
                if not spec.metadata_complete:
                    raise ValueError(f"Incomplete instrument metadata for {bar.symbol}")
            # 1. Execute orders queued from previous bar at current bar's Open
            self._fill_pending_orders(bar)

            # 2. Update price references and symbol history
            self.history[bar.symbol].append(bar)
            self.latest_prices[bar.symbol] = bar.close

            # 3. Mark portfolio to market with current prices
            self.portfolio.mark_to_market(bar.timestamp, self.latest_prices)

            # 4. Generate next-bar orders; lifecycle callbacks reconcile position state.
            order = self.strategy.on_bar(
                bar=bar,
                history=self.history[bar.symbol],
                portfolio=self.portfolio
            )

            if order and (
                self.trade_start is None or bar.timestamp >= self.trade_start
            ):
                self._queue_order(order, bar.timestamp)

        return self.portfolio

    def _notify_order_update(self, event: OrderUpdate) -> None:
        callback = getattr(self.strategy, "on_order_update", None)
        if callable(callback):
            callback(event)

    def _record_order_event(
        self,
        order: dict[str, Any],
        status: Literal[
            "pending", "partial_fill", "filled", "rejected", "cancelled", "expired"
        ],
        timestamp: object | None,
        *,
        reason: str | None = None,
        fill_price: float | None = None,
        quantity: float | None = None,
        position_quantity: float | None = None,
    ) -> OrderUpdate:
        event = {
            "order_id": order["order_id"],
            "symbol": order.get("symbol"),
            "action": order.get("action"),
            "status": status,
            "timestamp": timestamp,
            "reason": reason,
            "fill_price": fill_price,
            "quantity": quantity,
            "position_quantity": position_quantity,
        }
        self.order_events.append(event)
        self._notify_order_update(event)
        return event

    def _queue_order(self, order: Any, timestamp: object) -> None:
        order_id = self._next_order_id
        self._next_order_id += 1
        if (
            not isinstance(order, dict)
            or not isinstance(order.get("symbol"), str)
            or not order["symbol"].strip()
            or order.get("action") not in ("buy", "sell")
        ):
            malformed = {
                "order_id": order_id,
                "symbol": order.get("symbol") if isinstance(order, dict) else None,
                "action": order.get("action") if isinstance(order, dict) else None,
            }
            self.n_rejected += 1
            self._record_order_event(
                malformed, "rejected", timestamp, reason="malformed_order"
            )
            return
        queued = dict(order)
        queued["order_id"] = order_id
        max_wait_bars = queued.get("max_wait_bars")
        if max_wait_bars is not None and (
            isinstance(max_wait_bars, bool)
            or not isinstance(max_wait_bars, int)
            or max_wait_bars < 1
        ):
            self.n_rejected += 1
            self._record_order_event(
                queued, "rejected", timestamp, reason="invalid_expiration"
            )
            return
        queued["_bars_waited"] = 0
        if any(item.get("symbol") == queued["symbol"] for item in self.pending_orders):
            self.n_rejected += 1
            self._record_order_event(
                queued, "rejected", timestamp, reason="duplicate_pending_order"
            )
            return
        self.pending_orders.append(queued)
        self._record_order_event(queued, "pending", timestamp)

    def cancel_order(self, order_id: int) -> bool:
        for index, order in enumerate(self.pending_orders):
            if order["order_id"] == order_id:
                self.pending_orders.pop(index)
                self._record_order_event(
                    order,
                    "cancelled",
                    self._current_timestamp,
                    reason="user_cancelled",
                    position_quantity=self._position_quantity(order["symbol"]),
                )
                return True
        return False

    def _position_quantity(self, symbol: str) -> float:
        position = self.portfolio.positions.get(symbol)
        return position.quantity if position else 0.0

    def _wait_or_expire(
        self, order: dict[str, Any], timestamp: object, remaining_orders: list[Any]
    ) -> None:
        order["_bars_waited"] += 1
        max_wait = order.get("max_wait_bars")
        if max_wait is not None and order["_bars_waited"] >= max_wait:
            self._record_order_event(
                order,
                "expired",
                timestamp,
                reason="max_wait_bars",
                position_quantity=self._position_quantity(order["symbol"]),
            )
        else:
            remaining_orders.append(order)

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
        cash: float | None = None, commission: float = 0.0,
        slippage_bps: float = 0.0,
    ) -> float | str:
        """Turn an order's magnitude into signed share count.

        Exactly one of quantity / notional / fraction must be set.
        notional is signed dollars. fraction sizes buys off live equity
        and sells off current position value; fraction buys are further
        capped by available cash so they can never over-commit. Dust
        (under one share) returns "reject".
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
        if action == "buy" and cash is not None and shares > 0:
            eff = fill_price * (1 + slippage_bps / 10000.0)
            affordable = math.floor((cash - commission) / eff)
            if affordable < shares:
                shares = affordable
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
                self._record_order_event(
                    order, "rejected", current_bar.timestamp, reason="invalid_order"
                )
                continue
            if fill is None:
                # resting limit/stop, not touched yet
                self._wait_or_expire(order, current_bar.timestamp, remaining_orders)
                continue
            try:
                equity = self.portfolio.current_equity(self.latest_prices)
            except KeyError:
                equity = self.portfolio.cash
            spec = self.instrument_specs.get(order["symbol"])
            multiplier = spec.multiplier if spec and spec.multiplier else 1.0
            held = self.portfolio.positions.get(order["symbol"])
            position_qty = held.quantity if held else 0.0
            if "quantity" in order and order.get("_resolved_quantity"):
                shares = float(order["quantity"])
            else:
                shares = self._resolve_shares(
                    order, fill * multiplier, equity, position_qty,
                    cash=self.portfolio.cash,
                    commission=self.portfolio.commission,
                    slippage_bps=self.portfolio.slippage_bps,
                )
            if isinstance(shares, str):
                self.n_rejected += 1
                self._record_order_event(
                    order, "rejected", current_bar.timestamp, reason="invalid_size"
                )
                continue

            model = self.execution_models.get(order["symbol"], ExecutionCostModel())
            requested_shares = shares
            if not order.get("_resolved_quantity"):
                order["quantity"] = shares
                order["_resolved_quantity"] = True
                order.pop("notional", None)
                order.pop("fraction", None)
            fill_quantity = self._participation_fill_quantity(
                shares,
                current_bar.volume,
                model,
                spec.quantity_increment if spec else None,
            )
            if fill_quantity == 0:
                self._wait_or_expire(order, current_bar.timestamp, remaining_orders)
                continue
            participation_rate = (
                abs(fill_quantity) / current_bar.volume
                if current_bar.volume > 0
                else 0.0
            )
            spread_bps = model.half_spread_bps * model.scenario_multiplier
            slippage_bps = (
                self.portfolio.slippage_bps
                + model.slippage_bps * model.scenario_multiplier
            )
            impact_bps = model.impact_bps(participation_rate)
            ok = self.portfolio.execute_order(
                timestamp=current_bar.timestamp,
                symbol=order["symbol"],
                quantity=fill_quantity,
                fill_price=fill,
                slippage_bps=slippage_bps,
                spread_bps=spread_bps,
                impact_bps=impact_bps,
            )
            if ok:
                self.n_fills += 1
                remaining_quantity = requested_shares - fill_quantity
                if abs(remaining_quantity) > 1e-12:
                    order["quantity"] = remaining_quantity
                    self._record_order_event(
                        order,
                        "partial_fill",
                        current_bar.timestamp,
                        fill_price=fill,
                        quantity=fill_quantity,
                        position_quantity=self._position_quantity(order["symbol"]),
                    )
                    self._wait_or_expire(order, current_bar.timestamp, remaining_orders)
                else:
                    self._record_order_event(
                        order,
                        "filled",
                        current_bar.timestamp,
                        fill_price=fill,
                        quantity=fill_quantity,
                        position_quantity=self._position_quantity(order["symbol"]),
                    )
            else:
                self.n_rejected += 1
                self._record_order_event(
                    order,
                    "rejected",
                    current_bar.timestamp,
                    reason="portfolio_rejected",
                    fill_price=fill,
                    quantity=fill_quantity,
                    position_quantity=self._position_quantity(order["symbol"]),
                )
        self.pending_orders = remaining_orders

    @staticmethod
    def _participation_fill_quantity(
        requested_quantity: float,
        volume: float,
        model: ExecutionCostModel,
        quantity_increment: float | None,
    ) -> float:
        rate = model.max_participation_rate
        if rate is None:
            return requested_quantity
        if volume <= 0:
            return 0.0
        maximum = volume * rate
        if quantity_increment is not None:
            maximum = math.floor(maximum / quantity_increment) * quantity_increment
        quantity = min(abs(requested_quantity), maximum)
        return math.copysign(quantity, requested_quantity)
