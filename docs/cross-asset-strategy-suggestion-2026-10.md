# Cross-asset strategy research suggestion

## Bottom line

**No strategy in this screen is ready for live deployment.** The best single
row is a 10-day VWAP mean-reversion variant on the E-mini S&P future, with an
annualized proxy Sharpe of 2.64. But it is one result selected from 510
strategy/asset combinations after looking at the same one-year period. It
has not been validated out of sample and excludes fees, slippage, futures
rolls, contract multipliers, and margin. That is a strong multiple-testing
warning, not a trading recommendation.

The full ranked matrix, fixed OHLCV data, and rerun command are in the
[cross-asset research report](./cross-asset-strategy-research-2026-10.md).

## Test design

The screen covers the existing six strategy families plus ten new families,
with two or three parameter variants apiece (34 configurations total), on
five assets in each of three groups:

| Group | Symbols | Selection |
|---|---|---|
| Crypto | BTC-USD, ETH-USD, BNB-USD, XRP-USD, SOL-USD | Five large-cap, liquid non-stablecoins. CoinGecko market-cap ranks on November 2, 2026 were 1, 2, 4, 5, and 7 respectively; stablecoins ranked between them were excluded. |
| Equities | AAPL, MSFT, NVDA, AMZN, GOOGL | Liquid mega-cap U.S. companies; a convenient screen, not a survivorship-bias-free universe. |
| Derivatives | ES=F, NQ=F, CL=F, GC=F, SI=F | Continuous E-mini S&P, E-mini Nasdaq, WTI crude, gold, and silver futures from Yahoo Finance. |

Evaluation is November 1, 2025–October 31, 2026, with bars from June 1,
2025–October 31, 2025 processed as warm-up. Crypto contributes 365 evaluation
bars; equities and futures contribute about 250 sessions. Each instrument
and configuration is run independently. Signals fill at the next daily
open, one unit per order, long-only, with no commission or slippage. New
strategies maintain one signaled long position per symbol; some existing
strategies, notably RSI, can add units on repeated entry signals. Sell
signals that would open a short are rejected.

## Risk-adjusted score

The CSV is sorted descending by annualized Sharpe. For each bar, the report
calculates the change in simulated equity divided by the instrument's close
at the start boundary (one-unit initial notional). Sharpe is the mean of
these normalized daily changes divided by their population standard
deviation, annualized using `sqrt(365)` for crypto and `sqrt(252)` for
equities and derivatives; the assumed risk-free rate is zero. This is a
**unit-notional P&L Sharpe proxy**, not a return on a funded account. Exposure
can grow through repeated entries, and futures price-point P&L is not
converted to contract dollars. The score is useful for ranking this screen,
but is not a realistic portfolio Sharpe.

The CSV also includes annualized volatility, P&L relative to starting
one-unit notional, drawdown relative to that same notional, fills, and
rejected orders. Those measures share the same position-sizing limitations.

## Highest-ranked individual rows

These are the ten highest Sharpe rows among all 510 tests, in score order.
The complete list is in
[`cross-asset-strategy-results-2025-11-to-2026-10.csv`](./cross-asset-strategy-results-2025-11-to-2026-10.csv).

| Rank | Asset | Strategy | Variant | Proxy Sharpe | Volatility | P&L / initial notional | Max drawdown / initial notional | Fills | Rejected |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|
| 1 | ES=F | VWAP mean reversion | 10:1.0 | 2.635 | 10.49% | 27.422% | 7.096% | 28 | 0 |
| 2 | NQ=F | RSI | 14:30/70 | 2.544 | 5.04% | 12.722% | 1.045% | 2 | 13 |
| 3 | ES=F | RSI | 14:30/70 | 2.365 | 3.49% | 8.190% | 0.895% | 2 | 11 |
| 4 | ES=F | VWAP mean reversion | 20:1.5 | 2.121 | 8.31% | 17.490% | 7.096% | 22 | 0 |
| 5 | AAPL | RSI | 7:30/70 | 2.112 | 34.41% | 72.101% | 13.925% | 18 | 16 |
| 6 | NQ=F | Williams %R | 14:-90/-10 | 2.086 | 10.89% | 22.535% | 7.110% | 11 | 0 |
| 7 | AAPL | CCI | 20:-150/150 | 2.037 | 10.73% | 21.689% | 5.308% | 6 | 0 |
| 8 | AMZN | RSI | 14:30/70 | 2.007 | 12.94% | 25.760% | 8.026% | 2 | 3 |
| 9 | AMZN | Bollinger | 20:1.5 | 1.847 | 23.73% | 43.465% | 12.345% | 13 | 0 |
| 10 | NVDA | RSI | 7:30/70 | 1.827 | 39.47% | 71.534% | 26.846% | 13 | 10 |

High individual scores are not automatically robust. For example, the
NQ=F RSI row has 13 rejected short-opening signals for only two fills. The
best score came from selecting the winner among 510 tests on the same
historical window, which biases its apparent performance upward.

## Cross-asset median ranking

To reduce reliance on one instrument, the table below ranks variants by the
median Sharpe across all 15 instruments. “Positive” counts instruments with
Sharpe above zero. Equivalent Stochastic and Williams %R settings tie because
their formulas are algebraic transforms of one another at corresponding
thresholds; they are not independent confirmations.

| Rank | Strategy | Variant | Median Sharpe | Positive instruments | Median P&L / initial notional | Median drawdown / initial notional |
|---:|---|---|---:|---:|---:|---:|
| 1 | Ichimoku | 9/26/52:26 | 0.272 | 9/15 | 3.946% | 23.794% |
| 2 | Williams %R | 14:-80/-20 | 0.132 | 8/15 | 5.494% | 28.874% |
| 2 | Stochastic | 14:20/80 | 0.132 | 8/15 | 5.494% | 28.874% |
| 4 | Ichimoku | 7/22/44:22 | 0.091 | 8/15 | 1.602% | 19.224% |
| 5 | Stochastic | 14:30/70 | 0.085 | 8/15 | 2.410% | 26.721% |
| 6 | RSI | 14:30/70 | 0.084 | 9/15 | 8.190% | 37.783% |
| 7 | Donchian | 10/5 | 0.078 | 8/15 | 1.888% | 20.703% |
| 8 | MACD | 12/26/9 | 0.052 | 10/15 | 1.056% | 21.056% |
| 9 | EMA crossover | 12/26 | 0.044 | 8/15 | 0.728% | 21.270% |
| 10 | ROC | 60:0/0 | 0.032 | 8/15 | 0.564% | 17.293% |

Even the best cross-asset median Sharpe is only 0.27; the top-ranked
Ichimoku setting has a 23.8% median drawdown proxy. The aggregation also
mixes different asset classes and market regimes.

## Suggested next step

Do not trade the selected “winner” live. For a preregistered paper-trading
follow-up, test two deliberately different candidates:

1. **ES=F VWAP mean reversion, 10 bars / 1.0 standard deviation** — the
   highest individual proxy Sharpe (2.64), with 28 fills and no rejected
   orders. Treat it as a hypothesis vulnerable to selection bias and
   continuous-contract artifacts.
2. **Ichimoku 9/26/52/26** — the highest median Sharpe across the 15
   instruments (0.27), but with weak risk-adjusted performance and large
   drawdown proxies.

Freeze those choices and test on later, untouched periods. Before any live
decision, rerun with realistic commission, spread and slippage; correct
futures contract rolls, multipliers and margin; implement fixed risk-based
position sizing and exposure caps; compare with passive benchmarks; and
report account-equity returns, drawdown, and tail risk. If the results do not
survive those tests, do not relax the criteria to rescue them.

This is junior research based on a small, selected historical screen, not
personalized financial advice or a prediction of returns.
