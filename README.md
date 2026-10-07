# backtester

[![pytest](https://github.com/bmonagan/backtester/actions/workflows/pytest.yml/badge.svg)](https://github.com/bmonagan/backtester/actions/workflows/pytest.yml)

Event-driven daily-bar backtester in Python. Five strategies, long and short
positions, market/limit/stop orders, FIFO PnL with commissions and slippage,
and a comparison harness that runs every strategy over identical feeds into
one Sharpe/drawdown/CAGR/win-rate table.

## results (sample, AAPL daily 2020–2024)

Starting cash 100,000, zero costs. Past performance, not advice.
Full rows in [`docs/compare-aapl-2020-2024.csv`](docs/compare-aapl-2020-2024.csv).

| strategy  | final_equity | trades | sharpe | max_drawdown | cagr | win_rate | realized_pnl |
|-----------|--------------|--------|--------|--------------|------|----------|--------------|
| sma       | 106256.08    | 21     | 0.570  | 4.6%         | 1.5% | 50.0%    | 5793.72      |
| buyhold   | 111870.95    | 1      | 0.750  | 5.0%         | 2.9% | 0.0%     | 0.00         |
| rsi       | 109575.82    | 13     | 0.659  | 6.2%         | 2.3% | 100.0%   | 8024.43      |
| bollinger | 104616.22    | 22     | 0.440  | 3.4%         | 1.1% | 72.7%    | 4616.22      |
| donchian  | 106673.68    | 31     | 0.655  | 4.1%         | 1.6% | 53.3%    | 5704.43      |

## quickstart

```bash
uv sync
uv run pytest
uv run python scripts/make_demo_data.py
uv run backtester --help
uv run backtester --data data/demo_1d.parquet --strategy sma --fast 20 --slow 50
```

Compare every strategy over the same feed:

```bash
uv run backtester --data data/AAPL_1d.parquet --compare sma,buyhold,rsi,bollinger,donchian --out-csv compare.csv
```

Size positions by shares, dollars, or equity fraction:

```bash
uv run backtester --data data/demo_1d.parquet --strategy sma --notional 10000
uv run backtester --data data/demo_1d.parquet --strategy buyhold --fraction 0.5
```

Fetch fresh data:

```bash
uv run python scripts/single_ticker_fetch_data.py --symbol AAPL --start 2020-01-01 --end 2024-01-01
```

## how it works

```
DataFeed (parquet → Bars) → Strategy.on_bar → BacktestEngine → Portfolio → metrics
```

- `DataFeed` loads parquet, validates OHLCV columns, slices by date, and
  emits time-major bars for one or many tickers.
- Strategies see one bar plus that symbol's history and return an order or
  `None`: `sma`, `buyhold`, `rsi`, `bollinger`, `donchian`.
- The engine fills orders queued from the previous bar at the current bar's
  open, marks to market every bar, and counts fills vs rejects.
- `Portfolio` tracks cash, average-cost positions, FIFO realized PnL, and a
  per-bar equity curve. `metrics` derives Sharpe, max drawdown, CAGR, win
  rate from it. `compare` reruns each strategy on a fresh feed so the table
  is apples to apples.

## engineering decisions

- Fills happen at the next open, never the signaling close — no lookahead.
- Market orders fill at the open. Limit orders rest until touched and fill
  at the trigger or better (gaps through fill at the open). Stop orders
  trigger on touch and fill at the open when gapped through. Untriggered
  orders rest good-till-cancel; malformed ones count as rejected.
- Signals fire once per cross/break; strategy state always advances, so a
  persistent crossover can't emit a buy every bar.
- Realized PnL uses FIFO lots net of commission and slippage, for longs and
  shorts; the trade log keeps raw and effective prices side by side. Shorts
  are opt-in via `allow_shorts` and unavailable by default.
- Orders size by fixed shares (`quantity`), signed dollars (`notional`), or
  equity fraction (`fraction`: buys deploy off live equity, sells close off
  position value). Sizing resolves to whole shares at the fill price, and
  dust under one share counts as rejected.
- Strategy state is per symbol, so multi-ticker feeds don't leak indicators
  across names.

## limitations

- Daily bars. No intraday, no partial intrabar sequencing beyond OHLC
  trigger checks, no margin calls on shorts.
- The sample parquet is git-ignored; tests needing it skip in CI. Run
  `scripts/make_demo_data.py` for an offline demo or bring your own data
  via the fetch script.

## layout

- `src/backtester/datafeed.py` — parquet → `Bar` list, single or multi-ticker
- `src/backtester/strategy.py` — five strategies behind one `on_bar` interface
- `src/backtester/engine.py` — event loop, next-open fills, fill/reject counts
- `src/backtester/portfolio.py` — cash, positions, commission/slippage, FIFO PnL
- `src/backtester/metrics.py` — sharpe, max drawdown, cagr, win rate
- `src/backtester/compare.py` — multi-strategy comparison table
- `scripts/` — yfinance fetch and deterministic demo-data helpers

## testing

```bash
uv run pytest
uvx ruff check src tests
```

147 tests: strategy signals and validation, long/short accounting, limit
and stop fills, notional/fraction sizing, costs and realized PnL,
multi-ticker feeds, engine fills, metrics math, demo-data determinism,
CLI and comparison harness.
