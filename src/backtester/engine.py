# engine.py
class BacktestEngine:
    def __init__(self, feed: DataFeed, strategy: Strategy, starting_cash: float):
        self.feed = feed
        self.strategy = strategy
        self.portfolio = Portfolio(starting_cash)
        self.history: list[Bar] = []

    def run(self) -> Portfolio:
        for bar in self.feed:
            self.history.append(bar)
            order = self.strategy.on_bar(bar, self.history, self.portfolio)
            if order:
                fill_price = self.feed.peek_next().open  # avoid lookahead bias
                self.portfolio.execute_order(bar.timestamp, order["symbol"], order["quantity"], fill_price)
            self.portfolio.mark_to_market(bar.timestamp, {bar.symbol: bar.close})
        return self.portfolio
