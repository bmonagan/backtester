# Strategy comparison: S&P 500 futures, November 2025–October 2026

This is a one-year, daily-bar comparison of every built-in strategy and
small parameter variations, using Yahoo Finance's continuous E-mini S&P 500
futures symbol `ES=F`. It is a historical example, not a strategy
recommendation or evidence of expected future performance.

## Data and method

- Evaluation window: November 1, 2025–October 31, 2026 (250 daily bars; the
  first session was November 3 and the final session October 30).
- Warm-up: June 2–October 31, 2025 (108 daily bars) is processed before the
  evaluation window. This gives the longest listed channel (55 bars) and
  indicators a pre-period and lets each strategy establish positions. Any
  open positions carry across the boundary; P&L and drawdown start from
  marked equity at the October 31, 2025 close.
- Data: the fixed Yahoo Finance daily-bar snapshot in
  [`sample-es-futures-2025-06-to-2026-10.parquet`](sample-es-futures-2025-06-to-2026-10.parquet),
  downloaded November 1, 2026. Yahoo's continuous-futures series can change
  with its contract-roll and history methodology. The downloader can refresh
  it with:

  ```bash
  uv run python scripts/single_ticker_fetch_data.py \
    --symbol ES=F --start 2025-06-01 --end 2026-11-01 \
    --out docs/sample-es-futures-2025-06-to-2026-10.parquet
  ```

- Execution: market orders fill at the next daily bar's open. No commission
  or slippage; each signal order uses one unit; long-only behavior, as in the
  built-in strategies. Strategies that signal another buy while already long
  can accumulate units. Results are marked to each daily close. “Year fills”
  counts executions in the evaluation window, not completed round trips.
- Sizing interpretation: the backtester treats bars as cash-funded units and
  does not model futures contract multipliers, margin, or liquidation. P&L is
  shown in index points for the strategy's resulting unit exposure. The ES
  and MES dollar columns are the gross point P&L multiplied by $50 and $5 per
  point, respectively; they exclude fees, slippage, and financing. “Notional
  return” is point P&L divided by the October 31, 2025 ES close (6,874.00),
  not a return on margin or account equity.

## Results

The futures price rose from 6,874.00 at the October 31, 2025 close to
7,614.00 at the October 30, 2026 close. Variants are evaluated independently
with the same warm-up and one-unit-per-order sizing.

| Strategy | Parameters | Year fills | P&L (points) | Gross P&L (ES $) | Gross P&L (MES $) | Notional return | Max drawdown (points) |
|---|---|---:|---:|---:|---:|---:|---:|
| SMA crossover | 20/50 (default) | 5 | 602.25 | 30,112.50 | 3,011.25 | 8.761% | 345.25 |
| SMA crossover | 10/30 | 10 | 408.00 | 20,400.00 | 2,040.00 | 5.935% | 434.25 |
| SMA crossover | 5/20 | 21 | 16.25 | 812.50 | 81.25 | 0.236% | 547.75 |
| Buy and hold | baseline | 0 | 740.00 | 37,000.00 | 3,700.00 | 10.765% | 628.25 |
| RSI momentum | 14, 30/70 (default) | 2 | 563.00 | 28,150.00 | 2,815.00 | 8.190% | 61.50 |
| RSI momentum | 7, 30/70 | 20 | 7,146.75 | 357,337.50 | 35,733.75 | 103.968% | 3,403.75 |
| RSI momentum | 14, 40/60 | 16 | 4,592.25 | 229,612.50 | 22,961.25 | 66.806% | 1,356.75 |
| Bollinger mean reversion | 20, 2.0σ (default) | 8 | 1,091.00 | 54,550.00 | 5,455.00 | 15.871% | 620.25 |
| Bollinger mean reversion | 10, 2.0σ | 7 | 1,117.00 | 55,850.00 | 5,585.00 | 16.250% | 628.25 |
| Bollinger mean reversion | 20, 1.5σ | 11 | 988.25 | 49,412.50 | 4,941.25 | 14.377% | 620.25 |
| Donchian breakout | 20/10 (default) | 11 | -235.00 | -11,750.00 | -1,175.00 | -3.419% | 665.75 |
| Donchian breakout | 10/5 | 11 | 351.25 | 17,562.50 | 1,756.25 | 5.110% | 409.25 |
| Turtle System 1-style | 20/10 (default) | 11 | -235.00 | -11,750.00 | -1,175.00 | -3.419% | 665.75 |
| Turtle System 2-style variant | 55/20 | 9 | -906.00 | -45,300.00 | -4,530.00 | -13.180% | 945.00 |

Zero year fills means a strategy made no executions during the evaluation
window; it does not necessarily mean it was flat. Buy and hold entered during
warm-up and remained exposed for the year. RSI variants can accumulate
multiple units because RSI issues an order on each threshold crossover
without tracking whether the strategy is already long; this explains their
large point P&L and drawdowns and makes those rows especially unsuitable as
standalone performance claims. Turtle 20/10 and Donchian 20/10 match because
they use the same channel-breakout rules here.

One year is still a small sample, and the results are sensitive to dates,
parameters, and the continuous-contract series. The backtester does not
model futures margin, contract rolls, exchange fees, or slippage, so dollar
translations are illustrative gross P&L only, not a full futures-account
simulation.
