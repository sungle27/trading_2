import os
from dataclasses import dataclass
from dotenv import load_dotenv
load_dotenv()


# ============================================================
# Helpers
# ============================================================
def _s(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()

def _i(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)).strip())
    except ValueError:
        return default

def _f(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)).strip())
    except ValueError:
        return default


# ============================================================
# Config Dataclass
# ============================================================
@dataclass(frozen=True)
class Config:
    # ===== Binance =====
    BINANCE_FUTURES_REST: str = _s(
        "BINANCE_FUTURES_REST",
        "https://fapi.binance.com",
    )
    BINANCE_FUTURES_WS: str = _s(
        "BINANCE_FUTURES_WS",
        "wss://fstream.binance.com/stream",
    )
    TOP_N: int = _i("TOP_N", 20)

    # ===== Alert / Strategy Mode =====
    ALERT_PROFILE: str = _s("ALERT_PROFILE", "trade")   # trade | test
    ALERT_MODE: str = _s("ALERT_MODE", "signal")        # signal | rsi | macd

    # ===== Telegram =====
    TELEGRAM_BOT_TOKEN: str = _s("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = _s("TELEGRAM_CHAT_ID", "")

    # ===== Loop / Debug =====
    LOOP_SEC: int = _i("LOOP_SEC", 10)
    HEARTBEAT_SEC: int = _i("HEARTBEAT_SEC", 60)
    DEBUG_ENABLED: int = _i("DEBUG_ENABLED", 1)

    # ===== Global Risk Control =====
    COOLDOWN_SEC: int = _i("COOLDOWN_SEC", 600)
    SPREAD_MAX: float = _f("SPREAD_MAX", 0.0012)

    # ===== Enable / Disable Filters =====
    ENABLE_SPREAD: int = _i("ENABLE_SPREAD", 1)
    ENABLE_REGIME: int = _i("ENABLE_REGIME", 1)
    ENABLE_RSI: int = _i("ENABLE_RSI", 1)
    ENABLE_MACD: int = _i("ENABLE_MACD", 1)

    # ===== Regime / Trend =====
    # REGIME_EMA_GAP là tỉ lệ: 0.0025 = 0.25%
    REGIME_EMA_GAP: float = _f("REGIME_EMA_GAP", 0.0025)
    EMA_FAST: int = _i("EMA_FAST", 21)
    EMA_SLOW: int = _i("EMA_SLOW", 55)

    # ===== RSI =====
    RSI_PERIOD: int = _i("RSI_PERIOD", 14)
    RSI_LONG_MIN: float = _f("RSI_LONG_MIN", 40)
    RSI_LONG_MAX: float = _f("RSI_LONG_MAX", 52)
    RSI_SHORT_MIN: float = _f("RSI_SHORT_MIN", 46)
    RSI_SHORT_MAX: float = _f("RSI_SHORT_MAX", 62)

    # ===== MACD =====
    MACD_FAST: int = _i("MACD_FAST", 12)
    MACD_SLOW: int = _i("MACD_SLOW", 26)
    MACD_SIGNAL: int = _i("MACD_SIGNAL", 9)
    MACD_HIST_MIN_LONG: float = _f("MACD_HIST_MIN_LONG", -0.00015)
    MACD_HIST_MAX_SHORT: float = _f("MACD_HIST_MAX_SHORT", 0.00015)


# ============================================================
# Singleton export (RẤT QUAN TRỌNG)
# ============================================================
CFG = Config()

# ============================================================
# Backward-compatible exports
# (để main.py / alert_engine.py import trực tiếp)
# ============================================================
BINANCE_FUTURES_REST = CFG.BINANCE_FUTURES_REST
BINANCE_FUTURES_WS = CFG.BINANCE_FUTURES_WS
TOP_N = CFG.TOP_N

ALERT_PROFILE = CFG.ALERT_PROFILE
ALERT_MODE = CFG.ALERT_MODE

TELEGRAM_BOT_TOKEN = CFG.TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID = CFG.TELEGRAM_CHAT_ID

LOOP_SEC = CFG.LOOP_SEC
HEARTBEAT_SEC = CFG.HEARTBEAT_SEC
DEBUG_ENABLED = CFG.DEBUG_ENABLED

COOLDOWN_SEC = CFG.COOLDOWN_SEC
SPREAD_MAX = CFG.SPREAD_MAX

ENABLE_SPREAD = CFG.ENABLE_SPREAD
ENABLE_REGIME = CFG.ENABLE_REGIME
ENABLE_RSI = CFG.ENABLE_RSI
ENABLE_MACD = CFG.ENABLE_MACD

REGIME_EMA_GAP = CFG.REGIME_EMA_GAP
EMA_FAST = CFG.EMA_FAST
EMA_SLOW = CFG.EMA_SLOW

RSI_PERIOD = CFG.RSI_PERIOD
RSI_LONG_MIN = CFG.RSI_LONG_MIN
RSI_LONG_MAX = CFG.RSI_LONG_MAX
RSI_SHORT_MIN = CFG.RSI_SHORT_MIN
RSI_SHORT_MAX = CFG.RSI_SHORT_MAX

MACD_FAST = CFG.MACD_FAST
MACD_SLOW = CFG.MACD_SLOW
MACD_SIGNAL = CFG.MACD_SIGNAL
MACD_HIST_MIN_LONG = CFG.MACD_HIST_MIN_LONG
MACD_HIST_MAX_SHORT = CFG.MACD_HIST_MAX_SHORT
