import argparse
import csv

from backtester.compare import STRATEGIES, build_strategy, compare, format_table
from backtester.datafeed import DataFeed
from backtester.engine import BacktestEngine
from backtester.metrics import cagr, max_drawdown, sharpe_ratio, win_rate
from backtester.strategy import OrderTypeOverride


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="tiny OHLC backtester")
    p.add_argument("--data", default="data/AAPL_1d.parquet")
    p.add_argument("--start", default="2020-01-01")
    p.add_argument("--end", default="2024-01-01")
    p.add_argument("--cash", type=float, default=100000.0)
    p.add_argument("--strategy", choices=sorted(STRATEGIES), default="sma")
    p.add_argument("--fast", type=int, default=20)
    p.add_argument("--slow", type=int, default=50)
    p.add_argument("--quantity", type=float, default=100)
    p.add_argument("--notional", type=float, default=None)
    p.add_argument("--fraction", type=float, default=None)
    p.add_argument("--rsi-period", type=int, default=14)
    p.add_argument("--oversold", type=float, default=30)
    p.add_argument("--overbought", type=float, default=70)
    p.add_argument("--bb-period", type=int, default=20)
    p.add_argument("--bb-std", type=float, default=2.0)
    p.add_argument("--donchian-entry", type=int, default=20)
    p.add_argument("--donchian-exit", type=int, default=10)
    p.add_argument("--commission", type=float, default=0.0)
    p.add_argument("--slippage-bps", type=float, default=0.0)
    p.add_argument(
        "--allow-shorts", action="store_true",
        help="let sell orders open short positions instead of being rejected",
    )
    p.add_argument(
        "--order-type", choices=["market", "limit", "stop"], default="market",
        help="resting order type stamped onto every order",
    )
    p.add_argument(
        "--order-price", type=float, default=None,
        help="resting price for --order-type limit or stop",
    )
    p.add_argument(
        "--compare", default=None,
        help="comma-separated strategy names, e.g. sma,buyhold,rsi",
    )
    p.add_argument("--out-csv", default=None)
    return p


def sizing_kwargs_for(args) -> dict:
    if args.notional is not None:
        return {"notional": args.notional}
    if args.fraction is not None:
        return {"fraction": args.fraction}
    return {"quantity": args.quantity}


def strategy_kwargs_for(args, name: str) -> dict:
    sizing = sizing_kwargs_for(args)
    if name == "sma":
        return {
            "fast_period": args.fast,
            "slow_period": args.slow,
            **sizing,
        }
    if name == "rsi":
        return {
            "period": args.rsi_period,
            "oversold": args.oversold,
            "overbought": args.overbought,
            **sizing,
        }
    if name == "bollinger":
        return {
            "period": args.bb_period,
            "num_std": args.bb_std,
            **sizing,
        }
    if name == "donchian":
        return {
            "entry_period": args.donchian_entry,
            "exit_period": args.donchian_exit,
            **sizing,
        }
    return dict(sizing)


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.notional is not None and args.fraction is not None:
        parser.error("--notional and --fraction are mutually exclusive")

    if args.order_type in ("limit", "stop") and args.order_price is None:
        parser.error(f"--order-type {args.order_type} requires --order-price")

    if args.compare is not None:
        names = [n.strip() for n in args.compare.split(",") if n.strip()]
        if not names:
            parser.error("--compare needs at least one strategy name")
        bad = [n for n in names if n not in STRATEGIES]
        if bad:
            parser.error(
                f"unknown strategies {bad}, choose from {sorted(STRATEGIES)}"
            )

        def factory():
            return DataFeed(
                start=args.start, end=args.end, data_source=args.data
            )
        kwargs = {n: strategy_kwargs_for(args, n) for n in names}
        rows = compare(
            names, factory, starting_cash=args.cash,
            commission=args.commission, slippage_bps=args.slippage_bps,
            strategy_kwargs=kwargs, allow_shorts=args.allow_shorts,
            order_type=args.order_type, order_price=args.order_price,
        )
        print(format_table(rows))
        if args.out_csv:
            with open(args.out_csv, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
            print(f"wrote {args.out_csv}")
        return

    feed = DataFeed(start=args.start, end=args.end, data_source=args.data)
    strategy = build_strategy(
        args.strategy, **strategy_kwargs_for(args, args.strategy)
    )
    if args.order_type != "market":
        strategy = OrderTypeOverride(strategy, args.order_type, args.order_price)
    engine = BacktestEngine(
        feed=feed,
        strategy=strategy,
        starting_cash=args.cash,
        commission=args.commission,
        slippage_bps=args.slippage_bps,
        allow_shorts=args.allow_shorts,
    )

    pf = engine.run()
    eq = [s.total_equity for s in pf.history]
    print("Final portfolio:")
    print(pf)
    print(f"Final equity: {pf.current_equity(engine.latest_prices):.2f}")
    print(
        f"Trades: {len(pf.trade_log)} "
        f"fills={engine.n_fills} rejected={engine.n_rejected}"
    )
    print(f"Sharpe: {sharpe_ratio(eq):.3f}")
    print(f"Max drawdown: {max_drawdown(eq):.3%}")
    print(f"CAGR: {cagr(eq):.3%}")
    print(f"Win rate: {win_rate(pf.trade_log):.1%}")
    print(f"Realized PnL: {pf.realized_pnl:.2f}")

    if args.out_csv:
        with open(args.out_csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow([
                "timestamp", "cash", "holdings_value",
                "total_equity", "unrealized_pnl",
            ])
            for s in pf.history:
                w.writerow([
                    s.timestamp, s.cash, s.holdings_value,
                    s.total_equity, s.unrealized_pnl,
                ])
        print(f"wrote {args.out_csv}")


if __name__ == "__main__":
    main()
