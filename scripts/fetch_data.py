import yfinance as yf
from src.datafeed import databar

# import data
df = yf.download("AAPL", start="2020-01-01", end="2024-01-01", interval="1d")

# sanity checks 
df.isna().sum()           # missing values
df.index.is_monotonic_increasing   # sorted by time
df.index.duplicated().any()        # duplicate dates
(df["High"] >= df["Low"]).all()    # basic OHLC consistency
df.to_parquet("data/cache/AAPL_1d.parquet")
df = pd.read_parquet("data/cache/AAPL_1d.parquet")
