import argparse
import os

import yfinance as yf


def fetch(symbol: str, start: str, end: str, interval: str, out: str | None = None) -> str:
    df = yf.download(symbol, start=start, end=end, interval=interval)

    # flatten multi-index columns for single ticker
    if hasattr(df.columns, "droplevel"):
        try:
            df.columns = df.columns.droplevel("Ticker")
        except (KeyError, ValueError):
            pass

    df["Symbol"] = symbol

    print(df.isna().sum())
    assert df.index.is_monotonic_increasing
    assert not df.index.duplicated().any()
    assert (df["High"] >= df["Low"]).all()

    out = out or f"data/{symbol}_1d.parquet"
    out_dir = os.path.dirname(out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    df.to_parquet(out)
    print(df.head())
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="AAPL")
    p.add_argument("--start", default="2020-01-01")
    p.add_argument("--end", default="2024-01-01")
    p.add_argument("--interval", default="1d")
    p.add_argument("--out", default=None)
    args = p.parse_args()
    fetch(args.symbol, args.start, args.end, args.interval, args.out)
