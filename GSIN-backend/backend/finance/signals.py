from .backtester import load_aapl, recent_signals

def get_recent_signals():
    df = load_aapl()
    return recent_signals(df, lookback=20)
