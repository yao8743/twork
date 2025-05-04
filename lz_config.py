import os
from dotenv import load_dotenv
load_dotenv()
load_dotenv(dotenv_path='.lzbot.env')
API_TOKEN = os.getenv("BOT_TOKEN")
POSTGRES_DSN = os.getenv("POSTGRES_DSN")

