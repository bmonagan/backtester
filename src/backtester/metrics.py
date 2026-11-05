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


def _validate_periods_per_year(periods_per_year: int) -> None:
    if (
        isinstance(periods_per_year, bool)
        or not isinstance(periods_per_year, (int, float))
        or not math.isfinite(periods_per_year)
        or periods_per_year <= 0
    ):
        raise ValueError("periods_per_year must be finite and greater than zero")


def _equity_returns(equity_curve) -> list[float]:
    equities = _to_equity_list(equity_curve)
    if any(not math.isfinite(equity) for equity in equities):
        raise ValueError("equity values must be finite")
    returns = []
    for previous, current in zip(equities, equities[1:]):
        if previous <= 0:
            raise ValueError("beginning equity must be greater than zero")
        returns.append(current / previous - 1.0)
    return returns


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


def annualized_volatility(equity_curve, periods_per_year=252) -> float:
    """Population standard deviation of account returns, annualized."""
    _validate_periods_per_year(periods_per_year)
    returns = _equity_returns(equity_curve)
    if len(returns) < 2:
        return 0.0
    return statistics.pstdev(returns) * math.sqrt(periods_per_year)


def sortino_ratio(
    equity_curve,
    risk_free_rate=0.0,
    periods_per_year=252,
) -> float:
    """Annualized Sortino ratio using the per-period risk-free rate as target."""
    _validate_periods_per_year(periods_per_year)
    if not math.isfinite(risk_free_rate):
        raise ValueError("risk_free_rate must be finite")
    returns = _equity_returns(equity_curve)
    if len(returns) < 2:
        return 0.0
    target = risk_free_rate / periods_per_year
    excess = [value - target for value in returns]
    downside_deviation = math.sqrt(
        math.fsum(min(value, 0.0) ** 2 for value in excess) / len(excess)
    )
    if downside_deviation == 0:
        return 0.0
    return statistics.fmean(excess) / downside_deviation * math.sqrt(periods_per_year)


def max_drawdown_duration(equity_curve) -> int:
    """Longest number of consecutive observations below the prior equity peak."""
    equities = _to_equity_list(equity_curve)
    peak = float("-inf")
    current_duration = 0
    longest_duration = 0
    for equity in equities:
        if equity >= peak:
            peak = equity
            current_duration = 0
        else:
            current_duration += 1
            longest_duration = max(longest_duration, current_duration)
    return longest_duration


def historical_var(equity_curve, confidence_level=0.95) -> float:
    """Historical loss VaR as a positive fraction of equity."""
    returns = _equity_returns(equity_curve)
    quantile = _lower_tail_quantile(returns, confidence_level)
    return max(0.0, -quantile)


def historical_expected_shortfall(equity_curve, confidence_level=0.95) -> float:
    """Mean positive loss in the empirical lower tail, as a fraction of equity."""
    returns = _equity_returns(equity_curve)
    quantile = _lower_tail_quantile(returns, confidence_level)
    tail_returns = [value for value in returns if value <= quantile]
    return max(0.0, -statistics.fmean(tail_returns))


def _lower_tail_quantile(returns: list[float], confidence_level: float) -> float:
    if (
        isinstance(confidence_level, bool)
        or not isinstance(confidence_level, (int, float))
        or not math.isfinite(confidence_level)
        or not 0 < confidence_level < 1
    ):
        raise ValueError("confidence_level must be between zero and one")
    if not returns:
        return 0.0
    ordered = sorted(returns)
    index = max(0, math.ceil((1.0 - confidence_level) * len(ordered)) - 1)
    return ordered[index]


def portfolio_metrics(
    portfolio,
    risk_free_rate=0.0,
    periods_per_year=252,
    confidence_level=0.95,
) -> dict:
    """Summarize funded account returns, turnover, exposure, and margin use.

    Turnover is total absolute traded notional divided by average observed
    account equity. Exposure and margin utilization are averaged across the
    portfolio's mark-to-market observations.
    """
    history = []
    for snapshot in portfolio.history:
        if history and history[-1].timestamp == snapshot.timestamp:
            history[-1] = snapshot
        else:
            history.append(snapshot)
    equities = [snapshot.total_equity for snapshot in history]
    _equity_returns(equities)
    if any(equity <= 0 for equity in equities):
        raise ValueError("portfolio equity must remain greater than zero")
    average_equity = statistics.fmean(equities) if equities else 0.0
    if average_equity > 0:
        traded_notional = math.fsum(
            abs(trade["quantity"])
            * trade["fill_price"]
            * (
                portfolio.instrument_specs[trade["symbol"]].multiplier
                if trade["symbol"] in portfolio.instrument_specs
                and portfolio.instrument_specs[trade["symbol"]].multiplier
                else 1.0
            )
            for trade in portfolio.trade_log
        )
        turnover = traded_notional / average_equity
    else:
        turnover = 0.0
    average_exposure = (
        statistics.fmean(
            snapshot.gross_exposure / snapshot.total_equity for snapshot in history
        )
        if history
        else 0.0
    )
    average_margin_utilization = (
        statistics.fmean(
            snapshot.margin_used / snapshot.total_equity for snapshot in history
        )
        if history
        else 0.0
    )
    return {
        "total_return": (
            equities[-1] / equities[0] - 1.0 if len(equities) > 1 else 0.0
        ),
        "annualized_return": cagr(equities, periods_per_year),
        "sharpe": sharpe_ratio(
            equities, risk_free_rate=risk_free_rate, periods_per_year=periods_per_year
        ),
        "sortino": sortino_ratio(
            equities, risk_free_rate=risk_free_rate, periods_per_year=periods_per_year
        ),
        "annualized_volatility": annualized_volatility(equities, periods_per_year),
        "max_drawdown": max_drawdown(equities),
        "max_drawdown_duration": max_drawdown_duration(equities),
        "historical_var": historical_var(equities, confidence_level),
        "expected_shortfall": historical_expected_shortfall(
            equities, confidence_level
        ),
        "turnover": turnover,
        "average_gross_exposure": average_exposure,
        "average_margin_utilization": average_margin_utilization,
    }


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
