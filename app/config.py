import os
from dotenv import load_dotenv

load_dotenv()

BINANCE_FUTURES_REST = os.getenv("BINANCE_FUTURES_REST")
BINANCE_FUTURES_WS = os.getenv("BINANCE_FUTURES_WS")
TOP_N = int(os.getenv("TOP_N", "20"))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

COOLDOWN_SEC = int(os.getenv("COOLDOWN_SEC", "300"))
SPREAD_MAX = float(os.getenv("SPREAD_MAX", "0.0012"))
