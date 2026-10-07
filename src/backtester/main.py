import argparse
import csv

from backtester.datafeed import DataFeed
from backtester.engine import BacktestEngine
from backtester.metrics import cagr, max_drawdown, sharpe_ratio, win_rate
from backtester.strategy import BuyAndHoldStrategy, SmaCrossoverStrategy


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="tiny OHLC backtester")
    p.add_argument("--data", default="data/AAPL_1d.parquet")
    p.add_argument("--start", default="2020-01-01")
    p.add_argument("--end", default="2024-01-01")
    p.add_argument("--cash", type=float, default=1000000.0)
    p.add_argument("--strategy", choices=["sma", "buyhold"], default="sma")
    p.add_argument("--fast", type=int, default=20)
    p.add_argument("--slow", type=int, default=50)
    p.add_argument("--quantity", type=float, default=100)
    p.add_argument("--commission", type=float, default=0.0)
    p.add_argument("--slippage-bps", type=float, default=0.0)
    p.add_argument("--out-csv", default=None)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)

    feed = DataFeed(start=args.start, end=args.end, data_source=args.data)
    if args.strategy == "sma":
        strategy = SmaCrossoverStrategy(fast_period=args.fast, slow_period=args.slow, quantity=args.quantity)
    else:
        strategy = BuyAndHoldStrategy(quantity=args.quantity)
    engine = BacktestEngine(
        feed=feed,
        strategy=strategy,
        starting_cash=args.cash,
        commission=args.commission,
        slippage_bps=args.slippage_bps,
    )

    pf = engine.run()
    eq = [s.total_equity for s in pf.history]
    print("Final portfolio:")
    print(pf)
    print(f"Final equity: {pf.current_equity(engine.latest_prices):.2f}")
    print(f"Trades: {len(pf.trade_log)} fills={engine.n_fills} rejected={engine.n_rejected}")
    print(f"Sharpe: {sharpe_ratio(eq):.3f}")
    print(f"Max drawdown: {max_drawdown(eq):.3%}")
    print(f"CAGR: {cagr(eq):.3%}")
    print(f"Win rate: {win_rate(pf.trade_log):.1%}")
    print(f"Realized PnL: {pf.realized_pnl:.2f}")

    if args.out_csv:
        with open(args.out_csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["timestamp", "cash", "holdings_value", "total_equity", "unrealized_pnl"])
            for s in pf.history:
                w.writerow([s.timestamp, s.cash, s.holdings_value, s.total_equity, s.unrealized_pnl])
        print(f"wrote {args.out_csv}")


if __name__ == "__main__":
    main()
