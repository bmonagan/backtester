"""Guard the committed sample dataset and published results table.

The docs/ sample parquet and docs/ compare CSV are shipped so the README
table reproduces offline. This test recomputes the table from the sample
and checks it still matches the committed CSV.
"""

import csv
import os

from backtester.compare import compare
from backtester.datafeed import DataFeed

HERE = os.path.dirname(__file__)
SAMPLE = os.path.join(HERE, "..", "docs", "sample-aapl-1d-2020-2024.parquet")
RESULTS = os.path.join(HERE, "..", "docs", "compare-aapl-2020-2024.csv")
NAMES = ["sma", "buyhold", "rsi", "bollinger", "donchian"]
NUMERIC = ("final_equity", "sharpe", "max_drawdown", "cagr", "win_rate", "realized_pnl")


def _load_committed():
    with open(RESULTS) as f:
        return list(csv.DictReader(f))


def test_sample_and_results_are_committed():
    assert os.path.exists(SAMPLE), "sample parquet missing from docs/"
    assert os.path.exists(RESULTS), "results csv missing from docs/"


def test_sample_reproduces_results():
    committed = {r["strategy"]: r for r in _load_committed()}

    def factory():
        return DataFeed(
            start="2020-01-01", end="2024-01-01", data_source=SAMPLE,
        )

    # mirror the CLI defaults the committed CSV was generated with
    strategy_kwargs = {
        "sma": {"fast_period": 20, "slow_period": 50, "quantity": 100},
        "buyhold": {"quantity": 100},
        "rsi": {"period": 14, "oversold": 30, "overbought": 70, "quantity": 100},
        "bollinger": {"period": 20, "num_std": 2.0, "quantity": 100},
        "donchian": {"entry_period": 20, "exit_period": 10, "quantity": 100},
    }
    rows = compare(
        NAMES, factory, starting_cash=100000.0,
        strategy_kwargs=strategy_kwargs,
    )
    for row in rows:
        ref = committed[row["strategy"]]
        assert int(row["trades"]) == int(ref["trades"])
        for key in NUMERIC:
            assert float(row[key]) == float(ref[key]), (
                f"{row['strategy']}.{key}: {row[key]} != {ref[key]}"
            )
