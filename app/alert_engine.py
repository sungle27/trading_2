from typing import Dict, List, Tuple

# ============================================================
# CONFIG – DỄ TEST
# ============================================================
TEST_MODE_FORCE_LONG = False   # <-- đổi True để ÉP LONG TEST
VOL_RATIO_MIN = 1.1            # test: 1.1 | prod: 1.3 – 1.5
EMA_GAP_MIN = 0.0003           # nới để test trend mới hình thành


# ============================================================
# FAST CONTEXT FILTER (PRE-FILTER)
# ============================================================
def ctx_filters_signal(ctx: Dict[str, float], side: str) -> bool:
    """
    Fast pre-filter to skip very weak setups.
    No volume, no cooldown.
    """

    rsi5 = ctx.get("rsi_5m", 50.0)
    rsi15 = ctx.get("rsi_15m", 50.0)
    ema20 = ctx.get("ema20_15m", 0.0)
    ema50 = ctx.get("ema50_15m", 0.0)
    macd = ctx.get("macd_hist_15m", 0.0)

    if side == "LONG":
        if rsi5 < 40:
            return False
        if rsi15 < 40:
            return False
        if ema20 and ema50 and ema20 < ema50:
            return False
        if macd < -0.003:
            return False
        return True

    else:  # SHORT
        if rsi5 > 60:
            return False
        if rsi15 > 60:
            return False
        if ema20 and ema50 and ema20 > ema50:
            return False
        if macd > 0.003:
            return False
        return True


# ============================================================
# MAIN ALERT ENGINE
# ============================================================
def should_alert(
    side: str,               # "LONG" | "SHORT"
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
    # TEST MODE – FORCE LONG
    # ========================================================
    if TEST_MODE_FORCE_LONG and side == "LONG":
        return True, ["TEST MODE: force LONG"]

    # ========================================================
    # 0. COOLDOWN & SPREAD
    # ========================================================
    if now_s - last_alert_sec < cooldown_sec:
        return False, ["Cooldown active"]

    if spread > spread_max:
        return False, [f"Spread too large ({spread:.4%})"]

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
        return False, [f"EMA gap too small ({ema_gap:.4%})"]

    if side == "LONG":
        if ema20 <= ema50:
            return False, ["Trend not up (EMA20 <= EMA50)"]
        reasons.append("Uptrend confirmed (EMA20 > EMA50)")
    else:
        if ema20 >= ema50:
            return False, ["Trend not down (EMA20 >= EMA50)"]
        reasons.append("Downtrend confirmed (EMA20 < EMA50)")

    # ========================================================
    # 2. VOLUME SPIKE (5m)
    # ========================================================
    vol_ratio = ctx.get("vol_ratio_5m", 0.0)
    vol_dir = ctx.get("vol_dir_5m", 0.0)

    if vol_ratio < VOL_RATIO_MIN:
        return False, [f"Volume spike too weak ({vol_ratio:.2f}x)"]

    reasons.append(f"Volume spike {vol_ratio:.2f}x")

    if side == "LONG":
        if vol_dir <= 0:
            return False, ["No buy pressure"]
        reasons.append("Buy pressure detected")
    else:
        if vol_dir >= 0:
            return False, ["No sell pressure"]
        reasons.append("Sell pressure detected")

    # ========================================================
    # 3. HTF BIAS (1h)
    # ========================================================
    ema_htf = ctx.get("ema50_1h", 0.0)
    if ema_htf == 0.0:
        return False, ["HTF EMA not ready"]

    if side == "LONG":
        if mid <= ema_htf:
            return False, ["Price below EMA50 (1h)"]
        reasons.append("HTF bias bullish")
    else:
        if mid >= ema_htf:
            return False, ["Price above EMA50 (1h)"]
        reasons.append("HTF bias bearish")

    # ========================================================
    # 4. RSI TIMING (TEST FRIENDLY)
    # ========================================================
    rsi5 = ctx.get("rsi_5m", 50.0)
    rsi15 = ctx.get("rsi_15m", 50.0)

    if side == "LONG":
        if not (35 <= rsi15 <= 80):
            return False, [f"RSI15 out of range ({rsi15:.1f})"]
        if not (35 <= rsi5 <= 85):
            return False, [f"RSI5 out of range ({rsi5:.1f})"]
        reasons.append(f"RSI OK (5m={rsi5:.1f}, 15m={rsi15:.1f})")
    else:
        if not (20 <= rsi15 <= 65):
            return False, [f"RSI15 out of range ({rsi15:.1f})"]
        if not (20 <= rsi5 <= 65):
            return False, [f"RSI5 out of range ({rsi5:.1f})"]
        reasons.append(f"RSI OK (5m={rsi5:.1f}, 15m={rsi15:.1f})")

    # ========================================================
    # 5. MACD CLAMP
    # ========================================================
    macd = ctx.get("macd_hist_15m", 0.0)

    if side == "LONG":
        if macd < -0.002:
            return False, [f"MACD too negative ({macd:.5f})"]
        reasons.append(f"MACD OK ({macd:.5f})")
    else:
        if macd > 0.002:
            return False, [f"MACD too positive ({macd:.5f})"]
        reasons.append(f"MACD OK ({macd:.5f})")

    # ========================================================
    # CONFIRMED
    # ========================================================
    return True, reasons
