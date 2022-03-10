import os
import pytz
import dotenv
import logging
import datetime as dt
from discordwebhook import Discord


# Loading the environmental variables
dotenv.load_dotenv()

# Instantiating the Discord object
webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
discord = Discord(url=webhook_url)

# Logs file initialization
logFile = "logs.log"
logging.basicConfig(filename=logFile, level=logging.ERROR)


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

    # Posting the message in the Discord channel
    discord.post(embeds=[embed])