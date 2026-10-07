# datafeed.py
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator

import pandas as pd


@dataclass
class Bar:
    timestamp: object
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float


REQUIRED_COLS = {"Open", "High", "Low", "Close", "Volume"}


class DataFeed:
    def __init__(
        self, start: str | datetime, end: str | datetime,
        data_source: str, symbols: list[str] | str | None = None,
    ):
        self.start = start
        self.end = end
        self.data_source = data_source
        if isinstance(symbols, str):
            symbols = [symbols]
        self.requested_symbols = symbols
        self.bars = self._load()
        self.symbols: list[str] = sorted({b.symbol for b in self.bars})
        self._index: dict[tuple[str, object], int] = {
            (b.symbol, b.timestamp): i for i, b in enumerate(self.bars)
        }
        self._dates = {b.timestamp for b in self.bars}

    def _load(self) -> list[Bar]:
        df = pd.read_parquet(self.data_source).sort_index()
        df = df.loc[self.start:self.end]
        if df.empty:
            raise ValueError(
                f"No bars in [{self.start}:{self.end}] for {self.data_source}"
            )

        missing = REQUIRED_COLS - set(df.columns)
        if missing:
            raise ValueError(
                f"Missing OHLCV columns {sorted(missing)} in {self.data_source}"
            )

        # symbol handling: use column if present, else infer or require symbols param
        if "Symbol" not in df.columns:
            inferred = self._infer_symbol()
            if self.requested_symbols and len(self.requested_symbols) == 1:
                df = df.copy()
                df["Symbol"] = self.requested_symbols[0]
            elif inferred:
                df = df.copy()
                df["Symbol"] = inferred
            else:
                raise ValueError(
                    f"No Symbol column in {self.data_source}, pass symbols=[...]"
                )

        if self.requested_symbols:
            df = df[df["Symbol"].isin(self.requested_symbols)]
            if df.empty:
                raise ValueError(
                    f"No bars for {self.requested_symbols} in "
                    f"[{self.start}:{self.end}]"
                )

        bars = [
            Bar(
                timestamp=row.Index, symbol=row.Symbol, open=row.Open,
                high=row.High, low=row.Low, close=row.Close,
                volume=row.Volume,
            )
            for row in df.itertuples()
        ]
        # deterministic time-major, symbol-minor order for multi-ticker
        bars.sort(key=lambda b: (b.timestamp, b.symbol))
        if not bars:
            raise ValueError(
                f"No bars in [{self.start}:{self.end}] for {self.data_source}"
            )
        return bars

    def _infer_symbol(self) -> str | None:
        base = os.path.basename(str(self.data_source))
        # AAPL_1d.parquet -> AAPL
        stem = base.split(".")[0]
        if "_" in stem:
            return stem.split("_")[0] or None
        return None

    def get_index(self, date, symbol: str | None = None) -> int | None:
        if symbol is None:
            if len(getattr(self, "symbols", [])) == 1:
                symbol = self.symbols[0]
            else:
                # backward compat: fall back to date-only lookup for single-bar feeds
                # try any symbol match
                for (s, d), i in self._index.items():
                    if d == date:
                        return i
                return None
        return self._index.get((symbol, date))

    def peek_next(self, date, symbol: str | None = None) -> Bar | None:
        idx = self.get_index(date, symbol=symbol)
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
        return date in self._dates
