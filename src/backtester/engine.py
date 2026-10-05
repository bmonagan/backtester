# engine.py
from portfolio import Portfolio 
class BacktestEngine:
    def __init__(self, feed: DataFeed, strategy: Strategy, starting_cash: float):
        self.feed = feed
        self.strategy = strategy
        self.portfolio = Portfolio(starting_cash)
        self.history: list[Bar] = []

    def run(self) -> Portfolio:
        last_fast = last_slow = None
        for bar in self.feed:
            self.history.append(bar)
            
            # Long term for multi ticker testing would need to change how this part operates.  
            self.portfolio.mark_to_market(bar.timestamp, self.history)  # mark BEFORE filling

            order, last_fast, last_slow = self.strategy.on_bar(
                bar, self.history, self.portfolio, last_fast, last_slow
            )
            if order:
                print(order, last_fast, last_slow)
                nxt = self.feed.peek_next(bar.timestamp)
                if nxt is not None:  # last bar: drop the unfillable order
                    self.portfolio.execute_order(
                        nxt.timestamp, order["symbol"], order["quantity"], nxt.open
                    )
        return self.portfolio
