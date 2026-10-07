# backtester

tiny OHLC backtester. feed strategies through an engine, track cash and positions, print a metrics summary.

## quickstart

```bash
uv sync
uv run pytest
PYTHONPATH=src uv run python -m backtester.main --help
PYTHONPATH=src uv run python -m backtester.main --data data/AAPL_1d.parquet --strategy sma --fast 20 --slow 50
```

fetch fresh data:

```bash
uv run python scripts/single_ticker_fetch_data.py --symbol AAPL --start 2020-01-01 --end 2024-01-01
```

## layout

- `src/backtester/datafeed.py` — parquet → `Bar` list, single or multi-ticker
- `src/backtester/strategy.py` — `SmaCrossoverStrategy`, `BuyAndHoldStrategy`
- `src/backtester/engine.py` — fills pending orders at next open, tracks fills/rejects
- `src/backtester/portfolio.py` — cash, positions, commission/slippage, realized pnl
- `src/backtester/metrics.py` — sharpe, max drawdown, cagr, win rate
- `scripts/` — yfinance fetch helpers
