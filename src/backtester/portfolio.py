# portfolio.py
from collections import defaultdict
from dataclasses import dataclass
from math import isfinite

from backtester.instruments import InstrumentSpec


@dataclass
class Position:
    symbol: str
    quantity: float = 0.0
    avg_price: float = 0.0
    settlement_price: float | None = None

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
    margin_used: float = 0.0

class Portfolio:
    def __init__(
        self, starting_cash: float, commission: float = 0.0,
        slippage_bps: float = 0.0, allow_shorts: bool = False,
        instrument_specs: dict[str, InstrumentSpec] | None = None,
    ):
        if commission < 0:
            raise ValueError("commission must be >= 0")
        if slippage_bps < 0:
            raise ValueError("slippage_bps must be >= 0")
        self.cash = starting_cash
        self.commission = commission
        self.slippage_bps = slippage_bps
        self.allow_shorts = allow_shorts
        self.instrument_specs = instrument_specs or {}
        if any(symbol != spec.symbol for symbol, spec in self.instrument_specs.items()):
            raise ValueError("instrument spec keys must match their symbols")
        currencies = {spec.quote_currency for spec in self.instrument_specs.values()}
        if len(currencies) > 1:
            raise ValueError("all instrument quote currencies must match portfolio cash")
        self.cash_currency = next(iter(currencies), None)
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
        margin_used = 0.0

        for ticker, pos in self.positions.items():
            if pos.quantity == 0:
                continue
            if ticker not in prices or prices[ticker] is None:
                raise KeyError(
                    f"Missing price for {ticker} at {timestamp}"
                )
            price = prices[ticker]
            spec = self.instrument_specs.get(ticker)
            multiplier = spec.multiplier if spec and spec.multiplier else 1.0
            if spec and spec.asset_class == "future":
                if spec.margin_schedule is None:
                    raise ValueError(f"{ticker} futures metadata requires margin")
                settlement = pos.settlement_price
                if settlement is None:
                    settlement = price
                    pos.settlement_price = price
                variation = (price - settlement) * pos.quantity * multiplier
                self.cash += variation
                self.realized_pnl += variation
                pos.settlement_price = price
                margin_used += abs(pos.quantity) * spec.margin_schedule.initial
            else:
                positions_value += pos.quantity * price * multiplier
                total_cost_basis += pos.quantity * pos.avg_price * multiplier

        unrealized_pnl = positions_value - total_cost_basis
        total_equity = self.cash + positions_value

        snapshot = PortfolioSnapshot(
            timestamp=timestamp,
            cash=self.cash,
            holdings_value=positions_value,
            total_equity=total_equity,
            unrealized_pnl=unrealized_pnl,
            margin_used=margin_used,
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

        spec = self.instrument_specs.get(symbol)
        if spec and spec.quantity_increment:
            increments = quantity / spec.quantity_increment
            if abs(increments - round(increments)) > 1e-9:
                return False
        comm = self._commission_for_order(
            quantity, fill_price, spec, commission
        )
        eff = self._effective_price(quantity, fill_price, slippage_bps)
        pos = self.positions.get(symbol)
        pos_qty = pos.quantity if pos else 0.0
        if spec and spec.asset_class == "future":
            return self._execute_future_order(
                timestamp, symbol, quantity, fill_price, eff, comm, spec, pos
            )
        multiplier = spec.multiplier if spec and spec.multiplier else 1.0

        # 1. Buying (covers shorts first, then opens/extends long)
        if quantity > 0:
            if quantity * eff * multiplier + comm > self.cash:
                return False
            realized = 0.0
            cover_qty = min(quantity, -pos_qty) if pos_qty < 0 else 0.0
            if cover_qty > 0:
                comm_cover = comm * cover_qty / quantity
                cover_cost = cover_qty * eff * multiplier + comm_cover
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
                total_cost = long_qty * eff * multiplier + comm_long
                self.cash -= total_cost
                per_share = total_cost / long_qty
                self._lots[symbol].append([long_qty, per_share])

            new_qty = pos_qty + quantity
            if new_qty == 0:
                self.positions.pop(symbol, None)
            elif new_qty > 0:
                basis = (
                    max(pos_qty, 0.0) * (pos.avg_price if pos else 0.0) * multiplier
                )
                if long_qty > 0:
                    basis += long_qty * eff * multiplier + comm * long_qty / quantity
                self.positions[symbol] = Position(
                    symbol=symbol, quantity=new_qty,
                    avg_price=basis / (new_qty * multiplier),
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
                proceeds = close_qty * eff * multiplier - comm_close
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
                credit = short_qty * eff * multiplier - comm_short
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
                short_basis = (
                    (-min(pos_qty, 0.0))
                    * (pos.avg_price if pos else 0.0)
                    * multiplier
                )
                if short_qty > 0:
                    short_basis += (
                        short_qty * eff * multiplier - comm * short_qty / sell_qty
                    )
                self.positions[symbol] = Position(
                    symbol=symbol, quantity=new_qty,
                    avg_price=short_basis / (abs(new_qty) * multiplier),
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

    def _commission_for_order(
        self,
        quantity: float,
        fill_price: float,
        spec: InstrumentSpec | None,
        commission: float | None,
    ) -> float:
        if commission is not None:
            return commission
        if spec is None or spec.fee_schedule is None:
            return self.commission
        fees = spec.fee_schedule
        units = abs(quantity)
        notional = units * fill_price * (spec.multiplier or 1.0)
        variable = (
            units * fees.per_unit
            + notional * fees.notional_rate
            + units * fees.exchange_per_contract
        )
        return max(fees.minimum, variable)

    def _execute_future_order(
        self,
        timestamp,
        symbol: str,
        quantity: float,
        fill_price: float,
        effective_price: float,
        commission: float,
        spec: InstrumentSpec,
        position: Position | None,
    ) -> bool:
        if spec.margin_schedule is None or spec.multiplier is None:
            raise ValueError(f"{symbol} futures metadata requires multiplier and margin")
        old_quantity = position.quantity if position else 0.0
        new_quantity = old_quantity + quantity
        if new_quantity < 0 and not self.allow_shorts:
            return False
        close_quantity = (
            min(abs(quantity), abs(old_quantity))
            if old_quantity * quantity < 0
            else 0.0
        )
        open_quantity = abs(quantity) - close_quantity
        required_margin = abs(new_quantity) * spec.margin_schedule.initial
        if self.cash < required_margin + commission:
            return False

        realized = 0.0
        if position is not None and old_quantity:
            settlement = position.settlement_price
            if settlement is None:
                settlement = effective_price
            variation = (
                effective_price - settlement
            ) * old_quantity * spec.multiplier
            self.cash += variation
            self.realized_pnl += variation
            realized += variation

        self.cash -= commission
        if new_quantity == 0:
            self.positions.pop(symbol, None)
        else:
            if old_quantity == 0 or old_quantity * new_quantity < 0:
                average_price = effective_price
            elif open_quantity == 0:
                average_price = position.avg_price if position else effective_price
            else:
                average_price = (
                    abs(old_quantity) * (position.avg_price if position else 0.0)
                    + open_quantity * effective_price
                ) / abs(new_quantity)
            self.positions[symbol] = Position(
                symbol=symbol,
                quantity=new_quantity,
                avg_price=average_price,
                settlement_price=effective_price,
            )
        self.trade_log.append(
            {
                "timestamp": timestamp,
                "symbol": symbol,
                "quantity": quantity,
                "fill_price": fill_price,
                "effective_price": effective_price,
                "commission": commission,
                "realized_pnl": realized,
                "cash_balance": self.cash,
            }
        )
        return True

    def current_equity(self, prices: dict[str, float]) -> float:
        total_equity = self.cash
        for symb, pos in self.positions.items():
            if symb not in prices or prices[symb] is None:
                raise KeyError(f"Missing price for active position in {symb}")
            spec = self.instrument_specs.get(symb)
            multiplier = spec.multiplier if spec and spec.multiplier else 1.0
            if spec and spec.asset_class == "future":
                settlement = pos.settlement_price
                if settlement is not None:
                    total_equity += (
                        prices[symb] - settlement
                    ) * pos.quantity * multiplier
            else:
                total_equity += prices[symb] * pos.quantity * multiplier

        return total_equity

    def apply_split(self, symbol: str, ratio: float) -> None:
        if (
            isinstance(ratio, bool)
            or not isinstance(ratio, (int, float))
            or not isfinite(ratio)
            or ratio <= 0
        ):
            raise ValueError("split ratio must be greater than zero")
        if symbol not in self.positions:
            return
        spec = self.instrument_specs.get(symbol)
        if spec and spec.asset_class == "future":
            raise ValueError("stock splits cannot be applied to futures")
        position = self.positions[symbol]
        position.quantity *= ratio
        position.avg_price /= ratio
        for lots in (self._lots.get(symbol, []), self._short_lots.get(symbol, [])):
            for lot in lots:
                lot[0] *= ratio
                lot[1] /= ratio

    def apply_cash_dividend(self, symbol: str, amount_per_unit: float) -> float:
        if (
            isinstance(amount_per_unit, bool)
            or not isinstance(amount_per_unit, (int, float))
            or not isfinite(amount_per_unit)
            or amount_per_unit < 0
        ):
            raise ValueError("dividend amount must be greater than or equal to zero")
        spec = self.instrument_specs.get(symbol)
        if spec and spec.asset_class == "future":
            raise ValueError("cash dividends cannot be applied to futures")
        position = self.positions.get(symbol)
        if position is None:
            return 0.0
        multiplier = spec.multiplier if spec and spec.multiplier else 1.0
        amount = position.quantity * amount_per_unit * multiplier
        self.cash += amount
        self.realized_pnl += amount
        return amount

    def __str__(self):
        return f"Portfolio: Cash: {self.cash:.2f} Positions: {self.positions}"
