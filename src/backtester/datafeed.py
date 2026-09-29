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
    """Yields Bars one at a time — no peeking ahead."""
    def __init__(self, symbol: str, start: datetime, end: datetime, data_source: str):
        self.data_source = data_source 
        self._data = self._load()  # from Parquet/Postgres
        self._index_by_date = {bar.date: i for i, bar in enumerate(self.bars)}

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
    def peek_next(self, current_bar:Bar) -> Optional[Bar]:
        """Used by the engine to fill orders at next bar's open."""
        ...
        if (current_bar)
