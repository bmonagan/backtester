# Strategy comparison: top-five cryptocurrencies, November 2025–October 2026

This is a one-year, daily-bar comparison of every built-in strategy and
small parameter variations on the five cryptocurrencies ranked highest by
market capitalization on November 2, 2026. It is a historical example, not
a strategy recommendation or evidence of expected future performance.

## Assets and data

The market-cap ranks and asset identities are from the
[CoinGecko markets API](https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=5&page=1&sparkline=false),
queried November 2, 2026. The top five at that time were Bitcoin (BTC),
Ethereum (ETH), Tether (USDT), BNB, and XRP. This literal market-cap ranking
includes USDT, a stablecoin; Solana was ranked seventh and is not included.
Rankings change over time, and this is not a survivorship-bias-free asset
selection.

The fixed Yahoo Finance daily-bar snapshot is
[`sample-crypto-top5-2025-06-to-2026-10.parquet`](sample-crypto-top5-2025-06-to-2026-10.parquet).
It contains 520 bars per asset from June 1, 2025 through November 2, 2026.
Yahoo's daily crypto bars are used as supplied; provider timestamps,
aggregation, and historical data may be revised. Refresh the snapshot with:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
import pandas as pd
import yfinance as yf

tickers = ["BTC-USD", "ETH-USD", "USDT-USD", "BNB-USD", "XRP-USD"]
frames = []
for ticker in tickers:
    df = yf.download(
        ticker, start="2025-06-01", end="2026-11-03",
        interval="1d", auto_adjust=False, progress=False,
    )
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel("Ticker")
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df["Symbol"] = ticker
    frames.append(df)
pd.concat(frames).sort_index().to_parquet(
    Path("docs/sample-crypto-top5-2025-06-to-2026-10.parquet")
)
PY
```

The snapshot includes November 1–2, 2026 because it was fetched after the
evaluation period. Backtests explicitly stop at October 31, 2026; those later
bars do not enter signals, fills, or metrics.

## Method

- Evaluation: November 1, 2025–October 31, 2026, 365 calendar-day bars per
  asset.
- Warm-up: June 1–October 31, 2025, 153 daily bars per asset, processed
  before evaluation. Each strategy runs continuously through the warm-up;
  open positions carry across the boundary. P&L and drawdown start from
  marked equity at the October 31, 2025 close.
- Each asset and variant is run independently. Orders are market orders
  filled at the next daily open, with no commission or slippage. Strategies
  are long-only and use one coin per signal order. Sell signals that would
  open a short are rejected by the engine and are not counted as fills. The
  account starts with $1 billion to avoid cash rejections when signals
  accumulate positions.
- “Year fills” counts executions in the evaluation window, not completed
  round trips. “P&L” is the change in marked account equity from the
  evaluation start boundary to the final close. It is USD and reflects
  accumulated one-coin orders. “P&L / start price” divides that dollar P&L
  by the asset's October 31, 2025 close; because strategies can accumulate
  units, it is not a fixed-notional or account-equity return. Maximum
  drawdown is calculated from the same boundary-started equity curve.
- The engine's generic cash-funded units are not exchange spot execution:
  no exchange fees, spread, custody, financing, or tax is modeled. The
  $1-billion test account is a device to avoid cash constraints, not a
  suggested account size. Results, especially RSI variants, can be dominated
  by repeated entries and accumulated exposure.

## Results

### Rank 1 — Bitcoin (BTC-USD)

| Strategy | Parameters | Year fills | P&L (USD) | P&L / start price | Max drawdown (USD) |
|---|---|---:|---:|---:|---:|
| SMA crossover | 20/50 (default) | 10 | -980.22 | -0.895% | 25,387.54 |
| SMA crossover | 10/30 | 14 | -13,414.39 | -12.244% | 18,467.59 |
| SMA crossover | 5/20 | 19 | -303.84 | -0.277% | 14,293.68 |
| Buy and hold | baseline | 0 | -32,121.41 | -29.320% | 52,080.77 |
| RSI momentum | 14, 30/70 (default) | 11 | 11,697.41 | 10.677% | 142,393.05 |
| RSI momentum | 7, 30/70 | 28 | -78,250.03 | -71.425% | 268,764.47 |
| RSI momentum | 14, 40/60 | 24 | -97,707.98 | -89.185% | 286,276.32 |
| Bollinger mean reversion | 20, 2.0σ (default) | 7 | -26,869.53 | -24.526% | 38,894.46 |
| Bollinger mean reversion | 10, 2.0σ | 11 | -32,647.54 | -29.800% | 43,046.45 |
| Bollinger mean reversion | 20, 1.5σ | 12 | -34,848.79 | -31.809% | 48,887.37 |
| Donchian breakout | 20/10 (default) | 11 | -5,661.12 | -5.167% | 18,891.38 |
| Donchian breakout | 10/5 | 20 | -6,261.13 | -5.715% | 17,477.46 |
| Turtle System 1-style | 20/10 (default) | 11 | -5,661.12 | -5.167% | 18,891.38 |
| Turtle System 2-style variant | 55/20 | 8 | -12,889.84 | -11.766% | 14,496.26 |

### Rank 2 — Ethereum (ETH-USD)

| Strategy | Parameters | Year fills | P&L (USD) | P&L / start price | Max drawdown (USD) |
|---|---|---:|---:|---:|---:|
| SMA crossover | 20/50 (default) | 6 | -350.99 | -9.124% | 1,251.31 |
| SMA crossover | 10/30 | 16 | -386.65 | -10.051% | 810.71 |
| SMA crossover | 5/20 | 23 | 14.03 | 0.365% | 724.54 |
| Buy and hold | baseline | 0 | -1,594.33 | -41.443% | 2,346.25 |
| RSI momentum | 14, 30/70 (default) | 7 | -232.53 | -6.044% | 4,668.85 |
| RSI momentum | 7, 30/70 | 32 | -5,076.45 | -131.956% | 10,583.09 |
| RSI momentum | 14, 40/60 | 29 | -5,752.75 | -149.536% | 11,600.92 |
| Bollinger mean reversion | 20, 2.0σ (default) | 6 | -1,627.90 | -42.315% | 2,057.70 |
| Bollinger mean reversion | 10, 2.0σ | 11 | -1,255.47 | -32.634% | 1,527.90 |
| Bollinger mean reversion | 20, 1.5σ | 10 | -1,743.65 | -45.324% | 1,931.97 |
| Donchian breakout | 20/10 (default) | 14 | -1,273.24 | -33.096% | 1,277.46 |
| Donchian breakout | 10/5 | 16 | -473.11 | -12.298% | 693.56 |
| Turtle System 1-style | 20/10 (default) | 14 | -1,273.24 | -33.096% | 1,277.46 |
| Turtle System 2-style variant | 55/20 | 4 | -243.19 | -6.322% | 526.97 |

### Rank 3 — Tether (USDT-USD)

| Strategy | Parameters | Year fills | P&L (USD) | P&L / start price | Max drawdown (USD) |
|---|---|---:|---:|---:|---:|
| SMA crossover | 20/50 (default) | 12 | -0.002800 | -0.280% | 0.003222 |
| SMA crossover | 10/30 | 18 | -0.003371 | -0.337% | 0.003704 |
| SMA crossover | 5/20 | 22 | -0.002339 | -0.234% | 0.003240 |
| Buy and hold | baseline | 0 | -0.000874 | -0.087% | 0.002830 |
| RSI momentum | 14, 30/70 (default) | 6 | -0.001703 | -0.170% | 0.014024 |
| RSI momentum | 7, 30/70 | 19 | -0.001564 | -0.156% | 0.018058 |
| RSI momentum | 14, 40/60 | 34 | -0.001452 | -0.145% | 0.031033 |
| Bollinger mean reversion | 20, 2.0σ (default) | 9 | 0.001759 | 0.176% | 0.002556 |
| Bollinger mean reversion | 10, 2.0σ | 11 | 0.000597 | 0.060% | 0.002556 |
| Bollinger mean reversion | 20, 1.5σ | 15 | 0.002243 | 0.224% | 0.002198 |
| Donchian breakout | 20/10 (default) | 0 | 0.000000 | 0.000% | 0.000000 |
| Donchian breakout | 10/5 | 1 | -0.000827 | -0.083% | 0.001751 |
| Turtle System 1-style | 20/10 (default) | 0 | 0.000000 | 0.000% | 0.000000 |
| Turtle System 2-style variant | 55/20 | 0 | 0.000000 | 0.000% | 0.000000 |

### Rank 4 — BNB (BNB-USD)

| Strategy | Parameters | Year fills | P&L (USD) | P&L / start price | Max drawdown (USD) |
|---|---|---:|---:|---:|---:|
| SMA crossover | 20/50 (default) | 8 | -73.23 | -6.725% | 275.36 |
| SMA crossover | 10/30 | 12 | -25.01 | -2.296% | 191.17 |
| SMA crossover | 5/20 | 20 | -36.79 | -3.379% | 216.56 |
| Buy and hold | baseline | 0 | -386.34 | -35.478% | 548.96 |
| RSI momentum | 14, 30/70 (default) | 9 | 272.59 | 25.032% | 698.38 |
| RSI momentum | 7, 30/70 | 34 | -204.33 | -18.764% | 1,539.14 |
| RSI momentum | 14, 40/60 | 26 | -311.27 | -28.584% | 2,098.08 |
| Bollinger mean reversion | 20, 2.0σ (default) | 11 | -120.01 | -11.021% | 298.54 |
| Bollinger mean reversion | 10, 2.0σ | 9 | -272.14 | -24.991% | 387.32 |
| Bollinger mean reversion | 20, 1.5σ | 13 | -249.01 | -22.867% | 396.34 |
| Donchian breakout | 20/10 (default) | 9 | -6.45 | -0.592% | 172.31 |
| Donchian breakout | 10/5 | 24 | -238.35 | -21.888% | 261.15 |
| Turtle System 1-style | 20/10 (default) | 9 | -6.45 | -0.592% | 172.31 |
| Turtle System 2-style variant | 55/20 | 7 | -275.04 | -25.257% | 375.94 |

### Rank 5 — XRP (XRP-USD)

| Strategy | Parameters | Year fills | P&L (USD) | P&L / start price | Max drawdown (USD) |
|---|---|---:|---:|---:|---:|
| SMA crossover | 20/50 (default) | 8 | -0.85 | -33.865% | 0.87 |
| SMA crossover | 10/30 | 16 | -1.13 | -45.093% | 1.13 |
| SMA crossover | 5/20 | 25 | -0.68 | -27.300% | 0.74 |
| Buy and hold | baseline | 0 | -1.26 | -50.170% | 1.54 |
| RSI momentum | 14, 30/70 (default) | 5 | -0.23 | -9.002% | 1.15 |
| RSI momentum | 7, 30/70 | 31 | -8.23 | -328.157% | 13.79 |
| RSI momentum | 14, 40/60 | 39 | -13.19 | -525.872% | 22.01 |
| Bollinger mean reversion | 20, 2.0σ (default) | 8 | -0.90 | -35.782% | 1.15 |
| Bollinger mean reversion | 10, 2.0σ | 15 | -0.42 | -16.769% | 1.20 |
| Bollinger mean reversion | 20, 1.5σ | 10 | -1.07 | -42.478% | 1.27 |
| Donchian breakout | 20/10 (default) | 12 | -0.40 | -15.807% | 0.72 |
| Donchian breakout | 10/5 | 18 | -0.37 | -14.909% | 0.86 |
| Turtle System 1-style | 20/10 (default) | 12 | -0.40 | -15.807% | 0.72 |
| Turtle System 2-style variant | 55/20 | 2 | 0.02 | 0.647% | 0.24 |

## Interpretation and limitations

The same nominal one-coin order is not comparable in dollar risk across
assets. Repeated entries can make both drawdown and P&L divided by initial
price exceed 100%; these figures are exposure-sensitive, not percentage
returns on a funded account. RSI does not track position state and can
accumulate a new unit on each qualifying crossover. Tether's peg makes its
price range and dollar moves small; its inclusion follows the stated market
cap ranking, not a claim that stablecoins are comparable to volatile assets.

The strategy code is long-only and does not model exchange execution,
shorting, fees, spread, custody, funding, taxes, or portfolio-level
allocation/risk limits. One year and five assets are not sufficient to infer
robustness. Results should not be used as investment advice.
