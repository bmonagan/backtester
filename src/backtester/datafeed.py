# datafeed.py
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator
import pandas as pd


@dataclass
class Bar:
    # May need to add symbol to the bar at some point if i want to do multiple tickers, but not right now.
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class DataFeed:
    def __init__(self, symbol: str, start: datetime, end: datetime, data_source: str):
        self.symbol = symbol
        self.start = start
        self.end = end
        self.data_source = data_source
        self.bars = self._load()
        self._index_by_date = {bar.timestamp: i for i, bar in enumerate(self.bars)}

    def _load(self) -> list[Bar]:
        df = pd.read_parquet(self.data_source).sort_index()
        df = df.loc[self.start:self.end]
        assert not df.empty, "DataFrame is empty"
        return [
            Bar(timestamp=row.Index, open=row.Open, high=row.High, low=row.Low, close=row.Close, volume=row.Volume)
            for row in df.itertuples()
        ]

    def get_index(self, date) -> int | None:
        return self._index_by_date.get(date)

    def peek_next(self, date) -> Bar | None:
        idx = self.get_index(date)
        if idx is None or idx + 1 >= len(self.bars):
            return None
        return self.bars[idx + 1]

    def __len__(self) -> int:
        return len(self.bars)

    def __getitem__(self, i):
        return self.bars[i]

    def __iter__(self) -> Iterator[Bar]:
        return iter(self.bars)

    def __contains__(self, date) -> bool:
        return date in self._index_by_date
