from datafeed import DataFeed
from strategy import SmaCrossoverStrategy
from engine import BacktestEngine


def main():
    # Dataengine variables
    data_source = "data/AAPL_1d.parquet"
    start_day = "2020-01-01"
    end_day = "2024-01-01"
    starting_cash = 1000000.00
    # Strategy Variables 
    fast= 20 
    slow= 50 
    quantity= 100

    main_feed = DataFeed(start=start_day, end= end_day, data_source = data_source)
    strategy = SmaCrossoverStrategy(fast_period=fast, slow_period=slow, quantity=quantity)
    engine = BacktestEngine(feed=main_feed,strategy=strategy,starting_cash=starting_cash)
    

    engine.run()
    print("Final portfolio:")
    print(engine.portfolio)
    print("Final Equity:")
    print(round(engine.portfolio.current_equity(engine.latest_prices),2))
    #print("Trade Log")
    #print(engine.portfolio.trade_log)


    
     



if __name__ == "__main__":
    main()
