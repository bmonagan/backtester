import yfinance as yf
import pandas as pd

# import data
df = yf.download("AAPL", start="2020-01-01", end="2024-01-01", interval="1d")

# flatten columns: single ticker, so the Ticker level is redundant
df.columns = df.columns.droplevel("Ticker")   # -> Close, High, Low, Open, Volume

# sanity checks
print(df.isna().sum())                     # missing values
assert df.index.is_monotonic_increasing    # sorted by time
assert not df.index.duplicated().any()     # no duplicate dates
assert (df["High"] >= df["Low"]).all()     # basic OHLC consistency

df.to_parquet("data/AAPL_1d.parquet")
df = pd.read_parquet("data/AAPL_1d.parquet")
