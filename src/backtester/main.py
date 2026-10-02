from datafeed import DataFeed
from strategy import SmaCrossoverStrategy
from engine import BacktestEngine


def main():
    config = {"fast_window": 20, "slow_window": 50}
    data_source = "data/AAPL_1d.parquet"
    start_day = "2020-01-01"
    end_day = "2024-01-01"
    starting_cash = 100000.00
    main_feed = DataFeed(symbol = "aapl", start=start_day, end= end_day, data_source = data_source)
    strategy = SmaCrossoverStrategy(**config)
    engine = BacktestEngine(feed=main_feed,strategy=strategy,starting_cash=starting_cash)

    
     



if __name__ == "__main__":
    main()
