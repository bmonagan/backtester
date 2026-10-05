import pandas as pd
import yfinance as yf

symbol = "AAPL"

# import data
df = yf.download(symbol, start="2020-01-01", end="2024-01-01", interval="1d")

# flatten columns: single ticker, so the Ticker level is redundant
df.columns = df.columns.droplevel("Ticker")   # -> Close, High, Low, Open, Volume

# --- ADD SYMBOL HERE ---
df["Symbol"] = symbol

# sanity checks
print(df.isna().sum())                     # missing values
assert df.index.is_monotonic_increasing    # sorted by time
assert not df.index.duplicated().any()     # no duplicate dates
assert (df["High"] >= df["Low"]).all()     # basic OHLC consistency

# save to parquet
df.to_parquet(f"data/{symbol}_1d.parquet")

# load back (also note fixing the typo ".paquet" -> ".parquet")
df = pd.read_parquet(f"data/{symbol}_1d.parquet")
print(df.head())
