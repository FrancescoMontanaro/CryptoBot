import math
import time
import utils
import threading
import datetime as dt
import concurrent.futures
from binance.client import Client
from dataCollector import DataCollector


class CryptoBot:
    """ PRIVATE METHODS """
    # Class constructor
    def __init__(self, api_key, api_secret, symbols, minumum_profit, against_symbol="USDT", interval="1m", rsi_window=13, rsi_threshold=20.0) -> None:
        # Initializing object's attributes
        self.symbols = symbols
        self.against_symbol = against_symbol
        self.minumum_profit = minumum_profit
        self.interval = interval
        self.rsi_window = rsi_window
        self.rsi_threshold = rsi_threshold
        self.open_position = False
        self.timeout = 120

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

    
    def __computeIndicators(self, symbol, rsi_window) -> tuple:
        # Getting the symbol's data from the DataCollector object
        dataframe = self.data_collector.getSymbolData(symbol)

        delta = dataframe["close"].diff()
        up = delta.clip(lower=0)
        down = - 1 * delta.clip(upper=0)

        # Computing the exponential moving average
        ema_up = up.ewm(com=rsi_window, adjust=False).mean()
        ema_down = down.ewm(com=rsi_window, adjust=False).mean()

        # Computing the relative strength index
        relative_strength = ema_up / ema_down
        dataframe["rsi"] = round((100.0 - (100.0 / (1.0 + relative_strength))), 3)

        # Extracting the current RSI value and close price
        current_rsi = dataframe["rsi"].tail(1).values[0]
        current_price = dataframe["close"].tail(1).values[0]

        return symbol, current_rsi, current_price


    # Function to check for some buying opportunity
    def __buyingOpportunity(self) -> tuple:
        # Computing the RSI indicator for every symbol in the list
        symbols_data = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.symbols)) as executor:
            futures = {executor.submit(self.__computeIndicators, symbol, self.rsi_window): symbol for symbol in self.symbols}
            for future in concurrent.futures.as_completed(futures):
                symbols_data.append(future.result())

        # Filtering symbols whose RSI value is under the specified threshold
        symbols_data = [symbol_data for symbol_data in symbols_data if symbol_data[1] <= self.rsi_threshold]

        buying_opportunity = None
        if(len(symbols_data) > 0):
            # Sorting symbols by their RSI value
            symbols_data.sort(key=lambda symbol_data:symbol_data[1])

            # Selecting the best buying opportunity as the one with the lowest RSI value
            buying_opportunity = symbols_data[0]

        return buying_opportunity


    # Bot's trading process
    def __trade(self) -> None:
        while True:
            ### LOOKING FOR BUYING OPPORTUNITIES ###
            # Looking for a buying opportunity (RSI < threshold)
            buy_opportunity = None
            while buy_opportunity is None:
                buy_opportunity = self.__buyingOpportunity()

            # Buy opportunity found
            symbol, rsi, buy_price = buy_opportunity

            continue

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
            except Exception as e:
                utils.log(f'Error creating BUYING order: {str(e)}')
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
                    except Exception as e:
                        utils.log(f'Error sending BUYING report: {str(e)}')
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
                    break

                else:
                    # Fetching the last RSI value and the price of the symbol
                    _, current_rsi, current_price = self.__computeIndicators(symbol, self.rsi_window)

                    # Getting the time elapsed seconds from the creation of the order
                    current_time = dt.datetime.now()
                    elapsed_time = (current_time - creation_time).seconds

                    # If during the fulfillment operation the RSI value decreases while the
                    # last price of the symbol increases, the order is canceled: the previous 
                    # buying condition is no longer the best.
                    if (current_rsi < rsi and current_price > buy_price) or elapsed_time >= self.timeout:
                        try:
                            # Canceling the order
                            self.client.cancel_order(symbol=symbol, orderId=buy_order["id"])
                        except Exception as e:
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
                    except Exception as e:
                        utils.log(f'Error creating SELL order: {str(e)}')
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

                    except Exception as e:
                        utils.log(f'Error sending SELLING report: {str(e)}')
                        
                    else:
                        # Mark the position as close
                        self.open_position = False

                # if the order is Rejected, Canceled or Expired, the process restarts by trying to open another selling order
                elif sell_order["status"] == "REJECTED" or sell_order["status"] == "EXPIRED":
                    # Deleting sell order from the memory
                    self.data_collector.deleteOrder(sell_order_id)

                    # Mark the selling order as not open
                    sell_order_id = None
                
                # If the order has been manually canceled from the user, it breaks the cycle.
                elif sell_order["status"] == "CANCELED":
                    # Deleting sell order from the memory
                    self.data_collector.deleteOrder(sell_order_id)
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

        # Starting the CryptoBot's main thread
        crypto_bot_thread.start()
        
        # Joining the threads with the main thread
        data_collector_thread.join()
        crypto_bot_thread.join()