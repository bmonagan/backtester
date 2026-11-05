# Top-25 strict backtest readiness plan

## Decision

The current simulator is **not adequate for a stricter, real-world rerun** of
the 25 highest-ranked rows. I have not rerun or relabeled these results as
realistic. The existing leaderboard is only a research-screen ranking; its
Sharpe is a normalized P&L proxy, not portfolio return on invested capital.

The top 25 below are frozen from the 510-row CSV, sorted by its existing
proxy Sharpe. They contain 13 derivative rows and 12 equity rows, no crypto
rows. Nine rows have rejected orders, totaling 88 rejected signals. Several
RSI candidates have far more rejected orders than fills. A rejection is not
a simulated fill and cannot be treated as an executed exit.

## Existing top 25

| Rank | Asset | Strategy | Variant | Proxy Sharpe | Fills | Rejected |
|---:|---|---|---|---:|---:|---:|
| 1 | ES=F | VWAP mean reversion | 10:1.0 | 2.635 | 28 | 0 |
| 2 | NQ=F | RSI | 14:30/70 | 2.544 | 2 | 13 |
| 3 | ES=F | RSI | 14:30/70 | 2.365 | 2 | 11 |
| 4 | ES=F | VWAP mean reversion | 20:1.5 | 2.121 | 22 | 0 |
| 5 | AAPL | RSI | 7:30/70 | 2.112 | 18 | 16 |
| 6 | NQ=F | Williams %R | 14:-90/-10 | 2.086 | 11 | 0 |
| 7 | AAPL | CCI | 20:-150/150 | 2.037 | 6 | 0 |
| 8 | AMZN | RSI | 14:30/70 | 2.007 | 2 | 3 |
| 9 | AMZN | Bollinger | 20:1.5 | 1.847 | 13 | 0 |
| 10 | NVDA | RSI | 7:30/70 | 1.827 | 13 | 10 |
| 11 | ES=F | RSI | 14:40/60 | 1.773 | 16 | 10 |
| 12 | NQ=F | Stochastic | 14:20/80 | 1.732 | 17 | 0 |
| 13 | NQ=F | Williams %R | 14:-80/-20 | 1.732 | 17 | 0 |
| 14 | AMZN | Bollinger | 20:2.0 | 1.719 | 10 | 0 |
| 15 | AMZN | CCI | 20:-150/150 | 1.693 | 10 | 0 |
| 16 | ES=F | RSI | 7:30/70 | 1.661 | 20 | 9 |
| 17 | NVDA | VWAP mean reversion | 10:1.0 | 1.636 | 28 | 0 |
| 18 | CL=F | RSI | 14:30/70 | 1.629 | 4 | 4 |
| 19 | NVDA | VWAP mean reversion | 20:1.5 | 1.602 | 19 | 0 |
| 20 | ES=F | CCI | 20:-150/150 | 1.561 | 8 | 0 |
| 21 | ES=F | Bollinger | 20:2.0 | 1.547 | 8 | 0 |
| 22 | AAPL | Bollinger | 10:2.0 | 1.538 | 11 | 0 |
| 23 | AMZN | CCI | 20:-100/100 | 1.477 | 12 | 0 |
| 24 | AAPL | RSI | 14:40/60 | 1.472 | 14 | 12 |
| 25 | GC=F | Stochastic | 14:20/80 | 1.387 | 10 | 0 |

These are not 25 independent hypotheses: configurations repeat across the
same underlying symbols, and Stochastic/Williams %R settings can be
algebraically equivalent. The ranks were selected from 510 configurations
on the same evaluation year, so ranking the winners on that period creates
substantial selection bias.

## Why the current backtest is insufficient

1. **Futures are not accounted for as futures.** The portfolio treats one
   unit as one unit of the quoted price. It has no contract multiplier,
   tick value, initial/maintenance margin, variation margin, expiry, or
   contract-roll cash flows. A point of ES, NQ, CL, or GC movement is not one
   dollar of contract P&L.
2. **Sizing is not comparable across instruments.** The screen uses one
   share, coin, or futures contract per signal and a $1-billion cash balance.
   The quoted notional, leverage, and risk vary dramatically. Repeated
   entry signals can accumulate exposure.
3. **Strategy state is signal-based, not fill-based.** Many strategies set
   their internal in-position state when emitting an order, before the
   engine knows whether it fills. Sell-to-open signals are rejected with
   shorts disabled; strategies that mutate position state on that signal can
   become inconsistent with the ledger. The 88 rejected signals in the top
   25 demonstrate that rejection handling is material.
4. **Trading costs are too simple for this test.** The engine has a flat
   commission and constant basis-point slippage option, but no per-market
   fee schedule, bid-ask spread, maker/taker fees, market impact, volume
   participation, partial fills, borrow/funding costs, or futures exchange
   and clearing fees. The leaderboard assumed zero costs.
5. **Equity price history is not total-return accounting.** The snapshot uses
   Yahoo unadjusted daily OHLC. Splits, dividends, symbol changes, and
   point-in-time index membership are not modeled consistently; the five
   chosen equities also introduce survivorship and selection bias.
6. **The Sharpe is not a portfolio-return Sharpe.** It normalizes daily
   change in account equity by the asset's initial price, rather than
   calculating returns on beginning account equity or committed capital.
   It therefore cannot be interpreted as a funded strategy's risk-adjusted
   return.
7. **The test is in-sample and short.** The top 25 were selected after
   scoring 510 configurations on one year. There is no untouched holdout,
   walk-forward procedure, multiple-testing adjustment, or regime coverage.

## Implementation plan

Complete these phases before publishing a strict rerun. Keep the current
screen as an explicitly exploratory baseline; do not overwrite its CSV.

### Phase 1 — Freeze selection and test inputs

- Preserve the exact top-25 rows, parameter values, data snapshot, and
  original ordering in a manifest with data hashes.
- Treat the 2025-11 to 2026-10 year as discovery data only. Define later
  out-of-sample dates and parameter choices before running them.
- Add survivorship-aware equity constituents and point-in-time crypto
  membership for any historical cross-asset claim.
- **Acceptance:** a reviewer can reproduce the frozen manifest and verify
  that no holdout observations were used to select assets or parameters.

### Phase 2 — Instrument-aware data and accounting

- Add typed instrument metadata: asset class, quote currency, tick size,
  quantity increment, multiplier, contract size, trading calendar/time zone,
  and supported fee/margin schedule.
- For futures, ingest individual expiries and explicit roll rules. Account
  for contract multiplier, tick value, expiry, initial/maintenance margin,
  variation margin, roll execution and any forced liquidation. Do not treat
  continuous back-adjusted series as directly tradable positions.
- For equities, use split/dividend-consistent data and cash corporate
  actions; record delistings and symbol changes.
- Keep crypto venue, quote currency, fee tier, continuous-trading-day
  boundary, and any funding/borrow assumptions explicit.
- **Acceptance:** hand-calculated stock split/dividend, futures multiplier/
  tick/roll, and crypto quote-currency fixtures match ledger cash and equity
  exactly.

### Phase 3 — Fill-aware orders and risk sizing

- Make signal generation target-position based, or return strategy state
  updates only after fills. Pending, rejected, partial, cancelled, and filled
  orders must have distinct lifecycle events.
- Add per-instrument position sizing by target notional or account-risk
  budget, quantity increments, cash/margin checks, leverage caps, portfolio
  exposure caps, and configurable pyramiding only when intended.
- Model short availability, borrow fees, funding, margin calls, and
  liquidation rules explicitly; do not silently count rejected signals as
  strategy exits.
- **Acceptance:** tests cover rejected entry/exit, gap fill, partial fill,
  duplicate signal while pending, margin breach/liquidation, and no
  divergence between strategy target position and ledger position.

### Phase 4 — Market-specific execution and costs

- Add configurable commissions/fees per share, contract, notional, and
  venue, plus minimum charges and maker/taker schedules.
- Model bid/ask spread and adverse slippage by order side, volatility,
  liquidity, and order size versus volume. Support conservative gap fills,
  participation limits, partial fills, and unfilled-order expiry.
- Futures costs must include exchange/clearing fees and realistic roll
  execution; crypto must include venue fees and, where applicable, funding.
- Run base, adverse, and severe cost scenarios. Report gross and net results
  plus fee, spread, slippage, funding, and roll attribution.
- **Acceptance:** cost-free parity preserves the current engine's documented
  fills; synthetic tests assert each cost component and adverse gap behavior.

### Phase 5 — Return and risk reporting

- Calculate daily strategy equity returns as `equity[t] / equity[t-1] - 1`
  from a funded, margin-aware ledger, including flat/cash days and all costs.
- Report annualized Sharpe with a stated risk-free assumption, Sortino,
  maximum drawdown and duration, annualized volatility, turnover, exposure,
  margin utilization, tail loss/expected shortfall, trade count, and
  benchmark-relative returns.
- Use asset-class calendars and consistent portfolio capital. Report
  per-instrument and combined portfolio results separately.
- **Acceptance:** metric fixtures match hand-computed return series, and
  scaling initial capital without changing positions leaves return-based
  metrics invariant.

### Phase 6 — Out-of-sample and robustness protocol

- Use chronological walk-forward train/validation/test splits and a final
  untouched holdout. Freeze top-25 membership from discovery data; do not
  reselect winners on the holdout.
- Re-test across multiple volatility/trend regimes and rolling windows;
  include realistic cost sensitivity and delayed/worse fills.
- Report all 25 candidates, not only survivors. Add bootstrap confidence
  intervals and a multiple-testing adjustment; compare with cash and
  buy-and-hold benchmarks.
- **Acceptance:** publish exact data, configuration, and cost assumptions;
  report confidence intervals and every failed candidate; no strategy is
  called robust solely from a positive in-sample Sharpe.

## Deliverable sequence

1. Instrument metadata, corrected ledger accounting, and fixture tests.
2. Fill-aware strategy/order lifecycle and risk-based sizing.
3. Market-specific execution/cost models and cost-stress tests.
4. Corrected funded-account return metrics.
5. Frozen top-25 walk-forward runner and audited output.
6. A new recommendation only after holdout results pass all prior gates.

Until those gates are implemented and validated, the existing top-25 table
is a hypothesis list, not a realistic performance estimate or investment
recommendation.

## Phase execution status

### Phase 1 — Freeze selection and test inputs: in progress

- The exact top 25, original rank order, strategy variants, explicit parameter
  values, source metrics, and SHA-256 hashes for the result CSV and OHLCV
  snapshot are frozen in
  [`top-25-strict-backtest-manifest.json`](./top-25-strict-backtest-manifest.json).
- The discovery interval is November 1, 2025–October 31, 2026. The snapshot
  ends November 2, 2026; the predeclared one-year holdout is November 3,
  2026–November 2, 2027. It has not been run, and the manifest locks the
  selected strategies and parameters against holdout-based changes.
- Verify the manifest against its source inputs with
  `uv run python scripts/freeze_top25_manifest.py`. Regenerate it only for an
  intentional source change with `--write`.
- **Still outstanding:** the selected five equities and five crypto assets
  are not survivorship-aware historical universes. Phase 1 is not complete
  until point-in-time membership and an appropriate historical universe are
  sourced and frozen. No holdout result is available yet.

### Phase 2 — Instrument-aware data and accounting: in progress

- Added immutable, validated `InstrumentSpec`, `FeeSchedule`, and
  `MarginSchedule` metadata types. Unknown market conventions remain
  explicit; incomplete metadata cannot be reported as execution-ready.
- **Still outstanding:** no symbol metadata registry or instrument-aware
  ledger behavior is wired in yet. Futures contract history, corporate
  actions, and venue-specific crypto assumptions remain unmodeled. Existing
  backtests retain their prior behavior.
