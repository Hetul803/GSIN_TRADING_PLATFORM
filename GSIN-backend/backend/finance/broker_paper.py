class PaperBroker:
    def __init__(self, equity: float = 10_000.0):
        self.equity = float(equity)
        self.positions = {}

    def buy(self, symbol: str, price: float, qty: float):
        cost = price * qty
        if cost <= self.equity:
            self.equity -= cost
            self.positions[symbol] = self.positions.get(symbol, 0.0) + qty

    def sell(self, symbol: str, price: float, qty: float):
        pos = self.positions.get(symbol, 0.0)
        qty = min(qty, pos)
        self.positions[symbol] = pos - qty
        self.equity += price * qty
