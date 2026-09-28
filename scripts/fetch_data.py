import yfinance as yf

df = yf.download("AAPL", start="2020-01-01", end="2024-01-01", interval="1d")

print(df)
