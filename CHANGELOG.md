# changelog

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
