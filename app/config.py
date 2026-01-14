import os
from dataclasses import dataclass

def env_int(key: str, default: int) -> int:
    return int(os.getenv(key, str(default)).strip())

def env_float(key: str, default: float) -> float:
    return float(os.getenv(key, str(default)).strip())

def env_str(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()

@dataclass
class Config:
    # Core
    alert_profile: str = env_str("ALERT_PROFILE", "trade")   # test|trade
    alert_mode: str = env_str("ALERT_MODE", "signal")        # signal
    top_n: int = env_int("TOP_N", 20)

    # Binance
    binance_rest: str = env_str("BINANCE_FUTURES_REST", "https://fapi.binance.com")

    # Telegram
    tg_token: str = env_str("TELEGRAM_BOT_TOKEN", "")
    tg_chat_id: str = env_str("TELEGRAM_CHAT_ID", "")

    # Loop / debug
    loop_sec: int = env_int("LOOP_SEC", 10)
    heartbeat_sec: int = env_int("HEARTBEAT_SEC", 60)
    debug_enabled: int = env_int("DEBUG_ENABLED", 1)

    # Anti-spam
    cooldown_sec: int = env_int("COOLDOWN_SEC", 600)

    # Enable flags
    enable_spread: int = env_int("ENABLE_SPREAD", 1)
    enable_regime: int = env_int("ENABLE_REGIME", 1)
    enable_rsi: int = env_int("ENABLE_RSI", 1)
    enable_macd: int = env_int("ENABLE_MACD", 1)

    # Spread
    spread_max: float = env_float("SPREAD_MAX", 0.0012)

    # Regime / EMA gap
    ema_fast: int = env_int("EMA_FAST", 21)
    ema_slow: int = env_int("EMA_SLOW", 55)
    regime_ema_gap: float = env_float("REGIME_EMA_GAP", 0.0025)  # 0.25%

    # RSI
    rsi_period: int = env_int("RSI_PERIOD", 14)
    rsi_long_min: float = env_float("RSI_LONG_MIN", 40)
    rsi_long_max: float = env_float("RSI_LONG_MAX", 52)
    rsi_short_min: float = env_float("RSI_SHORT_MIN", 48)
    rsi_short_max: float = env_float("RSI_SHORT_MAX", 62)

    # MACD
    macd_fast: int = env_int("MACD_FAST", 12)
    macd_slow: int = env_int("MACD_SLOW", 26)
    macd_signal: int = env_int("MACD_SIGNAL", 9)
    macd_hist_min_long: float = env_float("MACD_HIST_MIN_LONG", -0.00015)
    macd_hist_max_short: float = env_float("MACD_HIST_MAX_SHORT", 0.00015)
