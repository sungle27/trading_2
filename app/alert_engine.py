from typing import Dict, List, Tuple
from .config import ALERT_PROFILE
from .config import (
    RSI_LONG_MIN, 
    RSI_LONG_MAX,
    RSI_SHORT_MIN, 
    RSI_SHORT_MAX,
)


# ==============================
# PROFILE PARAMS
# ==============================
PROFILE = {
    "test": {
        "VOL_RATIO": 1.3,
        "EMA_GAP": 0.0008,
        "RSI5": (35, 65),
        "RSI15": (35, 65),
        "MACD_MIN": -0.002,
        "HTF_BAND": 0.005,
    },
    "trade": {
        "VOL_RATIO": 1.5,
        "EMA_GAP": 0.0012,
        "RSI5": (40, 55),
        "RSI15": (45, 60),
        "MACD_MIN": -0.001,
        "HTF_BAND": 0.002,
    },
}[ALERT_PROFILE]


# ==============================
# CONTEXT FILTER
# ==============================
# def ctx_filters_signal(ctx: Dict[str, float], side: str) -> bool:
#     ema20 = ctx["ema20_15m"]
#     ema50 = ctx["ema50_15m"]
#     macd = ctx["macd_hist_15m"]

#     if side == "LONG":
#         return ema20 > ema50 and macd > PROFILE["MACD_MIN"]
#     else:
#         return ema20 < ema50 and macd < -PROFILE["MACD_MIN"]

def ctx_filters_signal(ctx, side):
    reasons = []

    if side == "LONG":
        if ctx["ema20_15m"] <= ctx["ema50_15m"]:
            reasons.append("EMA trend fail")

        if not (RSI_LONG_MIN <= ctx["rsi_5m"] <= RSI_LONG_MAX):
            reasons.append("RSI5 fail")

        if ctx["vol_ratio_5m"] < PROFILE["VOL_RATIO"]:
            reasons.append("Volume fail")

    if reasons:
        return False, reasons

    return True, ["CTX OK"]

# ==============================
# FINAL ALERT DECISION
# ==============================
def should_alert(
    side: str,
    mid: float,
    spread: float,
    ctx: Dict[str, float],
    now_s: int,
    last_alert_sec: int,
    cooldown_sec: int,
    spread_max: float,
) -> Tuple[bool, List[str]]:

    if now_s - last_alert_sec < cooldown_sec:
        return False, []

    if spread > spread_max:
        return False, []
    
    if spread > spread_max:
        return False, [f"Spread too high {spread:.5f}"]

    if now_s - last_alert_sec < cooldown_sec:
        return False, ["Cooldown active"]
    
    reasons: List[str] = []

    # ===== TREND GAP =====
    gap = abs(ctx["ema20_15m"] - ctx["ema50_15m"]) / mid
    if gap < PROFILE["EMA_GAP"]:
        return False, []
    reasons.append(f"EMA gap {gap:.3%}")

    # ===== VOLUME =====
    if ctx["vol_ratio_5m"] < PROFILE["VOL_RATIO"]:
        return False, []
    reasons.append(f"Volume spike {ctx['vol_ratio_5m']:.2f}x")

    # ===== DIRECTION =====
    if side == "LONG" and ctx["vol_dir_5m"] <= 0:
        return False, []
    if side == "SHORT" and ctx["vol_dir_5m"] >= 0:
        return False, []

    # ===== RSI =====
    rsi5 = ctx["rsi_5m"]
    rsi15 = ctx["rsi_15m"]
    if not (PROFILE["RSI5"][0] <= rsi5 <= PROFILE["RSI5"][1]):
        return False, []
    if not (PROFILE["RSI15"][0] <= rsi15 <= PROFILE["RSI15"][1]):
        return False, []

    reasons.append(f"RSI5={rsi5:.1f}, RSI15={rsi15:.1f}")

    # ===== HTF FILTER =====
    ema1h = ctx["ema50_1h"]
    band = PROFILE["HTF_BAND"]

    if side == "LONG" and mid < ema1h * (1 - band):
        return False, []
    if side == "SHORT" and mid > ema1h * (1 + band):
        return False, []

    reasons.append("HTF OK")

    return True, reasons
