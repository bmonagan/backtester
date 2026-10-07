import pandas as pd
import pytest

from backtester.datafeed import DataFeed, Bar

REAL_DATA = "data/AAPL_1d.parquet"


def _make_parquet(tmp_path, closes=(10.0, 11.0, 12.0)):
    idx = pd.date_range("2020-01-02", periods=len(closes), freq="D")
    df = pd.DataFrame(
        {
            "Open": closes,
            "High": closes,
            "Low": closes,
            "Close": closes,
            "Volume": [100] * len(closes),
            "Symbol": ["AAPL"] * len(closes),
        },
        index=idx,
    )
    path = str(tmp_path / "synth.parquet")
    df.to_parquet(path)
    return path


def test_load_synthetic_feed(tmp_path):
    path = _make_parquet(tmp_path)
    feed = DataFeed(start="2020-01-01", end="2020-12-31", data_source=path)
    assert len(feed) == 3
    bar = feed[0]
    assert isinstance(bar, Bar)
    assert bar.symbol == "AAPL"
    assert bar.close == pytest.approx(10.0)


def test_start_end_filtering(tmp_path):
    path = _make_parquet(tmp_path, closes=(1.0, 2.0, 3.0, 4.0, 5.0))
    feed = DataFeed(start="2020-01-02", end="2020-01-03", data_source=path)
    assert len(feed) == 2
    assert feed[0].close == pytest.approx(1.0)
    assert feed[1].close == pytest.approx(2.0)


def test_empty_slice_raises(tmp_path):
    path = _make_parquet(tmp_path)
    with pytest.raises(ValueError):
        DataFeed(start="2030-01-01", end="2030-12-31", data_source=path)


def test_get_index_peek_next_contains_iter(tmp_path):
    path = _make_parquet(tmp_path)
    feed = DataFeed(start="2020-01-01", end="2020-12-31", data_source=path)
    first = feed[0]
    assert feed.get_index(first.timestamp) == 0
    assert feed.get_index("not-a-date") is None
    nxt = feed.peek_next(first.timestamp)
    assert nxt is not None
    assert nxt.close == pytest.approx(11.0)
    assert feed.peek_next(feed[-1].timestamp) is None
    assert first.timestamp in feed
    assert "not-a-date" not in feed
    assert [b.close for b in feed] == pytest.approx([10.0, 11.0, 12.0])


def test_real_parquet_loads():
    feed = DataFeed(start="2020-01-01", end="2020-01-31", data_source=REAL_DATA)
    assert len(feed) > 0
    assert all(b.symbol == "AAPL" for b in feed)
