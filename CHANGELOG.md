# changelog

## 0.3.1

- Hardening pass: `--compare` with no names and `--notional` + `--fraction`
  together now fail fast with a clear CLI error instead of crashing or
  silently ignoring a flag.
- Fraction buys are capped by available cash, so multi-symbol sizing never
  over-commits and no longer rejects the second name.
- Committed a frozen AAPL sample parquet in `docs/` and a reproducibility
  test, so the README results table rebuilds offline with no network.

## 0.3.0

- Position sizing: orders carry `quantity` (shares), `notional` (signed
  dollars) or `fraction` (buys off live equity, sells off position value),
  resolved to whole shares at the fill price with dust rejection. All five
  strategies accept the trio, CLI gains `--notional` / `--fraction`, and
  the default cash is now 100,000 to match the sample comparison.

## 0.2.0

- Short selling: `Portfolio(allow_shorts=True)` opens negative-quantity
  positions, covers FIFO, tracks realized PnL on covers and flips.
- Order types: `market` (default, fills at open), `limit` and `stop` with
  trigger prices. Untriggered orders rest as good-till-cancel; malformed or
  unknown types count as rejected. `win_rate` now scores both long and
  short round-trips.
- Demo data: `scripts/make_demo_data.py` writes deterministic two-ticker
  parquet locally so a fresh clone runs end to end with no downloads.
- Python floor raised to 3.11 for `NotRequired` order keys.

## 0.1.0

- Event-driven engine with next-open fills, five strategies
  (sma, buyhold, rsi, bollinger, donchian), comparison harness and CLI.
- FIFO realized PnL with commission and slippage, Sharpe / max drawdown /
  CAGR / win rate, 95-test pytest suite with ruff-gated CI.
