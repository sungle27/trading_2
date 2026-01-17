from __future__ import annotations

from .config import (
    ALERT_PROFILE,
    ENABLE_SPREAD,
    ENABLE_REGIME,
    ENABLE_RSI,
    ENABLE_MACD,
    REGIME_EMA_GAP,
    RSI_LONG_MIN,
    RSI_LONG_MAX,
    RSI_SHORT_MIN,
    RSI_SHORT_MAX,
    MACD_HIST_MIN_LONG,
    MACD_HIST_MAX_SHORT,
    COOLDOWN_SEC,
    SPREAD_MAX,
)


# ============================================================
# CONTEXT FILTER
# ============================================================
def ctx_filters_signal(ctx: dict, side: str):
    """
    ctx keys:
        rsi, rsi15
        ema20, ema50, ema50_1h
        macd
        vol_ratio, vol_dir
    """

    reasons = []

    # ===== REGIME / TREND =====
    if ENABLE_REGIME:
        if ctx["ema20"] is None or ctx["ema50"] is None:
            return False, ["EMA not ready"]

        gap = abs(ctx["ema20"] - ctx["ema50"]) / ctx["ema50"]

        if gap < REGIME_EMA_GAP:
            reasons.append("EMA gap too small")

        if side == "LONG" and ctx["ema20"] <= ctx["ema50"]:
            reasons.append("EMA trend down")

        if side == "SHORT" and ctx["ema20"] >= ctx["ema50"]:
            reasons.append("EMA trend up")

    # ===== RSI =====
    if ENABLE_RSI:
        if ctx["rsi"] is None:
            return False, ["RSI not ready"]

        if side == "LONG" and not (RSI_LONG_MIN <= ctx["rsi"] <= RSI_LONG_MAX):
            reasons.append("RSI out of LONG range")

        if side == "SHORT" and not (RSI_SHORT_MIN <= ctx["rsi"] <= RSI_SHORT_MAX):
            reasons.append("RSI out of SHORT range")

    # ===== MACD =====
    if ENABLE_MACD:
        if ctx["macd"] is None:
            return False, ["MACD not ready"]

        if side == "LONG" and ctx["macd"] < MACD_HIST_MIN_LONG:
            reasons.append("MACD weak")

        if side == "SHORT" and ctx["macd"] > MACD_HIST_MAX_SHORT:
            reasons.append("MACD weak")

    if reasons:
        return False, reasons

    return True, ["CTX OK"]


# ============================================================
# FINAL ALERT GATE
# ============================================================
def should_alert(*, now_s: int, last_alert_sec: int, spread: float):
    reasons = []

    if ENABLE_SPREAD and spread > SPREAD_MAX:
        reasons.append("Spread too high")

    if now_s - last_alert_sec < COOLDOWN_SEC:
        reasons.append("Cooldown active")

    if reasons:
        return False, reasons

    return True, ["ALERT OK"]
