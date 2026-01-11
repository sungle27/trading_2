import os
from dotenv import load_dotenv

load_dotenv()

BINANCE_FUTURES_REST = os.getenv("BINANCE_FUTURES_REST", "https://fapi.binance.com")
BINANCE_FUTURES_WS = os.getenv("BINANCE_FUTURES_WS", "wss://fstream.binance.com/stream")
TOP_N = int(os.getenv("TOP_N", "20"))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

MYSQL_ENABLED = os.getenv("MYSQL_ENABLED", "0") == "1"
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "crypto_alert")
MYSQL_BAR_TABLE = os.getenv("MYSQL_BAR_TABLE", "bar_1s")
MYSQL_ALERT_TABLE = os.getenv("MYSQL_ALERT_TABLE", "alerts")

ALERT_MODE = os.getenv("ALERT_MODE", "signal")  # signal | rsi | macd

COOLDOWN_SEC = int(os.getenv("COOLDOWN_SEC", "90"))
ALERT_P_UP = float(os.getenv("ALERT_P_UP", "0.65"))
ALERT_P_DOWN = float(os.getenv("ALERT_P_DOWN", "0.65"))
FIXED_BPS = float(os.getenv("FIXED_BPS", "0.0004"))
K_VOL = float(os.getenv("K_VOL", "1.2"))
SPREAD_MAX = float(os.getenv("SPREAD_MAX", "0.0010"))

RSI_MODE = os.getenv("RSI_MODE", "threshold")
RSI_TF = os.getenv("RSI_TF", "5m")
RSI_OB = float(os.getenv("RSI_OB", "70"))
RSI_OS = float(os.getenv("RSI_OS", "30"))
RSI_COOLDOWN_SEC = int(os.getenv("RSI_COOLDOWN_SEC", "300"))

MACD_MODE = os.getenv("MACD_MODE", "hist_cross0")
MACD_TF = os.getenv("MACD_TF", "15m")
MACD_COOLDOWN_SEC = int(os.getenv("MACD_COOLDOWN_SEC", "300"))

MODEL_REG_PATH = os.getenv("MODEL_REG_PATH", "models/reg_lgbm.txt")
MODEL_CLF_PATH = os.getenv("MODEL_CLF_PATH", "models/clf_lgbm.txt")

LLSUNG_VER = os.getenv("LLSUNG_VER", "llsung_ver_")

