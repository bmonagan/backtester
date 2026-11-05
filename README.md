# backtester

[![pytest](https://github.com/bmonagan/backtester/actions/workflows/pytest.yml/badge.svg)](https://github.com/bmonagan/backtester/actions/workflows/pytest.yml)
![coverage](./docs/coverage.svg)

Event-driven daily-bar backtester in Python. Sixteen strategies, long and short
positions, market/limit/stop orders, FIFO PnL with commissions and slippage,
and a comparison harness that runs every strategy over identical feeds into
one Sharpe/drawdown/CAGR/win-rate table.

## results (sample, AAPL daily 2020–2024)

Starting cash 100,000, zero costs. Past performance, not advice.

Reproduce from the committed sample (no network):

```bash
uv run backtester --data docs/sample-aapl-1d-2020-2024.parquet \
  --start 2020-01-01 --end 2024-01-01 --cash 100000 \
  --compare sma,buyhold,rsi,bollinger,donchian \
  --out-csv docs/compare-aapl-2020-2024.csv
```

Full rows in [`docs/compare-aapl-2020-2024.csv`](docs/compare-aapl-2020-2024.csv).

See the [one-year S&P futures strategy comparison](docs/strategy-comparison-es-2026-10.md)
for all built-in strategies and parameter variations on daily `ES=F` bars,
including the pre-period warm-up.

See the [top-five cryptocurrency strategy comparison](docs/strategy-comparison-crypto-top5-2026-10.md)
for the same one-year window and warm-up across the five assets ranked highest
by market capitalization, including Tether.

The [crypto strategy suggestion](docs/crypto-strategy-suggestion-2026-10.md)
summarizes what the results do—and do not—support.

The [cross-asset strategy research report](docs/cross-asset-strategy-research-2026-10.md)
tests ten additional strategy families over crypto, equities, and futures;
its [510-row Sharpe-ranked output](docs/cross-asset-strategy-results-2025-11-to-2026-10.csv)
and [research suggestion](docs/cross-asset-strategy-suggestion-2026-10.md)
include the risk-adjusted results and limitations.

The [top-25 strict backtest readiness plan](docs/top-25-strict-backtest-readiness-plan.md)
records the current ranking and the simulator work required before those
strategies can be tested under realistic market conditions. Its
[frozen top-25 manifest](docs/top-25-strict-backtest-manifest.json) records
the selection, source hashes, and predeclared holdout window; verify it with
`uv run python scripts/freeze_top25_manifest.py`.

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

Compare every strategy over the same feed (committed sample, runs offline):

```bash
uv run backtester --data docs/sample-aapl-1d-2020-2024.parquet \
  --compare sma,buyhold,rsi,bollinger,donchian,turtle,ema,macd,roc,stochastic,williamsr,cci,keltner,atrtrail,ichimoku,vwap \
  --out-csv compare.csv
```

Size positions by shares, dollars, or equity fraction:

```bash
uv run backtester --data data/demo_1d.parquet --strategy sma --notional 10000
uv run backtester --data data/demo_1d.parquet --strategy buyhold --fraction 0.5
```

Let sell signals open shorts (naked sells are rejected by default):

```bash
uv run backtester --data data/demo_1d.parquet --strategy sma --allow-shorts
```

Stamp a resting order type onto every order (limit rests until touched,
stop triggers on touch):

```bash
uv run backtester --data data/demo_1d.parquet --strategy buyhold \
  --order-type limit --order-price 90
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
  `None`: `sma`, `buyhold`, `rsi`, `bollinger`, `donchian`, `turtle`, `ema`,
  `macd`, `roc`, `stochastic`, `williamsr`, `cci`, `keltner`, `atrtrail`,
  `ichimoku`, `vwap`.
- `turtle` implements the Turtle System 1-style momentum signal: buy a close
  above the prior 20-bar high and exit below the prior 10-bar low. Configure
  with `--turtle-entry` and `--turtle-exit`. It reuses the backtester's
  quantity/notional/fraction sizing; it does not model the original system's
  volatility-based N sizing, pyramiding, protective stops, or breakout filter.
- Additional strategies include EMA crossover, MACD, rate-of-change,
  stochastic, Williams %R, CCI, Keltner channel, ATR trailing breakout,
  Ichimoku cloud, and VWAP mean reversion. Their defaults and parameters are
  available through the strategy classes and comparison registry.
- The engine fills orders queued from the previous bar at the current bar's
  open, marks to market every bar, and counts fills vs rejects. It records
  per-order lifecycle events and exposes `cancel_order(order_id)` for
  outstanding orders. Strategies can reconcile internal position state from
  `on_order_update` callbacks.
- `Portfolio` tracks cash, average-cost positions, FIFO realized PnL, and a
  per-bar equity curve. `metrics` derives Sharpe, max drawdown, CAGR, win
  rate from it. `compare` reruns each strategy on a fresh feed so the table
  is apples to apples.
- Optional `InstrumentSpec` metadata enables contract multipliers, fee and
  quantity-increment checks, futures variation margin, and an account
  gross-leverage cap. Enable `strict_instruments=True` to reject symbols with
  incomplete metadata. This does not supply verified market data, futures
  expiry/roll schedules, or margin-call liquidation.

Execution assumptions can be set per symbol through `execution_models`:

```python
from backtester import BacktestEngine, ExecutionCostModel

engine = BacktestEngine(
    feed,
    strategy,
    starting_cash=100_000,
    execution_models={
        "AAPL": ExecutionCostModel(
            half_spread_bps=2,
            slippage_bps=3,
            impact_bps_at_full_participation=20,
            max_participation_rate=0.05,
            scenario="adverse",
        )
    },
)
portfolio = engine.run()
print(portfolio.cost_totals)
```

Spread and modeled slippage are charged adversely by order side. Impact scales
linearly with fill participation in bar volume; a participation cap can split
an order into partial fills. Orders may set `max_wait_bars` to expire after
that many eligible symbol bars; otherwise they remain good-till-cancelled.
Scenarios scale spread, modeled slippage, and impact by 1.0 (base), 1.5
(adverse), or 2.5 (severe). These configurable assumptions are not calibrated
market forecasts. Cost totals attribute commission, spread, slippage, and
impact, but the comparison/reporting layer does not yet produce gross/net
scenario leaderboards.

`fraction` is sized per order as a share of live equity (buys) or position
value (sells), capped by available cash. With several symbols held at once,
keep `fraction × expected concurrent positions` at or below 1 or later buys
will be rejected for insufficient funds.

Comparison rows include account-return Sharpe and Sortino, annualized
volatility, drawdown and drawdown duration, historical 95% VaR and expected
shortfall, turnover, gross exposure, and margin utilization. Returns use the
mark-to-market account equity curve, so cash days and execution costs are
included; Sharpe and Sortino use a zero risk-free/target rate by default.
Tail estimates from short histories are unstable and should not be treated
as forecasts.

To include benchmark-relative fields in `run_one` or `compare`, pass a
timestamped benchmark equity curve (or an equal-length un-timestamped
sequence) as `benchmark_equity_curve`. Timestamped observations are matched
on shared timestamps; the comparison does not fetch or construct a benchmark
automatically.

`walk_forward_splits` provides expanding chronological train/validation/test
windows over ordered timestamps. It collapses duplicate timestamps from
multi-symbol feeds; it only defines fold boundaries and does not run strategies
or access the predeclared top-25 holdout.

## engineering decisions

- Fills happen at the next open, never the signaling close — no lookahead.
- Market orders fill at the open. Limit orders rest until touched and fill
  at the trigger or better (gaps through fill at the open). Stop orders
  trigger on touch and fill at the open when gapped through. Untriggered
  orders rest good-till-cancel unless `max_wait_bars` is set; malformed ones
  count as rejected.
- Indicator state advances on each bar so a persistent crossover does not
  repeatedly emit the same signal. Stateful strategies reconcile position
  state through pending, partial-fill, and terminal order callbacks.
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
- Execution cost inputs are configurable rather than empirically calibrated;
  no volatility/liquidity-dependent spread model, venue-specific maker/taker
  schedule, futures roll execution, or crypto funding is included yet.
- The sample parquet is git-ignored; tests needing it skip in CI. Run
  `scripts/make_demo_data.py` for an offline demo or bring your own data
  via the fetch script.

## layout

- `src/backtester/datafeed.py` — parquet → `Bar` list, single or multi-ticker
- `src/backtester/strategy.py` and `src/backtester/extra_strategies.py` —
  strategies behind one `on_bar` interface
- `src/backtester/engine.py` — event loop, next-open fills, fill/reject counts
- `src/backtester/portfolio.py` — cash, positions, commission/slippage, FIFO PnL
- `src/backtester/metrics.py` — sharpe, max drawdown, cagr, win rate
- `src/backtester/compare.py` — multi-strategy comparison table
- `scripts/` — yfinance fetch and deterministic demo-data helpers

## testing

```bash
uv run pytest --cov --cov-report=term-missing
uvx ruff check src tests scripts
```

CI enforces a 90% coverage floor. Regenerate the badge after changes:

```bash
uv run pytest -q --cov
uv run python scripts/make_coverage_badge.py
```

239 tests: strategy signals and validation, long/short accounting, limit
and stop fills, notional/fraction sizing, costs and realized PnL,
multi-ticker feeds, engine fills, metrics math, demo-data determinism,
sample/table reproducibility, CLI and comparison harness.
