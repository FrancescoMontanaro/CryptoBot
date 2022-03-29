import os
import dotenv
import threading
import indicators
import numpy as np
import pandas as pd
import datetime as dt
from binance.client import Client


# Loading environmental variables
dotenv.load_dotenv()

api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_SECRET')


# Gloabal variables
interval = '1m'
investment = 825
buy_fees = 0.00075
sell_fees = 0.00075
fetch_symbols_data = False
symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "LUNAUSDT", "SOLUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "DOGEUSDT", "ATOMUSDT"]


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
def fetchSymbolsData(symbols, interval, lookback_months, lookback_days, lookback_hours=24) -> None:
    # Defining the end timestamp
    end = dt.datetime.now().timestamp()
    end = int(end * 1000)

    # Defining the start timestamp
    start = dt.datetime.now().timestamp()
    start = int(start * 1000) - (lookback_months * lookback_days * lookback_hours * 60 * 60 * 1000)

    # Fetching the historical data for each symbol in the list
    threads = []
    for symbol in symbols:
        symbol_thread = threading.Thread(target=fetchSymbolData, args=[symbol, interval, start, end])
        threads.append(symbol_thread)
        symbol_thread.start()
        
    for thread in threads:
        thread.join()


# Function to compute the indicators from the historical data of a given symbol
def applyIndicators(df) -> None:
    # Computing the SMA 200 on the close price values
    df["SMA_200"] = indicators.SMA(df["close"], window=200)

    # Removing Null values
    df = df.dropna()


# Function to load the historical data of the given symbols from the local files
def loadData() -> list:
    # Loading the historical data into a list of dataframes
    dataframes = []
    for symbol in symbols:
        file_path = os.path.join('historical_data', f'{symbol}.csv')

        if not os.path.exists(file_path):
            raise Exception(f'No historical data available for symbol {symbol}')

        # Loading the historical data of the selected symbol into a Pandas Dataframe
        df = pd.read_csv(file_path, sep=";")
        df.columns = ['time','open', 'high', 'low', 'close', 'volume']
        df = df.astype({"time": 'int64', "open": 'float64', "high": 'float64', "low": 'float64', "close": 'float64', "volume": 'float64'})

        # Computing the required indicators for the current symbol
        applyIndicators(df)

        dataframes.append({"symbol": symbol, "historical_data": df})

    return dataframes


# Function to test the trading strategy over a selected period
def testStrategy(symbols_data, periods) -> pd.DataFrame:
    transactions = pd.DataFrame()
    
    divergence_threshold = 1.01
    minimum_profit = 0.003
    
    open_position = False
    # Iterating over the selected number of periods
    for i in range(periods):
        if not open_position:
            # Sorting the symbols by SMA 200 - price ratio in reverse order
            symbols_data.sort(key=lambda symbol_data: ((symbol_data["historical_data"].iloc[i].SMA_200 / symbol_data["historical_data"].iloc[i].close)), reverse=True)
            symbol = symbols_data[0]

            # If the SMA 200 - price ratio is over the selected threshold: BUY
            if symbol["historical_data"].iloc[i].SMA_200 / symbol["historical_data"].iloc[i].close > divergence_threshold:
                # Getting the current balance
                balance = transactions.iloc[-1].balance if len(transactions) > 0 else investment

                # Computing the buying price
                buy_price = symbol["historical_data"].iloc[i].SMA_200 / divergence_threshold

                # Appending the transaction into a Pandas Dataframe
                df = pd.DataFrame([[symbol["symbol"], symbol["historical_data"].iloc[i].time, buy_price, -1, -1, -1, -1, balance]])
                df.columns = ['symbol', 'buy_timestamp', 'buy_price', 'sell_timestamp', 'sell_price', 'time_to_sell', 'transaction_profit', 'balance']
                df = df.astype({'buy_timestamp': 'int64', 'sell_timestamp': 'int64', 'time_to_sell': 'int64'})
                    
                transactions = pd.concat([transactions, df], ignore_index=True)

                # Marking the position as opened
                open_position = True

        else:
            # If the current price is such as to guarantee the minimum defined profit: SELL
            if (symbol["historical_data"].iloc[i].high / transactions.iloc[-1].buy_price) > (1 + minimum_profit):
                # Computing the selling price
                sell_price = (1 + minimum_profit) * transactions.iloc[-1].buy_price

                # Computing the net profit of the transaction according to the exchange fees
                transaction_profit = (1 - buy_fees) * transactions.iloc[-1].balance / transactions.iloc[-1].buy_price
                transaction_profit *= (1 - sell_fees) * sell_price
                transaction_profit -= transactions.iloc[-1].balance

                # Updating the latest transaction with the selling information
                idx = transactions.index[-1]
                transactions.loc[idx, 'sell_timestamp'] = symbol["historical_data"].iloc[i].time
                transactions.loc[idx, 'sell_price'] = sell_price
                transactions.loc[idx, 'time_to_sell'] = (symbol["historical_data"].iloc[i].time - transactions.iloc[-1].buy_timestamp) / (60 * 60 * 1000)
                transactions.loc[idx, 'transaction_profit'] = transaction_profit
                transactions.loc[idx, 'balance'] += transaction_profit

                # Marking the position as not opened
                open_position = False

        print(f'\r{i+1}/{periods} Periods tested...', end='')

    # If the latest transaction is incomplete, it is assumed to sell during the latest interval
    if transactions.iloc[-1].sell_timestamp == -1:
        # Computing the selling price
        sell_price = symbol["historical_data"].iloc[-1].close

        # Computing the net profit of the transaction according to the exchange fees
        transaction_profit = (1 - buy_fees) * transactions.iloc[-1].balance / transactions.iloc[-1].buy_price
        transaction_profit *= (1 - sell_fees) * sell_price
        transaction_profit -= transactions.iloc[-1].balance

        # Updating the latest transaction with the selling information
        idx = transactions.index[-1]
        transactions.loc[idx, 'sell_timestamp'] = symbol["historical_data"].iloc[-1].time
        transactions.loc[idx, 'sell_price'] = sell_price
        transactions.loc[idx, 'time_to_sell'] = (symbol["historical_data"].iloc[-1].time - transactions.iloc[-1].buy_timestamp) / (60 * 60 * 1000)
        transactions.loc[idx, 'transaction_profit'] = transaction_profit
        transactions.loc[idx, 'balance'] += transaction_profit

    return transactions


if __name__ == "__main__":
    # Fetching the symbols' historical data from the Binance API
    if fetch_symbols_data:
        client = Client(api_key=api_key, api_secret=api_secret)
        fetchSymbolsData(symbols=symbols, interval=interval, lookback_months=12, lookback_days=30)

    # Loading the historical data from the local files
    dataframes = loadData()

    # Backtesting the strategy on the available histaorical data
    periods = len(dataframes[0]["historical_data"])
    transactions = testStrategy(dataframes, periods)

    # Computing the winnig rate
    winning_rate = len(transactions.loc[transactions["transaction_profit"] > 0]) / len(transactions)
    winning_rate = round((winning_rate * 100), 4)

    # Extracting the total profit obtained
    percentage_profit = (transactions.iloc[-1].balance / investment) - 1
    percentage_profit = round((percentage_profit * 100), 4)
    total_profit = round((transactions.iloc[-1].balance - investment), 4)

    # Extracting the time information
    mean__time_to_sell = np.mean(transactions.time_to_sell)
    mean__time_to_sell = parseTime(mean__time_to_sell)

    min__time_to_sell = np.min(transactions.time_to_sell)
    min__time_to_sell = parseTime(min__time_to_sell)

    max__time_to_sell = np.max(transactions.time_to_sell)
    max__time_to_sell = parseTime(max__time_to_sell)

    # Displaying results
    print(f'\n{transactions}')
    print("--------------------------------------------------------------------")
    print(f'Winning rate --> {winning_rate}%')
    print(f'Total profit --> {total_profit}$ ({percentage_profit}%)')
    print(f'Time to sell(hh:mm) --> Mean: {mean__time_to_sell} | Min: {min__time_to_sell} | Max: {max__time_to_sell}')
    print("--------------------------------------------------------------------")