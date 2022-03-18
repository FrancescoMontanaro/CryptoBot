import os
import dotenv
from cryptoBot import CryptoBot


# Loading the environmental variables
dotenv.load_dotenv()
api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_SECRET')

# Global variables
symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "LUNAUSDT", "SOLUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "SHIBUSDT"]
against_symbol = "USDT"
minimum_profit = 1.003
interval = '1m'

# Instantiating the CryptoBot object
crypto_bot = CryptoBot(
    api_key=api_key, 
    api_secret=api_secret, 
    symbols=symbols, 
    minumum_profit=minimum_profit,
    against_symbol=against_symbol, 
    interval=interval
)


# Starting the bot's execution
if __name__ == "__main__":
    crypto_bot.start()