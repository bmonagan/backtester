"""Generate deterministic demo OHLCV parquet for local runs.

Nothing here touches the network. Output stays under data/ (git-ignored).
"""

import argparse

import numpy as np
import pandas as pd


def make_frame(ticker: str, days: int, seed: int, start_price: float) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    # mild upward drift with realistic daily vol, plus a slow sine regime
    drift = 0.0004
    vol = 0.015
    rets = drift + vol * rng.standard_normal(days)
    rets += 0.004 * np.sin(np.linspace(0, 6 * np.pi, days))
    closes = start_price * np.exp(np.cumsum(rets))
    spread = np.abs(rng.standard_normal(days)) * closes * 0.004
    opens = np.concatenate([[start_price], closes[:-1]])
    highs = np.maximum(opens, closes) + spread
    lows = np.minimum(opens, closes) - spread
    idx = pd.date_range("2021-01-03", periods=days, freq="B")
    df = pd.DataFrame(
        {
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": closes,
            "Volume": rng.integers(1_000_000, 5_000_000, size=days),
            "Symbol": ticker,
        },
        index=idx,
    )
    df.index.name = "Date"
    assert (df["High"] >= df["Low"]).all()
    assert not df.index.duplicated().any()
    return df


def generate(tickers, days: int, seed: int) -> pd.DataFrame:
    frames = [
        make_frame(t, days, seed + i, 100.0 + 50.0 * i)
        for i, t in enumerate(tickers)
    ]
    full = pd.concat(frames).sort_index()
    return full


def main(argv=None) -> str:
    p = argparse.ArgumentParser(description="make deterministic demo parquet")
    p.add_argument("--tickers", default="DEMO_A,DEMO_B")
    p.add_argument("--days", type=int, default=756)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", default="data/demo_1d.parquet")
    args = p.parse_args(argv)
    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    df = generate(tickers, args.days, args.seed)
    df.to_parquet(args.out)
    print(f"wrote {len(df)} rows for {tickers} to {args.out}")
    return args.out


if __name__ == "__main__":
    main()
