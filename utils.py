import pytz
import logging
import datetime as dt
from discordwebhook import Discord

# Global variables
logFile = "logs.log"
logging.basicConfig(filename=logFile, level=logging.ERROR)
discord = Discord(url="https://ptb.discord.com/api/webhooks/947919924662272060/OIJOK29aZwDPWUtIL0OEsr6uUiCVZ-GPkiRcYcy9Scg0P9IdrjEdXsoSTJYRjCiY5FSc")
crypto_icons = {"BTC": "1", "ETH": "1027", "BNB": "1839", "XRP": "52", "LUNA": "4172", "SOL": "5426", "ADA": "2010", "AVAX": "5805", "DOT": "6636", "DOGE": "74", "SHIB": "5994"}

# Function to get the datetime for the selected timezone.
def getDatetime() -> dt.datetime:
    date_time = dt.datetime.now()
    date_time = date_time.astimezone(pytz.timezone("Europe/Rome"))
    return date_time


# Function to log errors
def log(data) -> None:
    f = open(logFile,'r')
    lines = f.readlines()
    f.close()

    if(len(lines) > 1000):
        open(logFile,'w').close()

    logging.error('%s | %s' % (str(dt.datetime.now()), data))


# Function to send Discord notifications
def sendWebhook(symbol, description, color) -> None:
    embed = {
        "username": "Crypto Bot",
        "title": f'**{symbol}**',
        "color": color,
        "description": description,
        "footer": { "text": "Crypto Bot"},
        "timestamp": str(getDatetime())
    }

    if(symbol in crypto_icons.keys()):
        embed["thumbnail"] = f"https://s2.coinmarketcap.com/static/img/coins/128x128/{crypto_icons[symbol]}.png"

    # Posting the message in the Discord channel
    discord.post(embeds=[embed])