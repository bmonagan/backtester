from datafeed import DataFeed  
def main():
    data_source = "data/AAPL_1d.parquet"
    main_feed = DataFeed(symbol = "aapl", start="2020-01-01", end="2024-01-01", data_source = data_source)
    print(main_feed._data) 



if __name__ == "__main__":
    main()
