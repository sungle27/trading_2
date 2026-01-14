from .config import *

def ctx_filters_signal(ctx, side):
    reasons = []

    # ===== TREND =====
    if USE_TREND_FILTER:
        if side == "LONG" and ctx["ema20"] <= ctx["ema50"]:
            reasons.append("EMA trend fail")
        if side == "SHORT" and ctx["ema20"] >= ctx["ema50"]:
            reasons.append("EMA trend fail")

    # ===== RSI =====
    if USE_RSI_FILTER:
        if side == "LONG" and not (RSI_LONG_MIN <= ctx["rsi"] <= RSI_LONG_MAX):
            reasons.append("RSI fail")
        if side == "SHORT" and not (RSI_SHORT_MIN <= ctx["rsi"] <= RSI_SHORT_MAX):
            reasons.append("RSI fail")

    # ===== VOLUME =====
    if USE_VOLUME_FILTER:
        vol_th = VOL_RATIO_TRADE if ALERT_PROFILE == "trade" else VOL_RATIO_TEST
        if ctx["vol_ratio"] < vol_th:
            reasons.append("Volume low")

    # ===== MACD =====
    if USE_MACD_FILTER:
        if side == "LONG" and ctx["macd"] < MACD_HIST_MIN_LONG:
            reasons.append("MACD weak")
        if side == "SHORT" and ctx["macd"] > MACD_HIST_MAX_SHORT:
            reasons.append("MACD weak")

    return len(reasons) == 0, reasons


def should_alert(now_s, last_alert_sec, spread):
    if spread > SPREAD_MAX:
        return False, ["Spread too high"]
    if now_s - last_alert_sec < COOLDOWN_SEC:
        return False, ["Cooldown"]
    return True, []
