import utils
import threading
import pandas as pd
import datetime as dt
from binance.client import Client
from binance import ThreadedWebsocketManager


class DataCollector:
    """ PRIVATE METHODS """
    # Class constructor
    def __init__(self, api_key, api_secret, symbols, against_symbol="USDT", interval="1m", lookback_days=1, lookback_hours=6) -> None:
        # Initializing object's attributes
        self.symbols = symbols
        self.interval = interval
        self.lookback_days = lookback_days
        self.lookback_hours = lookback_hours
        self.against_symbol = against_symbol
        self.status = "DISCONNECTED"

        # Creating dataframes to containing historical data of the symbols
        self.symbols_dataframes = {symbol: None for symbol in self.symbols}

        # Creating list of assets' balances
        self.assets_balances = []

        # Creating list of orders
        self.orders = []

        # Instantiating the Binance API Client
        self.client = Client(api_key=api_key, api_secret=api_secret)

        # Instantiating the websocket manager
        self.twm = ThreadedWebsocketManager(api_key=api_key, api_secret=api_secret)


    # Function to collect historical data for a specific symbol
    def __historicalData(self, symbol) -> None:
        # Defining the start period
        start = dt.datetime.now().timestamp()
        start = int(start * 1000) - (self.lookback_days * self.lookback_hours * 60 * 60 * 1000)

        # Collecting historical data of the symbol
        historical_data = self.client.get_historical_klines(symbol.upper(), self.interval, start)

        # Loading the data into a pandas dataframe
        dataframe = pd.DataFrame([[data[i] for i in range(6)] for data in historical_data])
        dataframe.columns = ['time','open', 'high', 'low', 'close', 'volume']
        dataframe = dataframe.astype({"open": 'float64', "high": 'float64', "low": 'float64', "close": 'float64', "volume": 'float64'})
        dataframe.set_index("time", drop=True, inplace=True)
        dataframe.index.astype('int64')

        self.symbols_dataframes[symbol.upper()] = dataframe

    
    # Function to initialize the symbols' data
    def __initializeSymbolsData(self) -> None:
        # Starting a thread for each symbol to collect histprical data
        threads = []
        for symbol in self.symbols:
            thread = threading.Thread(target=self.__historicalData, args=[symbol])
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()


    # Callback function to collect and update symbols' data
    def __updateSymbolsData(self, msg) -> None:
        # Error handling
        if msg["e"] == "error" and msg["m"] == "Max reconnect retries reached":
            self.status = "DISCONNECTED"
            utils.log("Fatal Error - Websocket Disconnected")
            raise Exception("Websocket Disconnected")

        # If the candle's open time is not present in the symbol's dataframe, it is added and the oldest candle is removed
        elif msg["k"]["t"] not in self.symbols_dataframes[msg["s"]].index:
            # Loading the candle's data into a pandas dataframe
            df = pd.DataFrame([[msg["k"]["t"], msg["k"]["o"], msg["k"]["h"], msg["k"]["l"], msg["k"]["c"], msg["k"]["v"]]])
            df.columns = ['time','open', 'high', 'low', 'close', 'volume']
            df = df.astype({"open": 'float64', "high": 'float64', "low": 'float64', "close": 'float64', "volume": 'float64'})
            df.set_index("time", drop=True, inplace=True)
            df.index.astype('int64')

            # Appending the candle's dataframe to the symbol's main dataframe
            self.symbols_dataframes[msg["s"]] = pd.concat([self.symbols_dataframes[msg["s"]], df])

            # Remove first row corresponding to the oldest candle
            self.symbols_dataframes[msg["s"]] =  self.symbols_dataframes[msg["s"]].iloc[1:,:]

        # If the candle's open time is present in the symbol's dataframe, it updates the corresponding row with the latest values
        else:
            self.symbols_dataframes[msg["s"]].loc[msg["k"]["t"], 'open'] = float(msg["k"]["o"])
            self.symbols_dataframes[msg["s"]].loc[msg["k"]["t"], 'high'] = float(msg["k"]["h"])
            self.symbols_dataframes[msg["s"]].loc[msg["k"]["t"], 'low'] = float(msg["k"]["l"])
            self.symbols_dataframes[msg["s"]].loc[msg["k"]["t"], 'close'] = float(msg["k"]["c"])
            self.symbols_dataframes[msg["s"]].loc[msg["k"]["t"], 'volume'] = float(msg["k"]["v"])


    # Function to initialize user's data
    def __initializeUserData(self) -> None:
        # Fetching user's data
        account_info = self.client.get_account()
        
        # Fetchin user's open orders
        open_orders = self.client.get_open_orders()

        # Extracting user's assets balances
        balances = account_info["balances"]
        symbols = [symbol.replace(self.against_symbol, "") for symbol in self.symbols]

        # Loading the assets' balance into a list
        for balance in balances:
            if balance["asset"] in symbols or balance["asset"] == self.against_symbol:
                self.assets_balances.append(balance)

        # Loading the user's open orders into a list
        for open_order in open_orders:
            self.orders.append({
                "id": open_order["orderId"],
                "symbol": open_order["symbol"],
                "side": open_order["side"],
                "type": open_order["type"],
                "quantity": float(open_order["origQty"]),
                "price": float(open_order["price"]),
                "status": open_order["status"],
                "timestamp": open_order["time"],
                "filled_quantity": float(open_order["executedQty"])
            })


    # Callback function to collect and update user's data
    def __updateUserData(self, msg) -> None:
        # Error handling
        if msg["e"] == "error" and msg["m"] == "Max reconnect retries reached":
            self.status = "DISCONNECTED"
            utils.log("Fatal Error - Websocket Disconnected")
            raise Exception("Websocket Disconnected")

        # Updating user's assets balance
        elif msg["e"] == "outboundAccountPosition":
            for asset_balance in msg["B"]:
                account_asset_balance = [balance for balance in self.assets_balances if balance["asset"] == asset_balance["a"]]
                if len(account_asset_balance) > 0:
                    account_asset_balance = account_asset_balance[0]

                # Updating the free and locked quantity of the asset
                account_asset_balance["free"] = float(asset_balance["f"])
                account_asset_balance["locked"] = float(asset_balance["l"])

        # Updating user's open orders
        elif msg["e"] == "executionReport":
            # Updating the order if it is already present
            if msg['i'] in [o["id"] for o in self.orders]:
                orders = [o for o in self.orders if o["id"] == msg['i']]
                if len(orders) > 0:
                    order = orders[0]
                    order["status"] = msg["X"]
                    order["filled_quantity"] = float(msg["z"])

            # Adding the order if it is not present
            else:
                self.orders.append({
                    "id": msg["i"],
                    "symbol": msg["s"],
                    "side": msg["S"],
                    "type": msg["o"],
                    "quantity": float(msg["q"]),
                    "price": float(msg["p"]),
                    "status": msg["X"],
                    "timestamp": msg["T"],
                    "filled_quantity": float(msg["z"])
                })


    """ PUBLIC METHODS """
    # Function to start the data collection
    def start(self) -> None:
        # Initializing symbols' hystorical data
        self.__initializeSymbolsData()

        # Initializing user's data
        self.__initializeUserData()

        # Starting a websocket stream for each symbol
        self.twm.start()
        for symbol in self.symbols:
            self.twm.start_kline_socket(callback=self.__updateSymbolsData, symbol=symbol.lower(), interval=self.interval)

        # Starting a websocket stream to collect user's data
        self.twm.start_user_socket(callback=self.__updateUserData)

        # Setting the object status to READY
        self.status = "CONNECTED"

        # Joining the threads with the main thread
        self.twm.join()


    # Function to get the DataCollector status
    def getStatus(self) -> str:
        return self.status


    # Function to get the dataframe of a specific symbol
    def getSymbolData(self, symbol) -> pd.DataFrame:
        return self.symbols_dataframes[symbol]

    
    # Function to get balance of a given asset
    def getAssetBalance(self, symbol) -> dict:
        asset = None
        for balance in self.assets_balances:
            if balance["asset"] == symbol:
                asset = balance

        return asset


    # Function to get an order by id
    def getOrder(self, order_id) -> dict:
        order = None
        for stored_order in self.orders:
            if stored_order["id"] == order_id:
                order = stored_order

        return order


    # Function to delete an order by its id
    def deleteOrder(self, order_id) -> None:
        self.orders = [order for order in self.orders if order["id"] != order_id]


    # Function to remove all the orders from the memory
    def cleanOrders(self) -> None:
        self.orders = []