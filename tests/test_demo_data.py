import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import make_demo_data  # noqa: E402

from backtester.datafeed import DataFeed  # noqa: E402


def test_deterministic_same_seed():
    a = make_demo_data.generate(["DEMO_A"], days=30, seed=7)
    b = make_demo_data.generate(["DEMO_A"], days=30, seed=7)
    pd.testing.assert_frame_equal(a, b)


def test_different_seeds_differ():
    a = make_demo_data.generate(["DEMO_A"], days=30, seed=7)
    b = make_demo_data.generate(["DEMO_A"], days=30, seed=8)
    assert not a["Close"].equals(b["Close"])


def test_schema_and_invariants():
    df = make_demo_data.generate(["DEMO_A", "DEMO_B"], days=30, seed=7)
    assert {"Open", "High", "Low", "Close", "Volume", "Symbol"} <= set(df.columns)
    assert sorted(df["Symbol"].unique().tolist()) == ["DEMO_A", "DEMO_B"]
    assert (df["High"] >= df["Low"]).all()
    assert not df.reset_index().duplicated(subset=["Date", "Symbol"]).any()
    assert len(df) == 60


def test_main_writes_parquet(tmp_path):
    out = str(tmp_path / "demo.parquet")
    make_demo_data.main(["--tickers", "DEMO_A", "--days", "30", "--seed", "7", "--out", out])
    assert os.path.exists(out)
    df = pd.read_parquet(out)
    assert len(df) == 30


def test_demo_loads_in_datafeed_and_backtests(tmp_path):
    out = str(tmp_path / "demo.parquet")
    make_demo_data.main(["--tickers", "DEMO_A,DEMO_B", "--days", "60", "--seed", "7", "--out", out])
    feed = DataFeed(start="2020-01-01", end="2030-01-01", data_source=out)
    assert len(feed) == 120
    assert sorted(feed.symbols) == ["DEMO_A", "DEMO_B"]
    filtered = DataFeed(
        start="2020-01-01", end="2030-01-01", data_source=out, symbols=["DEMO_A"]
    )
    assert len(filtered) == 60
