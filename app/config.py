import os

ALERT_PROFILE = os.getenv("ALERT_PROFILE", "trade")

USE_TREND_FILTER = os.getenv("USE_TREND_FILTER", "1") == "1"
USE_VOLUME_FILTER = os.getenv("USE_VOLUME_FILTER", "1") == "1"
USE_RSI_FILTER = os.getenv("USE_RSI_FILTER", "1") == "1"
USE_MACD_FILTER = os.getenv("USE_MACD_FILTER", "0") == "1"
USE_HTF_FILTER = os.getenv("USE_HTF_FILTER", "0") == "1"

VOL_RATIO_TRADE = float(os.getenv("VOL_RATIO_TRADE", 1.3))
VOL_RATIO_TEST = float(os.getenv("VOL_RATIO_TEST", 1.15))

RSI_LONG_MIN = float(os.getenv("RSI_LONG_MIN", 40))
RSI_LONG_MAX = float(os.getenv("RSI_LONG_MAX", 55))
RSI_SHORT_MIN = float(os.getenv("RSI_SHORT_MIN", 45))
RSI_SHORT_MAX = float(os.getenv("RSI_SHORT_MAX", 65))

EMA_GAP = float(os.getenv("EMA_GAP", 0.0008))

MACD_HIST_MIN_LONG = float(os.getenv("MACD_HIST_MIN_LONG", -0.0015))
MACD_HIST_MAX_SHORT = float(os.getenv("MACD_HIST_MAX_SHORT", 0.0015))

SPREAD_MAX = float(os.getenv("SPREAD_MAX", 0.001))
COOLDOWN_SEC = int(os.getenv("COOLDOWN_SEC", 600))
