import os
from dataclasses import dataclass

def _s(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()

def _i(key: str, default: int) -> int:
    return int(os.getenv(key, str(default)).strip())

def _f(key: str, default: float) -> float:
    return float(os.getenv(key, str(default)).strip())

@dataclass
class Config:
    # ===== Binance =====
    BINANCE_FUTURES_REST: str = _s("BINANCE_FUTURES_REST", "https://fapi.binance.com")
    BINANCE_FUTURES_WS: str = _s("BINANCE_FUTURES_WS", "wss://fstream.binance.com/stream")
    TOP_N: int = _i("TOP_N", 20)

    # ===== Alert mode =====
    ALERT_PROFILE: str = _s("ALERT_PROFILE", "trade")  # test | trade
    ALERT_MODE: str = _s("ALERT_MODE", "signal")       # signal | rsi | macd (mình giữ signal)

    # ===== Telegram =====
    TELEGRAM_BOT_TOKEN: str = _s("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = _s("TELEGRAM_CHAT_ID", "")

    # ===== Loop / Debug =====
    LOOP_SEC: int = _i("LOOP_SEC", 10)                 # thêm mới: mỗi bao lâu scan
    HEARTBEAT_SEC: int = _i("HEARTBEAT_SEC", 60)       # thêm mới: ping sống
    DEBUG_ENABLED: int = _i("DEBUG_ENABLED", 1)

    # ===== Global Control =====
    COOLDOWN_SEC: int = _i("COOLDOWN_SEC", 600)
    SPREAD_MAX: float = _f("SPREAD_MAX", 0.0012)

    # ===== Enable flags (bật/tắt từng bộ) =====
    ENABLE_SPREAD: int = _i("ENABLE_SPREAD", 1)
    ENABLE_REGIME: int = _i("ENABLE_REGIME", 1)
    ENABLE_RSI: int = _i("ENABLE_RSI", 1)
    ENABLE_MACD: int = _i("ENABLE_MACD", 1)

    # ===== Regime / Trend =====
    # NOTE: REGIME_EMA_GAP nên là tỉ lệ: 0.0025 = 0.25%
    REGIME_EMA_GAP: float = _f("REGIME_EMA_GAP", 0.0025)
    EMA_FAST: int = _i("EMA_FAST", 21)     # thêm mới (default hợp lý)
    EMA_SLOW: int = _i("EMA_SLOW", 55)

    # ===== RSI =====
    RSI_PERIOD: int = _i("RSI_PERIOD", 14)  # thêm mới
    RSI_LONG_MIN: float = _f("RSI_LONG_MIN", 40)
    RSI_LONG_MAX: float = _f("RSI_LONG_MAX", 52)
    RSI_SHORT_MIN: float = _f("RSI_SHORT_MIN", 46)
    RSI_SHORT_MAX: float = _f("RSI_SHORT_MAX", 62)

    # ===== MACD =====
    MACD_FAST: int = _i("MACD_FAST", 12)     # thêm mới
    MACD_SLOW: int = _i("MACD_SLOW", 26)
    MACD_SIGNAL: int = _i("MACD_SIGNAL", 9)
    MACD_HIST_MIN_LONG: float = _f("MACD_HIST_MIN_LONG", -0.00015)
    MACD_HIST_MAX_SHORT: float = _f("MACD_HIST_MAX_SHORT", 0.00015)
