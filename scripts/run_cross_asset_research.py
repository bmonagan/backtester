"""Run the fixed cross-asset daily strategy research matrix."""

import argparse
import csv
import math
import statistics
from pathlib import Path

import pandas as pd
import yfinance as yf

from backtester.datafeed import DataFeed
from backtester.engine import BacktestEngine
from backtester.extra_strategies import (
    AtrTrailingBreakoutStrategy,
    CciStrategy,
    EmaCrossoverStrategy,
    IchimokuCloudStrategy,
    KeltnerChannelStrategy,
    MacdStrategy,
    RateOfChangeStrategy,
    StochasticOscillatorStrategy,
    VwapMeanReversionStrategy,
    WilliamsRStrategy,
)
from backtester.strategy import (
    BollingerMeanReversionStrategy,
    BuyAndHoldStrategy,
    DonchianBreakoutStrategy,
    RsiMomentumStrategy,
    SmaCrossoverStrategy,
    TurtleTradingStrategy,
)

DATA_START = "2025-06-01"
DATA_END = "2026-11-03"
EVALUATION_START = "2025-11-01"
EVALUATION_END = "2026-10-31"
STARTING_CASH = 1_000_000_000.0

ASSETS = {
    "crypto": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD"],
    "equity": ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"],
    "derivative": ["ES=F", "NQ=F", "CL=F", "GC=F", "SI=F"],
}


def _config(strategy: str, variant: str, cls, **params) -> dict:
    return {"strategy": strategy, "variant": variant, "class": cls, "params": params}


CONFIGS = [
    _config("SMA", "20/50", SmaCrossoverStrategy, fast_period=20, slow_period=50),
    _config("SMA", "10/30", SmaCrossoverStrategy, fast_period=10, slow_period=30),
    _config("SMA", "5/20", SmaCrossoverStrategy, fast_period=5, slow_period=20),
    _config("Buy and hold", "default", BuyAndHoldStrategy),
    _config("RSI", "14:30/70", RsiMomentumStrategy, period=14, oversold=30, overbought=70),
    _config("RSI", "7:30/70", RsiMomentumStrategy, period=7, oversold=30, overbought=70),
    _config("RSI", "14:40/60", RsiMomentumStrategy, period=14, oversold=40, overbought=60),
    _config("Bollinger", "20:2.0", BollingerMeanReversionStrategy, period=20, num_std=2.0),
    _config("Bollinger", "10:2.0", BollingerMeanReversionStrategy, period=10, num_std=2.0),
    _config("Bollinger", "20:1.5", BollingerMeanReversionStrategy, period=20, num_std=1.5),
    _config("Donchian", "20/10", DonchianBreakoutStrategy, entry_period=20, exit_period=10),
    _config("Donchian", "10/5", DonchianBreakoutStrategy, entry_period=10, exit_period=5),
    _config("Turtle", "20/10", TurtleTradingStrategy, entry_period=20, exit_period=10),
    _config("Turtle", "55/20", TurtleTradingStrategy, entry_period=55, exit_period=20),
    _config("EMA crossover", "12/26", EmaCrossoverStrategy, fast_period=12, slow_period=26),
    _config("EMA crossover", "8/21", EmaCrossoverStrategy, fast_period=8, slow_period=21),
    _config("MACD", "12/26/9", MacdStrategy, fast_period=12, slow_period=26, signal_period=9),
    _config("MACD", "8/21/5", MacdStrategy, fast_period=8, slow_period=21, signal_period=5),
    _config("ROC", "20:0/0", RateOfChangeStrategy, period=20),
    _config("ROC", "60:0/0", RateOfChangeStrategy, period=60),
    _config(
        "Stochastic",
        "14:20/80",
        StochasticOscillatorStrategy,
        period=14,
        oversold=20,
        overbought=80,
    ),
    _config(
        "Stochastic",
        "14:30/70",
        StochasticOscillatorStrategy,
        period=14,
        oversold=30,
        overbought=70,
    ),
    _config(
        "Williams %R", "14:-80/-20", WilliamsRStrategy, period=14, oversold=-80, overbought=-20
    ),
    _config(
        "Williams %R", "14:-90/-10", WilliamsRStrategy, period=14, oversold=-90, overbought=-10
    ),
    _config("CCI", "20:-100/100", CciStrategy, period=20, entry_level=-100, exit_level=100),
    _config("CCI", "20:-150/150", CciStrategy, period=20, entry_level=-150, exit_level=150),
    _config(
        "Keltner", "20/10:2.0", KeltnerChannelStrategy, period=20, atr_period=10, multiplier=2.0
    ),
    _config(
        "Keltner", "20/10:1.5", KeltnerChannelStrategy, period=20, atr_period=10, multiplier=1.5
    ),
    _config(
        "ATR trailing breakout",
        "20/14:3.0",
        AtrTrailingBreakoutStrategy,
        entry_period=20,
        atr_period=14,
        atr_multiplier=3.0,
    ),
    _config(
        "ATR trailing breakout",
        "55/14:2.5",
        AtrTrailingBreakoutStrategy,
        entry_period=55,
        atr_period=14,
        atr_multiplier=2.5,
    ),
    _config(
        "Ichimoku",
        "9/26/52:26",
        IchimokuCloudStrategy,
        conversion_period=9,
        base_period=26,
        span_b_period=52,
        displacement=26,
    ),
    _config(
        "Ichimoku",
        "7/22/44:22",
        IchimokuCloudStrategy,
        conversion_period=7,
        base_period=22,
        span_b_period=44,
        displacement=22,
    ),
    _config("VWAP mean reversion", "20:1.5", VwapMeanReversionStrategy, period=20, num_std=1.5),
    _config("VWAP mean reversion", "10:1.0", VwapMeanReversionStrategy, period=10, num_std=1.0),
]


def download_snapshot(path: Path) -> None:
    frames = []
    tickers = [ticker for values in ASSETS.values() for ticker in values]
    for ticker in tickers:
        frame = yf.download(
            ticker,
            start=DATA_START,
            end=DATA_END,
            interval="1d",
            auto_adjust=False,
            progress=False,
        )
        if frame.empty:
            raise RuntimeError(f"No daily bars returned for {ticker}")
        if isinstance(frame.columns, pd.MultiIndex):
            frame.columns = frame.columns.droplevel("Ticker")
        frame = frame[["Open", "High", "Low", "Close", "Volume"]].copy()
        frame["Symbol"] = ticker
        frames.append(frame)
    combined = pd.concat(frames).sort_index()
    path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(path)


def _sharpe(returns: list[float], periods_per_year: int) -> float:
    if len(returns) < 2:
        return 0.0
    deviation = statistics.pstdev(returns)
    if deviation == 0:
        return 0.0
    return statistics.fmean(returns) / deviation * math.sqrt(periods_per_year)


def run_matrix(data_path: Path) -> list[dict]:
    data = pd.read_parquet(data_path)
    results = []
    for asset_class, tickers in ASSETS.items():
        annual_periods = 365 if asset_class == "crypto" else 252
        for ticker in tickers:
            asset_data = data[data["Symbol"] == ticker]
            pre = asset_data.loc[asset_data.index < EVALUATION_START]
            if pre.empty:
                raise ValueError(f"{ticker} is missing the evaluation boundary close")
            start_price = float(pre.iloc[-1]["Close"])
            if start_price <= 0:
                raise ValueError(f"{ticker} has a nonpositive boundary close")

            for config in CONFIGS:
                feed = DataFeed(
                    start=DATA_START,
                    end=EVALUATION_END,
                    data_source=str(data_path),
                    symbols=ticker,
                )
                strategy = config["class"](quantity=1, **config["params"])
                engine = BacktestEngine(
                    feed=feed,
                    strategy=strategy,
                    starting_cash=STARTING_CASH,
                    allow_shorts=False,
                )
                portfolio = engine.run()
                before = [
                    snapshot
                    for snapshot in portfolio.history
                    if pd.Timestamp(snapshot.timestamp) < pd.Timestamp(EVALUATION_START)
                ]
                period = [
                    snapshot
                    for snapshot in portfolio.history
                    if pd.Timestamp(snapshot.timestamp) >= pd.Timestamp(EVALUATION_START)
                ]
                if not before or not period:
                    raise ValueError(f"{ticker} has incomplete evaluation-window bars")
                equity = [before[-1].total_equity] + [snapshot.total_equity for snapshot in period]
                daily_returns = [
                    (current - previous) / start_price
                    for previous, current in zip(equity[:-1], equity[1:])
                ]
                peak = equity[0]
                max_drawdown = 0.0
                for value in equity:
                    peak = max(peak, value)
                    max_drawdown = max(max_drawdown, peak - value)
                fills = sum(
                    pd.Timestamp(trade["timestamp"]) >= pd.Timestamp(EVALUATION_START)
                    for trade in portfolio.trade_log
                )
                results.append(
                    {
                        "asset_class": asset_class,
                        "symbol": ticker,
                        "strategy": config["strategy"],
                        "variant": config["variant"],
                        "sharpe": _sharpe(daily_returns, annual_periods),
                        "annualized_volatility_pct": (
                            statistics.pstdev(daily_returns) * math.sqrt(annual_periods) * 100
                            if daily_returns
                            else 0.0
                        ),
                        "pnl_asset_price_units": equity[-1] - equity[0],
                        "pnl_pct_of_initial_unit_notional": (
                            (equity[-1] - equity[0]) / start_price * 100
                        ),
                        "max_drawdown_asset_price_units": max_drawdown,
                        "max_drawdown_pct_of_initial_unit_notional": (
                            max_drawdown / start_price * 100
                        ),
                        "fills": fills,
                        "rejected_orders": engine.n_rejected,
                    }
                )
    return sorted(
        results,
        key=lambda row: (
            -row["sharpe"],
            row["asset_class"],
            row["symbol"],
            row["strategy"],
            row["variant"],
        ),
    )


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("docs/sample-cross-asset-2025-06-to-2026-10.parquet"),
    )
    parser.add_argument("--refresh", action="store_true", help="download fresh Yahoo Finance bars")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/cross-asset-strategy-results-2025-11-to-2026-10.csv"),
    )
    args = parser.parse_args(argv)
    if args.refresh:
        download_snapshot(args.data)
    if not args.data.is_file():
        parser.error(f"data snapshot not found: {args.data}; pass --refresh to download it")
    results = run_matrix(args.data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    print(f"Wrote {len(results)} risk-sorted rows to {args.out}")
    for row in results[:10]:
        print(
            f"{row['sharpe']:.3f} {row['asset_class']:10s} {row['symbol']:8s} "
            f"{row['strategy']} {row['variant']}"
        )


if __name__ == "__main__":
    main()
