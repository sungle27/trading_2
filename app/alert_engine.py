from typing import Dict, List, Tuple


# ============================================================
# FAST CONTEXT FILTER (OPTIONAL – PRE FILTER)
# ============================================================
def ctx_filters_signal(ctx: Dict[str, float], side: str) -> bool:
    """
    Lightweight pre-filter to skip very weak setups.
    DOES NOT use volume or cooldown.
    """

    rsi5 = ctx.get("rsi_5m", 50.0)
    rsi15 = ctx.get("rsi_15m", 50.0)

    ema20 = ctx.get("ema20_15m", 0.0)
    ema50 = ctx.get("ema50_15m", 0.0)

    macd = ctx.get("macd_hist_15m", 0.0)

    if side == "LONG":
        if rsi5 < 45:
            return False
        if rsi15 < 45:
            return False
        if ema20 and ema50 and ema20 <= ema50:
            return False
        if macd < -0.002:
            return False
        return True

    else:  # SHORT
        if rsi5 > 55:
            return False
        if rsi15 > 55:
            return False
        if ema20 and ema50 and ema20 >= ema50:
            return False
        if macd > 0.002:
            return False
        return True


# ============================================================
# MAIN ALERT ENGINE (RETURN REASONS)
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
    """
    FINAL decision engine.

    Returns:
        (True, reasons[]) or (False, [])
    """

    reasons: List[str] = []

    # ========================================================
    # 0. COOLDOWN & SPREAD
    # ========================================================
    if now_s - last_alert_sec < cooldown_sec:
        return False, []

    if spread > spread_max:
        return False, []

    reasons.append(f"Spread OK ({spread:.4%})")

    # ========================================================
    # 1. TREND REGIME FILTER (15m / 30m mapped here)
    # ========================================================
    ema20 = ctx.get("ema20_15m", 0.0)
    ema50 = ctx.get("ema50_15m", 0.0)

    if ema20 == 0.0 or ema50 == 0.0:
        return False, []

    ema_gap = abs(ema20 - ema50) / mid
    if ema_gap < 0.001:
        return False, []

    if side == "LONG" and ema20 > ema50:
        reasons.append("EMA20 > EMA50 (trend up)")
    elif side == "SHORT" and ema20 < ema50:
        reasons.append("EMA20 < EMA50 (trend down)")
    else:
        return False, []

    # ========================================================
    # 2. VOLUME SPIKE (5m – CORE CONDITION)
    # ========================================================
    vol_ratio = ctx.get("vol_ratio_5m", 0.0)
    vol_dir = ctx.get("vol_dir_5m", 0.0)

    if vol_ratio < 1.3:
        return False, []

    reasons.append(f"Volume spike {vol_ratio:.2f}x")

    if side == "LONG" and vol_dir > 0:
        reasons.append("Directional volume: BUY pressure")
    elif side == "SHORT" and vol_dir < 0:
        reasons.append("Directional volume: SELL pressure")
    else:
        return False, []

    # ========================================================
    # 3. HTF BIAS (1h)
    # ========================================================
    ema_htf = ctx.get("ema50_1h", 0.0)
    if ema_htf == 0.0:
        return False, []

    if side == "LONG" and mid > ema_htf:
        reasons.append("Price above EMA50 (1h)")
    elif side == "SHORT" and mid < ema_htf:
        reasons.append("Price below EMA50 (1h)")
    else:
        return False, []

    # ========================================================
    # 4. RSI TIMING (PULLBACK / CONTINUATION)
    # ========================================================
    rsi_5 = ctx.get("rsi_5m", 50.0)
    rsi_15 = ctx.get("rsi_15m", 50.0)

    if side == "LONG":
        if not (40 <= rsi_15 <= 65):
            return False, []
        if not (40 <= rsi_5 <= 70):
            return False, []
        reasons.append(f"RSI pullback OK (5m={rsi_5:.1f}, 15m={rsi_15:.1f})")

    else:  # SHORT
        if not (35 <= rsi_15 <= 60):
            return False, []
        if not (30 <= rsi_5 <= 60):
            return False, []
        reasons.append(f"RSI pullback OK (5m={rsi_5:.1f}, 15m={rsi_15:.1f})")

    # ========================================================
    # 5. MACD CLAMP (ANTI FAKE)
    # ========================================================
    macd_hist = ctx.get("macd_hist_15m", 0.0)

    if side == "LONG" and macd_hist >= -0.001:
        reasons.append(f"MACD hist OK ({macd_hist:.5f})")
    elif side == "SHORT" and macd_hist <= 0.001:
        reasons.append(f"MACD hist OK ({macd_hist:.5f})")
    else:
        return False, []

    # ========================================================
    # CONFIRMED
    # ========================================================
    return True, reasons
