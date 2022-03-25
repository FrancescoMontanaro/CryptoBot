import os
import dotenv
import indicators
import numpy as np
import pandas as pd
import datetime as dt
from binance.client import Client


dotenv.load_dotenv()

# Gloabal variables
fees = 0.0015
interval = '1m'
lookback_days = 30
transaction_profit = 0.003
fetch_symbols_data = False
api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_SECRET')
symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "LUNAUSDT", "SOLUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "DOGEUSDT", "ATOMUSDT", "SHIBUSDT"]


# Function to convert a timestamp into the hh:mm format
def parseTime(time) -> str:
    result = '{0:02.0f}:{1:02.0f}'.format(*divmod(time * 60, 60))
    return result


# Function to fetch the historical data for a give symbol
def fetchSymbolData(symbol, interval, start, end) -> None:
    # Fetching the historical data from the Binance API
    historical_data = client.get_historical_klines(symbol, interval, start_str=start, end_str=end)
    historical_data = [[data[i] for i in range(6)] for data in historical_data]

    # Saving the historical data of the given symbol into a local CSV file
    file_path = os.path.join('historical_data', f'{symbol}.csv')
    open(file_path, 'w').close()

    with open(file_path, 'a') as f:
        for data in historical_data:
            data_string = ""
            for i in range(len(data)):
                data_string += f'{data[i]};' if i < (len(data) -1) else data[i]

            f.write(f'{data_string}\n')

    print(f'Historical data loaded for symbol : {symbol}')


# Function to fetch the historical data of a given list of symbols
def fetchSymbolsData(symbols, interval, lookback_days, lookback_hours=24) -> None:
    # End timestamp
    end = dt.datetime.now().timestamp()
    end = int(end * 1000)

    # Start timestamp
    start = dt.datetime.now().timestamp()
    start = int(start * 1000) - (lookback_days * lookback_hours * 60 * 60 * 1000)

    for symbol in symbols:
        try:
            fetchSymbolData(symbol=symbol, interval=interval, start=start, end=end)
        except Exception as e:
            print(f'Error loading {symbol} historical data --> {str(e)}')


# Function to compute the indicators from the historical data of a given symbol
def applyIndicators(df) -> None:
    # Computing the SMA 200 on the close price values
    df["SMA_200"] = df["close"].rolling(200).mean()

    # Computing the RSI 14 on the close price values
    df["RSI"] = indicators.RSI(df["close"], window=14)

    # Computing the Bollinger Bands indicator
    df["BOOL_UP"], df["BOOL_DOWN"] = indicators.BOLL(df["close"])


# Function to load the historical data of the given symbols from the local files
def loadData() -> list:
    # Loading the historical data into a list of dataframes
    dataframes = []
    for symbol in symbols:
        file_path = os.path.join('historical_data', f'{symbol}.csv')

        if not os.path.exists(file_path):
            raise Exception(f'No historical data available for symbol {symbol}')

        df = pd.read_csv(file_path, sep=";")
        df.columns = ['time','open', 'high', 'low', 'close', 'volume']
        df = df.astype({"time": 'int64', "open": 'float64', "high": 'float64', "low": 'float64', "close": 'float64', "volume": 'float64'})

        # Computing the required indicators for the current symbol
        applyIndicators(df)

        dataframes.append({"symbol": symbol, "historical_data": df})

    return dataframes


# Function to apply and test the trading strategy on the given period
def applyStrategy(symbols_data):
    periods = len(symbols_data[0]["historical_data"])

    open_position = False
    open_symbol_df = None

    transactions = pd.DataFrame()

    for i in range(periods):
        if not open_position:
            matching_conditions = []
            for symbol_data in symbols_data:
                if (symbol_data["historical_data"].iloc[i].SMA_200 / symbol_data["historical_data"].iloc[i].close) >= 1.01:
                    matching_conditions.append(symbol_data)

            if len(matching_conditions) > 0:
                matching_conditions.sort(key=lambda symbol_data: (symbol_data["historical_data"].iloc[i].SMA_200 / symbol_data["historical_data"].iloc[i].close), reverse=True)

                selected_symbol = matching_conditions[0]

                df = pd.DataFrame([[selected_symbol["symbol"], selected_symbol["historical_data"].iloc[i].time, selected_symbol["historical_data"].iloc[i].close, None, None, None, None]])
                df.columns = ['symbol', 'buy_timestamp', 'buy_price', 'sell_timestamp', 'sell_price', 'transaction_profit', 'opening_time']
                df = df.astype({'buy_timestamp': 'int64'})
                
                transactions = pd.concat([transactions, df], ignore_index=True)

                open_position = True
                open_symbol_df = selected_symbol

        else:
            if open_symbol_df["historical_data"].iloc[i].close >= (1 + transaction_profit) * transactions.iloc[-1].buy_price:
                idx = transactions.index[-1]

                transactions.loc[idx, 'sell_timestamp'] = open_symbol_df["historical_data"].iloc[i].time
                transactions.loc[idx, 'sell_price'] = open_symbol_df["historical_data"].iloc[i].close
                transactions.loc[idx, 'transaction_profit'] = (1 - (fees / transaction_profit)) * transaction_profit
                transactions.loc[idx, 'opening_time'] = (open_symbol_df["historical_data"].iloc[i].time - transactions.iloc[-1].buy_timestamp) / (60 * 60 * 1000)
                transactions = transactions.astype({'sell_timestamp': 'int64'})
                
                open_position = False
                open_symbol_df = None

    if transactions.iloc[-1].sell_timestamp is None:
        print(f'Transaction blocked in open position since : {transactions.iloc[-1].buy_timestamp}')
        transactions = transactions[:-1]

    return transactions


if __name__ == "__main__":
    # Fetching the symbols' historical data from the Binance API
    if fetch_symbols_data:
        client = Client(api_key=api_key, api_secret=api_secret)
        fetchSymbolsData(symbols=symbols, interval=interval, lookback_days=lookback_days)

    # Loading the historical data from the local files
    dataframes = loadData()

    # Backtesting the strategy on the available histaorical data
    transactions = applyStrategy(dataframes)

    # Extracting the evaluation parameters
    num_transactions = len(transactions)
    transactions_per_day = round((len(transactions) / lookback_days), 4)
    total_profit = round((np.sum(transactions.transaction_profit.values) * 100), 4)
    daily_profit = round((total_profit / lookback_days), 4)
    mean_sell_time = np.mean(transactions.opening_time.values)
    min_sell_time = np.min(transactions.opening_time.values)
    max_sell_time = np.max(transactions.opening_time.values)

    # Displaying results
    print(f'BACKTESTING STRATEGY FOR {lookback_days} DAYS PERIOD')
    print("-------------------------------------------------------")
    print(f'Total profit --> {total_profit}% ({daily_profit}%/day)')
    print(f'Buy/Sell transactions count --> {len(transactions)} ({transactions_per_day} trans./day)')
    print(f'Time to sell(hh:mm) --> Average: {parseTime(mean_sell_time)} | Minimum: {parseTime(min_sell_time)} | Maximum: {parseTime(max_sell_time)}')
    print("-------------------------------------------------------")