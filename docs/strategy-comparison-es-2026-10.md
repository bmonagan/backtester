# Strategy comparison: S&P 500 futures, October 2026

This is a one-month, daily-bar comparison of every built-in strategy and
small parameter variations, using Yahoo Finance's continuous E-mini S&P 500
futures symbol `ES=F`. It is a short historical example, not a strategy
recommendation or evidence of expected future performance.

## Data and method

- Evaluation window: October 1–30, 2026 (22 daily bars; October 31 was not a
  trading day).
- Warm-up: July 1–September 30, 2026, included so the moving-average and
  channel strategies have history before the evaluation starts. Existing
  positions carry into October; P&L is measured from the September 30 close.
- Data: the fixed Yahoo Finance daily-bar snapshot in
  [`sample-es-futures-2026-10.parquet`](sample-es-futures-2026-10.parquet),
  downloaded November 1, 2026. Yahoo's continuous-futures series can change
  with its contract-roll and history methodology. The downloader can refresh
  it with:

  ```bash
  uv run python scripts/single_ticker_fetch_data.py \
    --symbol ES=F --start 2026-07-01 --end 2026-11-01 \
    --out docs/sample-es-futures-2026-10.parquet
  ```

- Execution: market orders fill at the next daily bar's open. No commission
  or slippage; one contract-equivalent per entry; long-only behavior, as in
  the built-in strategies. Results are marked to each daily close. “October
  fills” counts executions in the evaluation window, not completed round
  trips.
- Sizing interpretation: the backtester treats bars as cash-funded units and
  does not model futures contract multipliers, margin, or liquidation. P&L is
  therefore first shown in index points for one contract-equivalent. The ES
  and MES dollar columns are the gross point P&L multiplied by $50 and $5 per
  point, respectively; they exclude fees, slippage, and financing. “Notional
  return” is point P&L divided by the September 30 ES close (7,715.50), not a
  return on margin or account equity.

## Results

The futures price fell from 7,715.50 at the September 30 close to 7,614.00 at
the October 30 close. Variants are evaluated independently with the same
warm-up and one-unit sizing.

| Strategy | Parameters | October fills | P&L (points) | Gross P&L (ES $) | Gross P&L (MES $) | Notional return | Max drawdown (points) |
|---|---|---:|---:|---:|---:|---:|---:|
| SMA crossover | 20/50 (default) | 0 | 0.00 | 0.00 | 0.00 | 0.000% | 0.00 |
| SMA crossover | 10/30 | 1 | -0.50 | -25.00 | -2.50 | -0.006% | 214.25 |
| SMA crossover | 5/20 | 1 | 25.25 | 1,262.50 | 126.25 | 0.327% | 169.75 |
| Buy and hold | baseline | 0 | -101.50 | -5,075.00 | -507.50 | -1.316% | 260.00 |
| RSI momentum | 14, 30/70 (default) | 0 | 0.00 | 0.00 | 0.00 | 0.000% | 0.00 |
| RSI momentum | 7, 30/70 | 0 | 0.00 | 0.00 | 0.00 | 0.000% | 0.00 |
| RSI momentum | 14, 40/60 | 0 | 0.00 | 0.00 | 0.00 | 0.000% | 0.00 |
| Bollinger mean reversion | 20, 2.0σ (default) | 0 | 0.00 | 0.00 | 0.00 | 0.000% | 0.00 |
| Bollinger mean reversion | 10, 2.0σ | 1 | -65.50 | -3,275.00 | -327.50 | -0.849% | 186.25 |
| Bollinger mean reversion | 20, 1.5σ | 1 | -65.50 | -3,275.00 | -327.50 | -0.849% | 186.25 |
| Donchian breakout | 20/10 (default) | 1 | -36.00 | -1,800.00 | -180.00 | -0.467% | 194.50 |
| Donchian breakout | 10/5 | 1 | 52.75 | 2,637.50 | 263.75 | 0.684% | 105.75 |
| Turtle System 1-style | 20/10 (default) | 1 | -36.00 | -1,800.00 | -180.00 | -0.467% | 194.50 |
| Turtle System 2-style variant | 55/20 | 2 | -191.50 | -9,575.00 | -957.50 | -2.482% | 221.75 |

Zero October fills means a strategy made no executions during October; it does
not necessarily mean it was flat. For example, buy and hold entered during
warm-up and remained exposed for the evaluation month. Turtle 20/10 and
Donchian 20/10 match because they use the same channel-breakout rules here.
Several strategies and variants were flat for the entire evaluation window,
so their zero P&L should not be read as a successful risk-adjusted result.

This small, single-month sample is highly sensitive to the selected dates and
parameters. The backtester also does not model futures margin, contract rolls,
exchange fees, or slippage, so the dollar translations are illustrative gross
P&L only and are not a full futures-account simulation.
