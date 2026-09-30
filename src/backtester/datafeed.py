# datafeed.py
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator, Optional
import pandas as pd

@dataclass
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

class DataFeed:
    def __init__(self, symbol: str, start: datetime, end: datetime, data_source: str):
        self.data_source = data_source 
        self._bars = self._load()  # from Parquet/Postgres
        self._index_by_date = {bar.date: i for i, bar in enumerate(self._bars)}

    def _load(self):
        # Semi Placeholder function. Not sure what the data source will going forward
        # will try to keep it modular so it will be open to more data sources.
        df = pd.read_parquet(self.data_source).sort_index()
        assert not df.empty, "DatatFrame is empty"
        bars = [
                Bar(timestamp=row.Index, open=row.Open, high=row.High, low=row.Low, close=row.Close, volume=row.Volume)
                for row in df.itertuples()
               ]
        return bars
     def get_index(self, date) -> int | None:
        return self._index_by_date.get(date)

    def peek_next(self, date) -> DataBar | None:
        # Date is a reliable check because we're not checking trades
        # We are checking prices at distinct points in time
        idx = self.get_index(date)
        if idx is None or idx + 1 >= len(self.bars):
            return None
        return self.bars[idx + 1]
