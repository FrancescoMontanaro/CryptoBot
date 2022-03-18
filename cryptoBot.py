import math
import time
import utils
import threading
import indicators
import datetime as dt
import concurrent.futures
from binance.client import Client
from dataCollector import DataCollector


class CryptoBot:
    """ PRIVATE METHODS """
    # Class constructor
    def __init__(self, api_key, api_secret, symbols, minumum_profit, against_symbol="USDT", interval="1m") -> None:
        # Initializing object's attributes
        self.symbols = symbols
        self.against_symbol = against_symbol
        self.minumum_profit = minumum_profit
        self.interval = interval
        self.open_position = False
        self.timeout = 60

        # Instantiating the Binance API Client
        self.client = Client(api_key=api_key, api_secret=api_secret)

        # Instantiating the DataCollector object
        self.data_collector = DataCollector(
            api_key=api_key, 
            api_secret=api_secret, 
            symbols=self.symbols, 
            against_symbol=self.against_symbol, 
            interval=self.interval
        )


    # Function to get the number of decimal digits for a specific symbol
    def __getDecimals(self, symbol) -> tuple:
        # Collecting the information of a symbol
        symbol_info = self.client.get_symbol_info(symbol)

        # Extracting the filters of the symbol
        lot_size = [filter for filter in symbol_info["filters"] if filter["filterType"] == "LOT_SIZE"][0]
        price_filter = [filter for filter in symbol_info["filters"] if filter["filterType"] == "PRICE_FILTER"][0]

        # Extracting the sizes for each filter
        sizes = [lot_size["stepSize"], price_filter["tickSize"]]

        # Computing the number of decimals of each symbol's size
        decimals = []
        for size in sizes:
            filter_decimals = 0
            is_decimal = False
            for c in size:
                if is_decimal is True:
                    filter_decimals += 1
                if c == '1':
                    break
                if c == '.':
                    is_decimal = True

            decimals.append(filter_decimals)

        decimals = tuple(decimals)

        return decimals


    # Function to truncate a number after a specific number of decimals
    def __truncateNumber(self, number, digits) -> float:
        stepper = 10.0 ** digits
        truncated_number = math.trunc(stepper * number) / stepper
        
        return truncated_number
    

    # Function to open a buying order for a specific symbol at a given price
    def __buyOrder(self, symbol, price, amount) -> str:
        # Getting the number of decimals required for the selected symbol
        quantity_decimals, price_decimals = self.__getDecimals(symbol)

        # Rearranging the quantity and the price according to the symbol's rules
        quantity = amount / price
        quantity = self.__truncateNumber(quantity, quantity_decimals)

        price = round(price, price_decimals)
        price = format(price, f'.8f')

        # Creating the buying order
        order = self.client.order_limit_buy(
            symbol=symbol,
            quantity=quantity,
            price=price
        )

        # Extracting order id
        order_id = order["orderId"]

        return order_id


    # Function to open a selling order for a specific symbol at a given price
    def __sellOrder(self, symbol, price, amount) -> str:
        # Getting the number of decimals required for the selected symbol
        quantity_decimals, price_decimals = self.__getDecimals(symbol)

        # Fetching the quantity of the crypto to sell 
        symbol_balance = self.data_collector.getAssetBalance(symbol.replace(self.against_symbol, ""))
        symbol_balance = float(symbol_balance["free"])

        quantity = amount if amount <= symbol_balance else symbol_balance

        # Rearranging the quantity and the price according to the symbol's rules
        quantity = self.__truncateNumber(quantity, quantity_decimals)

        price = round(price, price_decimals)
        price = format(price, f'.8f')

        # Creating the selling order
        order = self.client.order_limit_sell(
            symbol=symbol,
            quantity=quantity,
            price=price
        )

        # Extracting order id
        order_id = order["orderId"]

        return order_id

    
    # Function to compute the required indicators of a given symbol
    def __computeIndicators(self, dataframe) -> tuple:
        # Computing the RSI indicator
        dataframe["RSI"] = indicators.RSI(dataframe["close"], window=14)

        # Computing Exponential moving averages
        dataframe["EMA_50"] = indicators.EMA(dataframe["close"], window=50)
        dataframe["EMA_200"] = indicators.EMA(dataframe["close"], window=200)

        return dataframe


    # Function to collect the data of a symbol and to compute the required inidcators
    def __symbolData(self, symbol) -> dict:
        # Getting the symbol's data from the DataCollector object
        dataframe = self.data_collector.getSymbolData(symbol)

        # Computing the required indicators
        dataframe = self.__computeIndicators(dataframe)

        return {"symbol": symbol, "historical_data": dataframe}


    # Function to collect the data of all the symbols in the list and compute the required inidcators
    def __symbolsData(self) -> list:
        symbols_data = []

        # Fetching the data and computing the indicators for every symbol in the list
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.symbols)) as executor:
            futures = {executor.submit(self.__symbolData, symbol): symbol for symbol in self.symbols}
            for future in concurrent.futures.as_completed(futures):
                symbols_data.append(future.result())

        return symbols_data


    # Function defining the buying strategy
    def __buyingStrategy(self) -> dict:
        # Getting the data of the symbols
        symbols_data = self.__symbolsData()

        increasing_symbols = []
        for symbol_data in symbols_data:
            # Extracting the latest 3 RSI values
            latest_rsi_values = symbol_data["historical_data"]["RSI"].tail(3) 

            # Checking if the latest rsi values are monotonically increasing in the selected range of values
            if latest_rsi_values.is_monotonic_increasing and all(latest_rsi_values.values[:2] < 50) and latest_rsi_values.values[2] >= 50:
                increasing_symbols.append(symbol_data)

        if len(increasing_symbols) > 0:
            # Sorting symbols by their RSI variation
            increasing_symbols.sort(key=lambda increasing_symbol: (increasing_symbol["historical_data"].iloc[-3]["RSI"] / increasing_symbol["historical_data"].iloc[-1]["RSI"]))

            # Selecting the symbol to invest in as the one with the lowest RSI variation
            selected_symbol = increasing_symbols[0]

            return selected_symbol

        else:
            return None


    # Bot's trading process
    def __trade(self) -> None:
        while True:
            ### LOOKING FOR BUYING OPPORTUNITIES ###
            # Looking for a buying opportunity (RSI < threshold)
            buy_opportunity = None
            while buy_opportunity is None:
                buy_opportunity = self.__buyingStrategy()

            # Buy opportunity found
            symbol = buy_opportunity["symbol"]
            rsi = buy_opportunity["historical_data"].iloc[-1]["RSI"]
            buy_price = buy_opportunity["historical_data"].iloc[-1]["close"]

            # Logging operation
            utils.log(f'Buying opportunity found - Symbol: {symbol} | Buying price: {buy_price}{self.against_symbol}')

            ### BUYING PROCESS ###
            # Creating a buying order.
            # If an error occurs, the process restarts by looking for buying opportunities.
            try:
                # Fetching the amount to invest
                investment = self.data_collector.getAssetBalance(self.against_symbol)
                investment = float(investment["free"])

                # Creating the buying order
                buy_order_id = self.__buyOrder(symbol, buy_price, investment)

                # Saving the timestamp in which the buying order has been placed
                creation_time = dt.datetime.now()

                # Logging operation
                utils.log(f'Buying order created - Id: {buy_order_id}')

            except Exception as e:
                utils.log(f'Error creating buying order: {str(e)}')
                continue

            # Checking for buying order fulfillment.
            self.open_position = False
            while not self.open_position:
                # Getting buy order information
                buy_order = self.data_collector.getOrder(buy_order_id)

                # Waiting until the buying order information are available before proceeding
                if buy_order is None:
                    time.sleep(1)
                    continue

                # Order Filled
                if buy_order["status"] == "FILLED" or (buy_order["status"] == "TRADE" and buy_order["filled_quantity"] >= buy_order["quantity"]):
                    try:
                        # Sending a buying notification to the Discord channel
                        utils.sendWebhook(
                            symbol=symbol.replace(self.against_symbol, ""),
                            description=f'Price: **{buy_price} {self.against_symbol}**\nQuantity invested: **{investment} {self.against_symbol}**\nQuantity bought: **{buy_order["quantity"]} {symbol.replace(self.against_symbol, "")}**\nRSI: **{rsi}**',
                            color=6146183
                        )

                        # Logging operation
                        utils.log(f'Buying order filled - Id: {buy_order_id}')

                    except Exception as e:
                        # Logging error
                        utils.log(f'Error sending buying report: {str(e)}')

                    else:
                        # Mark the position as open
                        self.open_position = True

                # if the order is partially filled, checks again the order status by jumping to the next iteration.
                elif buy_order["status"] == "PARTIALLY_FILLED" or (buy_order["status"] == "TRADE" and buy_order["filled_quantity"] < buy_order["quantity"]):
                    time.sleep(1)
                    continue

                # If the order is Rejected, Canceled or Expired, the process restarts by looking for buying opportunities.
                elif buy_order["status"] == "CANCELED" or buy_order["status"] == "REJECTED" or buy_order["status"] == "EXPIRED":
                    # Deleting buy order from the memory
                    self.data_collector.deleteOrder(buy_order_id)

                    # logging operation
                    utils.log(f'Buying order {buy_order["status"].lower()} - Id: {buy_order_id}')
                    
                    break

                else:
                    # Fetching the last RSI value and the price of the symbol
                    symbol_data = self.__symbolData(symbol)

                    # Extracting the current RSI and price of the symbol
                    current_rsi = symbol_data["historical_data"].iloc[-1]["RSI"]
                    current_price = symbol_data["historical_data"].iloc[-1]["close"]

                    # Getting the time elapsed seconds from the creation of the order
                    current_time = dt.datetime.now()
                    elapsed_time = (current_time - creation_time).seconds

                    # If during the fulfillment operation the RSI value decreases while the
                    # last price of the symbol increases, the order is canceled: the previous 
                    # buying condition is no longer the best.
                    if (current_rsi < rsi and  current_price > buy_price) or elapsed_time >= self.timeout:
                        try:
                            # Canceling the order
                            self.client.cancel_order(symbol=symbol, orderId=buy_order["id"])

                        except Exception as e:
                            # Logging error
                            utils.log(f'Error canceling order ({buy_order["id"]}): {str(e)}')

                time.sleep(1)

            ### SELLING PROCESS ###
            sell_order_id = None
            while self.open_position:
                # Creating a selling order.
                # If an error occurs, the process restarts by trying to open another sell order.
                while sell_order_id is None:
                    try:
                        # Computing the sell price according to the desired profit
                        sell_price = buy_price * self.minumum_profit

                        # Creating the selling order
                        sell_order_id = self.__sellOrder(symbol, sell_price, float(buy_order["quantity"]))

                        # Logging operation
                        utils.log(f'Selling order created - Id: {sell_order_id}')

                    except Exception as e:
                        # Logging error
                        utils.log(f'Error creating sell order: {str(e)}')

                        continue

                    finally:
                        time.sleep(1)

                # Fetching sell order information
                sell_order = self.data_collector.getOrder(sell_order_id)

                # Waiting until the selling order information are available before proceeding
                if sell_order is None:
                    time.sleep(1)
                    continue

                # Order Filled
                if sell_order["status"] == "FILLED" or (sell_order["status"] == "TRADE" and sell_order["filled_quantity"] >= sell_order["quantity"]):
                    try:
                        # Fetching the current account balance
                        account_balance = self.data_collector.getAssetBalance(self.against_symbol)
                        account_balance = float(account_balance["free"])

                        # Computing the profit obtained from the transaction
                        profit = round(((account_balance * (sell_price / buy_price)) - account_balance), 3)

                        # Sending a selling notification to the Discord channel
                        utils.sendWebhook(
                            symbol=symbol.replace(self.against_symbol, ""),
                            description=f'Price: **{sell_price} {self.against_symbol}**\nTransaction profit: **{profit} {self.against_symbol}**\nBalance: **{round(account_balance, 3)} {self.against_symbol}**',
                            color=14898529
                        )

                        # Deleting orders from the memory
                        self.data_collector.deleteOrder(buy_order_id)
                        self.data_collector.deleteOrder(sell_order_id)

                        # Logging operation
                        utils.log(f'Selling order filled - Id: {sell_order_id}')

                    except Exception as e:
                        # Logging error
                        utils.log(f'Error sending selling report: {str(e)}')
                        
                    else:
                        # Mark the position as close
                        self.open_position = False

                # if the order is Rejected, Canceled or Expired, the process restarts by trying to open another selling order
                elif sell_order["status"] == "REJECTED" or sell_order["status"] == "EXPIRED":
                    # Deleting sell order from the memory
                    self.data_collector.deleteOrder(sell_order_id)

                    # Mark the selling order as not open
                    sell_order_id = None

                    # Logging operation
                    utils.log(f'Selling order {sell_order["status"].lower()} - Id: {sell_order_id}')
                
                # If the order has been manually canceled from the user, it breaks the cycle.
                elif sell_order["status"] == "CANCELED":
                    # Deleting sell order from the memory
                    self.data_collector.deleteOrder(sell_order_id)

                    # Logging operation
                    utils.log(f'Selling order canceled - Id: {sell_order_id}')

                    break

                time.sleep(1)


    """ PUBLIC METHODS """
    # Function to start the CryptoBot's execution
    def start(self) -> None:
        # Creating the objects threads
        data_collector_thread = threading.Thread(target=self.data_collector.start, args=[])
        crypto_bot_thread = threading.Thread(target=self.__trade, args=[])

        # Starting the DataCollector's main thread
        data_collector_thread.start()

        # Waiting until the DataCollector is connected to the websocket
        data_collector_status = self.data_collector.getStatus()
        while data_collector_status != "CONNECTED":
            data_collector_status = self.data_collector.getStatus()
            time.sleep(1)

        utils.log("Bot connected")

        # Starting the CryptoBot's main thread
        crypto_bot_thread.start()
        
        # Joining the threads with the main thread
        data_collector_thread.join()
        crypto_bot_thread.join()