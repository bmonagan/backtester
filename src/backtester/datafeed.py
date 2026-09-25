# datafeed.py
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator, Optional

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
    def __init__(self, symbol: str, start: datetime, end: datetime):
        self.symbol = symbol
        self.start = start
        self.end = end
        self._data = self._load()  # from Parquet/Postgres

    def _load(self):
        raise NotImplementedError

    def __iter__(self) -> Iterator[Bar]:
        for row in self._data:
            yield row

    def peek_next(self) -> Optional[Bar]:
        """Used by the engine to fill orders at next bar's open."""
        ...
