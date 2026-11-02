# Crypto strategy suggestion from the November 2025–October 2026 comparison

## Bottom line

**The comparison does not justify deploying any tested strategy with real
capital.** It covers only one year, evaluates the five coins selected by
their market-cap ranking at the end of the period, omits trading costs, and
does not apply portfolio-level risk limits. The results are therefore
exploratory, not evidence that a strategy has a durable edge.

The full per-coin results and method are in the
[top-five crypto comparison](./strategy-comparison-crypto-top5-2026-10.md).

## What the results suggest

- Buy and hold lost value over the period on BTC, ETH, BNB, and XRP.
- No tested configuration was consistently strong across those four volatile
  assets.
- RSI 7 and RSI 14 with 40/60 thresholds produced very large drawdowns on
  several assets. RSI signals can submit another buy each time a qualifying
  crossover occurs, even while already long. The simulated position can
  therefore accumulate, making those headline P&L values unsuitable for
  choosing a strategy.
- The Turtle/Donchian 55/20 variant had fewer fills than most alternatives
  and smaller drawdowns than many tested variants on BTC and ETH, but it
  still lost 11.8% and 6.3% of the starting-price proxy, respectively, and
  lost 25.3% on BNB. Its one positive result was XRP at 0.6%. This is not a
  robust cross-asset result.
- USDT is a stablecoin and is not a useful proxy for a volatile-asset
  momentum opportunity. Its inclusion follows the snapshot-date market-cap
  ranking, not a recommendation to trade it.

## Suggested next step

Do not trade this backtest live. If selecting one candidate for **further
paper testing only**, start with Turtle/Donchian 55/20 on BTC, and treat it as
a hypothesis rather than a recommendation. It had eight fills and an
11.8% loss on the report's starting-price proxy, so the test did not show
profitability; the reason to investigate it first is its lower activity and
smaller reported BTC drawdown than many of the alternatives, not a positive
return.

Before drawing a conclusion, rerun it over multiple non-overlapping market
regimes and add:

1. A fixed, position-aware sizing rule so an entry cannot silently pyramid.
2. Explicit fees, spread, and slippage assumptions.
3. Portfolio-level exposure limits and a predeclared drawdown stop.
4. A benchmark and out-of-sample periods selected before inspecting results.
5. A consistent risk denominator (account equity or volatility-targeted
   exposure), rather than P&L divided by a coin's initial price.

If it fails those tests, remain uninvested under this strategy rather than
relaxing the rules after seeing the results.

This is a general interpretation of a small historical simulation, not
personalized financial advice or a prediction of future returns.
