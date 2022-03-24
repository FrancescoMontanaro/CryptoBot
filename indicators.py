import pandas as pd


# Function to compute the Simple Moving Average indicator for a given symbol
def SMA(close_prices, window=50) -> pd.Series:
    # Computing the simple moving average with the selceted window
    sma = close_prices.rolling(window).mean()

    return sma


# Function to compute the Exponential Moving Average indicator for a given symbol
def EMA(close_prices, window=50) -> pd.Series:
    # Computing the exponential moving average with the selceted window
    ema = close_prices.ewm(span=window, adjust=False).mean()

    return ema


# Function to compute the RSI indicator for a given symbol
def RSI(close_prices, window=14) -> pd.Series:
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
def MACD(close_prices, windows=[12, 26, 9]) -> tuple:
    # Computing the exponential moving averages
    ema_12 = close_prices.ewm(span=windows[0], adjust=False).mean()
    ema_26 = close_prices.ewm(span=windows[1], adjust=False).mean()

    # Computing the MACD
    macd = ema_12 - ema_26

    # Computing the signal line
    macd_signal = macd.ewm(span=windows[2], adjust=False).mean()

    # Computing the divregence between the MACD anc the signal line
    divergence = macd - macd_signal

    return macd, macd_signal, divergence