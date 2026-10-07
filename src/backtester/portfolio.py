# portfolio.py
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class Position:
    symbol: str
    quantity: float = 0.0
    avg_price: float = 0.0

    def __repr__(self):
        return (
            f"Position(symbol='{self.symbol}', quantity={self.quantity}, "
            f"avg_price={self.avg_price:.2f})"
        )

@dataclass
class PortfolioSnapshot:
    timestamp: object
    cash: float
    holdings_value: float
    total_equity: float
    unrealized_pnl: float

class Portfolio:
    def __init__(
        self, starting_cash: float, commission: float = 0.0,
        slippage_bps: float = 0.0, allow_shorts: bool = False,
    ):
        if commission < 0:
            raise ValueError("commission must be >= 0")
        if slippage_bps < 0:
            raise ValueError("slippage_bps must be >= 0")
        self.cash = starting_cash
        self.commission = commission
        self.slippage_bps = slippage_bps
        self.allow_shorts = allow_shorts
        self.positions: dict[str, Position] = {}
        self.equity_curve: list[tuple] = []  # (timestamp, equity)
        self.trade_log: list[dict] = []
        self.history: list[PortfolioSnapshot] = []
        self.realized_pnl: float = 0.0
        # symbol -> [[qty, per_share_basis]] (long lots, qty > 0)
        self._lots: dict[str, list[list[float]]] = defaultdict(list)
        # symbol -> [[qty, per_share_credit]] (short lots, qty > 0 shares sold)
        self._short_lots: dict[str, list[list[float]]] = defaultdict(list)

    def _effective_price(
        self, quantity: float, fill_price: float,
        slippage_bps: float | None = None,
    ) -> float:
        s = self.slippage_bps if slippage_bps is None else slippage_bps
        if s == 0:
            return fill_price
        side = 1 if quantity > 0 else -1
        return fill_price * (1 + side * s / 10000.0)

    def mark_to_market(self, timestamp, prices: dict[str, float]):
        """Record current equity given latest prices per symbol."""
        positions_value = 0.0
        total_cost_basis = 0.0

        for ticker, pos in self.positions.items():
            if pos.quantity == 0:
                continue
            if ticker not in prices or prices[ticker] is None:
                raise KeyError(
                    f"Missing price for {ticker} at {timestamp}"
                )
            price = prices[ticker]

            positions_value += pos.quantity * price
            total_cost_basis += pos.quantity * self.positions[ticker].avg_price

        unrealized_pnl = positions_value - total_cost_basis
        total_equity = self.cash + positions_value

        snapshot = PortfolioSnapshot(
            timestamp=timestamp,
            cash=self.cash,
            holdings_value=positions_value,
            total_equity=total_equity,
            unrealized_pnl=unrealized_pnl
        )
        self.history.append(snapshot)
        self.equity_curve.append((timestamp, total_equity))
        return snapshot

    def execute_order(
        self, timestamp, symbol: str, quantity: float, fill_price: float,
        commission: float | None = None,
        slippage_bps: float | None = None,
    ) -> bool:
        """Update cash/positions, append to trade_log."""
        if quantity == 0:
            return False

        comm = self.commission if commission is None else commission
        eff = self._effective_price(quantity, fill_price, slippage_bps)
        pos = self.positions.get(symbol)
        pos_qty = pos.quantity if pos else 0.0

        # 1. Buying (covers shorts first, then opens/extends long)
        if quantity > 0:
            if quantity * eff + comm > self.cash:
                return False
            realized = 0.0
            cover_qty = min(quantity, -pos_qty) if pos_qty < 0 else 0.0
            if cover_qty > 0:
                comm_cover = comm * cover_qty / quantity
                cover_cost = cover_qty * eff + comm_cover
                self.cash -= cover_cost
                matched = 0.0
                lots = self._short_lots.get(symbol, [])
                remaining = cover_qty
                while remaining > 1e-12 and lots:
                    lot_qty, lot_px = lots[0]
                    m = min(lot_qty, remaining)
                    matched += m * lot_px
                    lot_qty -= m
                    remaining -= m
                    if lot_qty <= 1e-12:
                        lots.pop(0)
                    else:
                        lots[0][0] = lot_qty
                realized += matched - cover_cost
                self.realized_pnl += matched - cover_cost

            long_qty = quantity - cover_qty
            if long_qty > 0:
                comm_long = comm * long_qty / quantity
                total_cost = long_qty * eff + comm_long
                self.cash -= total_cost
                per_share = total_cost / long_qty
                self._lots[symbol].append([long_qty, per_share])

            new_qty = pos_qty + quantity
            if new_qty == 0:
                self.positions.pop(symbol, None)
            elif new_qty > 0:
                basis = (max(pos_qty, 0.0) * (pos.avg_price if pos else 0.0))
                if long_qty > 0:
                    basis += long_qty * eff + comm * long_qty / quantity
                self.positions[symbol] = Position(
                    symbol=symbol, quantity=new_qty,
                    avg_price=basis / new_qty,
                )
            else:
                self.positions[symbol] = Position(
                    symbol=symbol, quantity=new_qty,
                    avg_price=pos.avg_price if pos else eff,
                )

        # 2. Selling (closes longs first, then opens/extends short)
        else:
            sell_qty = abs(quantity)
            close_qty = min(sell_qty, pos_qty) if pos_qty > 0 else 0.0
            short_qty = sell_qty - close_qty
            if short_qty > 0 and not self.allow_shorts:
                return False

            realized = 0.0
            if close_qty > 0:
                comm_close = comm * close_qty / sell_qty
                proceeds = close_qty * eff - comm_close
                self.cash += proceeds
                remaining = close_qty
                cost = 0.0
                lots = self._lots.get(symbol, [])
                while remaining > 1e-12 and lots:
                    lot_qty, lot_px = lots[0]
                    m = min(lot_qty, remaining)
                    cost += m * lot_px
                    lot_qty -= m
                    remaining -= m
                    if lot_qty <= 1e-12:
                        lots.pop(0)
                    else:
                        lots[0][0] = lot_qty
                realized += proceeds - cost
                self.realized_pnl += proceeds - cost

            if short_qty > 0:
                comm_short = comm * short_qty / sell_qty
                credit = short_qty * eff - comm_short
                self.cash += credit
                per_share = credit / short_qty
                self._short_lots[symbol].append([short_qty, per_share])

            new_qty = pos_qty - sell_qty
            if new_qty == 0:
                self.positions.pop(symbol, None)
            elif new_qty > 0:
                self.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=new_qty,
                    avg_price=pos.avg_price if pos else eff,
                )
            else:
                short_basis = (-min(pos_qty, 0.0)) * (pos.avg_price if pos else 0.0)
                if short_qty > 0:
                    short_basis += short_qty * eff - comm * short_qty / sell_qty
                self.positions[symbol] = Position(
                    symbol=symbol, quantity=new_qty,
                    avg_price=short_basis / abs(new_qty),
                )

        # 3. Log trade execution
        self.trade_log.append({
            "timestamp": timestamp,
            "symbol": symbol,
            "quantity": quantity,
            "fill_price": fill_price,
            "effective_price": eff,
            "commission": comm,
            "realized_pnl": realized,
            "cash_balance": self.cash,
        })
        return True

    def current_equity(self, prices: dict[str, float]) -> float:
        total_equity = self.cash
        for symb, pos in self.positions.items():
            if symb not in prices or prices[symb] is None:
                raise KeyError(f"Missing price for active position in {symb}")
            total_equity += prices[symb] * pos.quantity

        return total_equity

    def __str__(self):
        return f"Portfolio: Cash: {self.cash:.2f} Positions: {self.positions}"
