import os
import dotenv
from cryptoBot import CryptoBot


# Loading the environmental variables
dotenv.load_dotenv()
api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_SECRET')

# Global variables
symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "LUNAUSDT", "SOLUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "DOGEUSDT", "SHIBUSDT"]
against_symbol = "USDT"
minimum_profit = 1.003
rsi_threshold = 26.0
rsi_window = 13
interval = '1m'

# Instantiating the CryptoBot object
crypto_bot = CryptoBot(
    api_key=api_key, 
    api_secret=api_secret, 
    symbols=symbols, 
    minumum_profit=minimum_profit,
    against_symbol=against_symbol, 
    interval=interval,
    rsi_window=rsi_window,
    rsi_threshold=rsi_threshold
)

if __name__ == "__main__":
    # Starting the bot's execution
    crypto_bot.start()