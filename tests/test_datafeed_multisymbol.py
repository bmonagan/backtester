import pandas as pd
import pytest

from datafeed import DataFeed


def _make_multi(tmp_path):
    idx = pd.date_range("2020-01-02", periods=3, freq="D")
    frames = []
    for sym, base in [("AAPL", 10.0), ("MSFT", 20.0)]:
        df = pd.DataFrame(
            {
                "Open": [base, base + 1, base + 2],
                "High": [base, base + 1, base + 2],
                "Low": [base, base + 1, base + 2],
                "Close": [base, base + 1, base + 2],
                "Volume": [100, 100, 100],
                "Symbol": [sym] * 3,
            },
            index=idx,
        )
        frames.append(df)
    full = pd.concat(frames).sort_index()
    path = str(tmp_path / "multi.parquet")
    full.to_parquet(path)
    return path


def test_multi_loads_time_major(tmp_path):
    path = _make_multi(tmp_path)
    feed = DataFeed(start="2020-01-01", end="2020-12-31", data_source=path)
    assert len(feed) == 6
    assert sorted(feed.symbols) == ["AAPL", "MSFT"]
    # same date, AAPL before MSFT
    assert feed[0].timestamp == feed[1].timestamp
    assert feed[0].symbol == "AAPL"
    assert feed[1].symbol == "MSFT"


def test_multi_symbol_filter(tmp_path):
    path = _make_multi(tmp_path)
    feed = DataFeed(start="2020-01-01", end="2020-12-31", data_source=path, symbols=["MSFT"])
    assert len(feed) == 3
    assert all(b.symbol == "MSFT" for b in feed)


def test_multi_missing_symbol_raises(tmp_path):
    path = _make_multi(tmp_path)
    with pytest.raises(ValueError):
        DataFeed(start="2020-01-01", end="2020-12-31", data_source=path, symbols=["GOOG"])


def test_missing_ohlc_raises(tmp_path):
    idx = pd.date_range("2020-01-02", periods=2, freq="D")
    df = pd.DataFrame({"Close": [1.0, 2.0], "Symbol": ["AAPL", "AAPL"]}, index=idx)
    path = str(tmp_path / "bad.parquet")
    df.to_parquet(path)
    with pytest.raises(ValueError):
        DataFeed(start="2020-01-01", end="2020-12-31", data_source=path)


def test_missing_symbol_infers_from_file_or_param(tmp_path):
    idx = pd.date_range("2020-01-02", periods=2, freq="D")
    df = pd.DataFrame(
        {"Open": [1.0, 2.0], "High": [1.0, 2.0], "Low": [1.0, 2.0], "Close": [1.0, 2.0], "Volume": [10, 10]},
        index=idx,
    )
    path = str(tmp_path / "AAPL_1d.parquet")
    df.to_parquet(path)
    feed = DataFeed(start="2020-01-01", end="2020-12-31", data_source=path)
    assert all(b.symbol == "AAPL" for b in feed)
