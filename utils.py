import os
import pytz
import dotenv
import hashlib
import datetime as dt
from discordwebhook import Discord


# Loading the environmental variables
dotenv.load_dotenv()

# Instantiating the Discord object
webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
discord = Discord(url=webhook_url)

# Logs file
log_file = "logs.log"


# Function to get the datetime for the selected timezone.
def getDatetime() -> dt.datetime:
    date_time = dt.datetime.now()
    date_time = date_time.astimezone(pytz.timezone("Europe/Rome"))
    return date_time


# Function to initialize the logging files
def initLogFile() -> None:
    open(log_file,'w').close()


# Function to log errors
def log(data) -> None:
    # Creating the log file if it does not exist
    if not os.path.exists(log_file):
        open(log_file,'w').close()

    # Appending the line to the file
    with open(log_file, 'a') as f:
        f.write('%s --> %s\n' % (str(dt.datetime.now()), data))


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