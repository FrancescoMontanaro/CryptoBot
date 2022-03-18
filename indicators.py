import pandas as pd


# Function to compute the Exponential Moving Average indicator for a given symbol
def EMA(close_prices, window) -> pd.Series:
    # Computing the exponential moving average with the selceted window
    ema = close_prices.ewm(com=window-1, adjust=False).mean()

    return ema


# Function to compute the RSI indicator for a given symbol
def RSI(close_prices, window) -> pd.Series:
    delta = close_prices.diff()
    up = delta.clip(lower=0)
    down = - 1 * delta.clip(upper=0)

    # Computing the exponential moving average
    ema_up = up.ewm(com=window-1, adjust=False).mean()
    ema_down = down.ewm(com=window-1, adjust=False).mean()

    # Computing the relative strength index
    relative_strength = ema_up / ema_down
    rsi = round((100.0 - (100.0 / (1.0 + relative_strength))), 2)

    return rsi


# Function to compute the MACD indicator for a given symbol
def MACD(close_prices) -> tuple:
    # Computing the exponential moving averages
    ema_12 = close_prices.ewm(com=11, adjust=False).mean()
    ema_26 = close_prices.ewm(com=25, adjust=False).mean()

    # Computing the MACD
    macd = ema_12 - ema_26

    # Computing the signal line
    signal = macd.ewm(span=8, adjust=False).mean()

    return macd, signal