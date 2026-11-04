# Cross-asset strategy screen, November 2025–October 2026

This report documents the tested universe, the ten newly implemented
strategy families, the parameter matrix, the risk metric, and the complete
ranked output. The companion
[strategy suggestion](./cross-asset-strategy-suggestion-2026-10.md)
summarizes the results and recommends only further paper testing.

## New strategy families tested

Each new family was run at the two listed parameter settings. All enter
long-only and exit with the paired signal; stops, shorts, commissions, and
portfolio-level sizing are not added implicitly.

| Family | Rule used | Variants |
|---|---|---|
| EMA crossover | Enter when fast EMA crosses above slow EMA; exit on the reverse cross. | 12/26, 8/21 |
| MACD | Enter on MACD crossing above its signal EMA; exit on the bearish cross. | 12/26/9, 8/21/5 |
| Rate of change (ROC) | Enter when N-bar price change crosses above zero; exit below zero. | 20, 60 bars |
| Stochastic oscillator | Enter when %K crosses up through oversold; exit down through overbought. | 14 bars, 20/80 and 30/70 |
| Williams %R | Enter crossing up from oversold; exit crossing down from overbought. | 14 bars, -80/-20 and -90/-10 |
| Commodity channel index (CCI) | Enter on cross above a negative CCI threshold; exit below the positive threshold. | 20 bars, ±100 and ±150 |
| Keltner channel | Enter above the prior EMA/ATR upper channel; exit below the lower channel. | 20 EMA / 10 ATR, multipliers 2.0 and 1.5 |
| ATR trailing breakout | Enter above the prior N-bar high; exit below the highest-high chandelier stop. | 20/14 bars at 3 ATR; 55/14 at 2.5 ATR |
| Ichimoku cloud | Enter above the lag-safe cloud with conversion above base; exit below cloud. | 9/26/52 with 26 displacement; 7/22/44 with 22 displacement |
| VWAP mean reversion | Enter below a rolling volume-weighted price band; exit on a cross back above VWAP. | 20 bars / 1.5σ; 10 bars / 1.0σ |

The existing families were also included: SMA 20/50, 10/30, 5/20;
buy-and-hold; RSI 14:30/70, 7:30/70, 14:40/60; Bollinger 20:2.0, 10:2.0,
20:1.5; Donchian 20/10 and 10/5; Turtle 20/10 and 55/20. Together with the
20 new-family configurations, the screen contains 34 configurations per
asset and 510 asset/configuration results.

## Universe, period, and execution

- **Crypto:** BTC-USD, ETH-USD, BNB-USD, XRP-USD, SOL-USD. These are the five
  highest-ranked non-stablecoins by [CoinGecko market cap](https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=10&page=1&sparkline=false)
  on November 2, 2026 (overall ranks 1, 2, 4, 5, 7); stablecoins are
  excluded. This is a point-in-time selection and carries
  survivorship/selection bias.
- **Equities:** AAPL, MSFT, NVDA, AMZN, GOOGL, selected as liquid U.S.
  mega-cap companies. This is not a historical constituent universe.
- **Derivatives:** Yahoo Finance continuous symbols ES=F, NQ=F, CL=F, GC=F,
  SI=F for E-mini S&P 500, E-mini Nasdaq 100, WTI crude, gold, and silver.
  These series are not individual tradable futures contracts and may have
  vendor-specific roll adjustments.
- **Data:** fixed Yahoo Finance daily OHLCV snapshot in
  [`sample-cross-asset-2025-06-to-2026-10.parquet`](./sample-cross-asset-2025-06-to-2026-10.parquet),
  fetched November 2, 2026. Data includes June 2025 through November 2, 2026;
  the two post-evaluation dates are excluded from every backtest.
- **Evaluation:** November 1, 2025–October 31, 2026. This is 365 crypto daily
  bars and about 250 equity/futures sessions.
- **Warm-up:** June 1, 2025–October 31, 2025. It is processed before the
  evaluation boundary so long indicators such as Ichimoku have history and
  signals may establish positions. Positions carry over the boundary. The
  engine marks equity at the last pre-period close and performance starts
  from that mark.
- **Execution:** one asset/configuration per independent run, one unit per
  entry signal, $1 billion starting cash to avoid cash rejections, no
  commission/slippage, and no shorting. Short-opening sell signals are
  rejected and counted; 377 such orders were rejected in the 510 runs.
  Results are not a cross-asset portfolio.

## Score and interpretation

Rows in the complete CSV are sorted by descending annualized Sharpe. Daily
P&L is normalized by the asset's close at the evaluation start boundary. The
Sharpe is mean daily normalized P&L divided by its population standard
deviation, multiplied by `sqrt(365)` for crypto or `sqrt(252)` for equities
and derivatives. The assumed risk-free rate is zero.

This is a **unit-notional P&L Sharpe proxy**, not an account-equity return:
the account is deliberately oversized, positions may accumulate, and the
denominator is one unit's starting price rather than account equity or
futures margin. Futures P&L is in index/commodity price points per contract
unit, not dollars; no contract multiplier, margin, or roll cost is modeled.
Equity OHLC uses Yahoo's unadjusted Close rather than total-return data.
Values are gross of commissions, spread, slippage, borrow/funding, and taxes.
Sharpe selected from 510 configurations on one year is subject to substantial
multiple-testing bias.

## Reproduce

With the project's dependencies installed, regenerate the data and sorted
CSV with:

```bash
uv run python scripts/run_cross_asset_research.py --refresh
```

To rerun from the frozen snapshot without a network request:

```bash
uv run python scripts/run_cross_asset_research.py
```

The output
[`cross-asset-strategy-results-2025-11-to-2026-10.csv`](./cross-asset-strategy-results-2025-11-to-2026-10.csv)
contains all 510 rows, sorted by Sharpe, including annualized volatility,
unit-notional P&L, maximum drawdown, fills, and rejected orders.
