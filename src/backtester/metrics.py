# metrics.py
"""Performance metrics for backtest results.

All helpers accept flexible inputs so they work with:
- list[float] of equity values
- list[(timestamp, equity)] tuples (e.g. Portfolio.equity_curve)
- list[PortfolioSnapshot] (Portfolio.history)
"""

import math
import statistics
from collections import defaultdict


def _to_equity_list(equity_curve) -> list[float]:
    if not equity_curve:
        return []
    out: list[float] = []
    for item in equity_curve:
        # PortfolioSnapshot or any object with total_equity
        if hasattr(item, "total_equity"):
            out.append(float(item.total_equity))
        # dict with total_equity / equity
        elif isinstance(item, dict):
            if "total_equity" in item:
                out.append(float(item["total_equity"]))
            elif "equity" in item:
                out.append(float(item["equity"]))
            else:
                raise ValueError(f"Cannot extract equity from dict {item!r}")
        # (timestamp, equity) tuple/list
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            try:
                out.append(float(item[1]))
            except (TypeError, ValueError):
                # fallback: maybe (equity,) style? re-raise clearly
                raise ValueError(f"Cannot extract equity from {item!r}")
        else:
            out.append(float(item))
    return out


def sharpe_ratio(equity_curve, risk_free_rate=0.0, periods_per_year=252) -> float:
    """Annualized Sharpe ratio from an equity curve.

    risk_free_rate is assumed annualized; it is converted to per-period.
    Returns 0.0 when there is insufficient data or zero volatility.
    """
    equities = _to_equity_list(equity_curve)
    if len(equities) < 2:
        return 0.0
    returns: list[float] = []
    for prev, cur in zip(equities[:-1], equities[1:]):
        if prev == 0:
            return 0.0
        returns.append(cur / prev - 1.0)
    if len(returns) < 2:
        return 0.0
    rf_per = float(risk_free_rate) / float(periods_per_year)
    excess = [r - rf_per for r in returns]
    std = statistics.pstdev(excess)
    if std == 0:
        return 0.0
    mean = statistics.fmean(excess)
    return mean / std * math.sqrt(periods_per_year)


def max_drawdown(equity_curve) -> float:
    """Max peak-to-trough drawdown as a fraction (0.0 - 1.0)."""
    equities = _to_equity_list(equity_curve)
    if not equities:
        return 0.0
    peak = equities[0]
    max_dd = 0.0
    for eq in equities:
        if eq > peak:
            peak = eq
        if peak > 0:
            dd = (peak - eq) / peak
            if dd > max_dd:
                max_dd = dd
    return max_dd


def cagr(equity_curve, periods_per_year=252) -> float:
    """Compound annual growth rate, assuming evenly spaced periods.

    n = len(equities) - 1 periods. Returns 0.0 for invalid input.
    """
    equities = _to_equity_list(equity_curve)
    if len(equities) < 2:
        return 0.0
    start, end = equities[0], equities[-1]
    if start <= 0 or end < 0:
        return 0.0
    n = len(equities) - 1
    if n <= 0:
        return 0.0
    total = end / start
    return total ** (float(periods_per_year) / n) - 1.0


def win_rate(trade_log) -> float:
    """Fraction of closing executions that were profitable (0.0 - 1.0).

    Uses FIFO matching per symbol on raw fill prices (pre-cost signal
    quality). Buys close open shorts first, sells close open longs first;
    each execution that closes something counts as one trade. Returns 0.0
    when there are no closed trades.
    """
    if not trade_log:
        return 0.0
    longs: dict[str, list[list[float]]] = defaultdict(list)
    shorts: dict[str, list[list[float]]] = defaultdict(list)
    closed_pnls: list[float] = []

    for t in trade_log:
        if isinstance(t, dict):
            symbol = t.get("symbol")
            qty = t.get("quantity", 0)
            price = t.get("fill_price", 0)
        else:
            symbol = getattr(t, "symbol", None)
            qty = getattr(t, "quantity", 0)
            price = getattr(t, "fill_price", 0)
        if symbol is None:
            continue
        qty = float(qty)
        price = float(price)
        if qty > 0:
            # cover shorts first, remainder opens long
            remaining, pnl, matched = qty, 0.0, False
            queue = shorts.get(symbol, [])
            while remaining > 1e-12 and queue:
                lot_qty, lot_px = queue[0]
                m = min(lot_qty, remaining)
                pnl += (lot_px - price) * m
                lot_qty -= m
                remaining -= m
                matched = True
                if lot_qty <= 1e-12:
                    queue.pop(0)
                else:
                    queue[0][0] = lot_qty
            if matched:
                closed_pnls.append(pnl)
            if remaining > 1e-12:
                longs[symbol].append([remaining, price])
        elif qty < 0:
            # close longs first, remainder opens short
            remaining, pnl, matched = -qty, 0.0, False
            queue = longs.get(symbol, [])
            while remaining > 1e-12 and queue:
                lot_qty, lot_px = queue[0]
                m = min(lot_qty, remaining)
                pnl += (price - lot_px) * m
                lot_qty -= m
                remaining -= m
                matched = True
                if lot_qty <= 1e-12:
                    queue.pop(0)
                else:
                    queue[0][0] = lot_qty
            if matched:
                closed_pnls.append(pnl)
            if remaining > 1e-12:
                shorts[symbol].append([remaining, price])

    if not closed_pnls:
        return 0.0
    wins = sum(1 for p in closed_pnls if p > 0)
    return wins / len(closed_pnls)
