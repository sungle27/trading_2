from typing import Dict, List, Tuple
from .config import TEST_MODE

# ============================================================
# TEST CONFIG
# ============================================================
TEST_MODE = "BOTH"  
# OPTIONS:
#   "OFF"   → chạy logic thật
#   "LONG"  → ép LONG
#   "SHORT" → ép SHORT
#   "BOTH"  → LUÂN PHIÊN LONG / SHORT (để test)

VOL_RATIO_MIN = 1.4        # test: 1.1 | prod: 1.4+
EMA_GAP_MIN = 0.0015       # test nới trend


# ============================================================
# FAST CONTEXT FILTER (LIGHT PRE-FILTER)
# ============================================================
def ctx_filters_signal(ctx: Dict[str, float], side: str) -> bool:
    rsi5 = ctx.get("rsi_5m", 50.0)
    rsi15 = ctx.get("rsi_15m", 50.0)
    ema20 = ctx.get("ema20_15m", 0.0)
    ema50 = ctx.get("ema50_15m", 0.0)

    if side == "LONG":
        return rsi5 > 35 and rsi15 > 35 and ema20 >= ema50
    else:
        return rsi5 < 65 and rsi15 < 65 and ema20 <= ema50


# ============================================================
# MAIN ALERT ENGINE
# ============================================================
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

    reasons: List[str] = []

    # ========================================================
    # TEST MODE – FORCE LONG / SHORT / BOTH
    # ========================================================
    if TEST_MODE != "OFF":
        if TEST_MODE == side or TEST_MODE == "BOTH":
            return True, [f"TEST MODE: force {side}"]

    # ========================================================
    # 0. COOLDOWN & SPREAD
    # ========================================================
    if now_s - last_alert_sec < cooldown_sec:
        return False, ["Cooldown"]

    if spread > spread_max:
        return False, ["Spread too large"]

    reasons.append(f"Spread OK ({spread:.4%})")

    # ========================================================
    # 1. TREND FILTER (15m)
    # ========================================================
    ema20 = ctx.get("ema20_15m", 0.0)
    ema50 = ctx.get("ema50_15m", 0.0)

    if ema20 == 0.0 or ema50 == 0.0:
        return False, ["EMA not ready"]

    ema_gap = abs(ema20 - ema50) / mid
    if ema_gap < EMA_GAP_MIN:
        return False, ["EMA gap too small"]

    if side == "LONG":
        if ema20 <= ema50:
            return False, ["Not uptrend"]
        reasons.append("Uptrend (EMA20 > EMA50)")
    else:
        if ema20 >= ema50:
            return False, ["Not downtrend"]
        reasons.append("Downtrend (EMA20 < EMA50)")

    # ========================================================
    # 2. VOLUME SPIKE (5m)
    # ========================================================
    vol_ratio = ctx.get("vol_ratio_5m", 0.0)
    vol_dir = ctx.get("vol_dir_5m", 0.0)

    if vol_ratio < VOL_RATIO_MIN:
        return False, [f"Volume weak ({vol_ratio:.2f}x)"]

    reasons.append(f"Volume spike {vol_ratio:.2f}x")

    if side == "LONG" and vol_dir <= 0:
        return False, ["No buy pressure"]
    if side == "SHORT" and vol_dir >= 0:
        return False, ["No sell pressure"]

    reasons.append("Directional volume OK")

    # ========================================================
    # 3. HTF BIAS (1h)
    # ========================================================
    ema_htf = ctx.get("ema50_1h", 0.0)
    if ema_htf == 0.0:
        return False, ["HTF EMA not ready"]

    if side == "LONG" and mid <= ema_htf:
        return False, ["Below EMA50 1h"]
    if side == "SHORT" and mid >= ema_htf:
        return False, ["Above EMA50 1h"]

    reasons.append("HTF bias aligned")

    # ========================================================
    # 4. RSI (TEST FRIENDLY)
    # ========================================================
    rsi5 = ctx.get("rsi_5m", 50.0)
    rsi15 = ctx.get("rsi_15m", 50.0)

    if side == "LONG":
        if not (40 <= rsi5 <= 70):
            return False, ["RSI5 extreme"]
        if not (45 <= rsi15 <= 65):
            return False, ["RSI15 extreme"]
    else:
        if not (30 <= rsi5 <= 60):
            return False, ["RSI5 extreme"]
        if not (35 <= rsi15 <= 55):
            return False, ["RSI15 extreme"]

    reasons.append(f"RSI OK (5m={rsi5:.1f}, 15m={rsi15:.1f})")

    # ========================================================
    # 5. MACD (ANTI FAKE)
    # ========================================================
    macd = ctx.get("macd_hist_15m", 0.0)

    if side == "LONG" and macd < -0.0005:
        return False, ["MACD too negative"]
    if side == "SHORT" and macd > 0.0005:
        return False, ["MACD too positive"]

    reasons.append(f"MACD OK ({macd:.5f})")

    # ========================================================
    # CONFIRMED
    # ========================================================
    return True, reasons
