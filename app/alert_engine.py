from typing import Dict, List, Tuple


# ============================================================
# FAST CONTEXT FILTER (OPTIONAL – PRE-FILTER)
# ============================================================
def ctx_filters_signal(ctx: Dict[str, float], side: str) -> bool:
    """
    Lightweight pre-filter (NO volume, NO cooldown).
    Used to quickly discard weak symbols.
    """

    rsi5 = ctx.get("rsi_5m", 50.0)
    rsi15 = ctx.get("rsi_15m", 50.0)
    ema20_15 = ctx.get("ema20_15m", 0.0)
    ema50_15 = ctx.get("ema50_15m", 0.0)
    macd15 = ctx.get("macd_hist_15m", 0.0)

    if side == "LONG":
        if rsi5 < 50:
            return False
        if rsi15 < 45:
            return False
        if ema20_15 and ema50_15 and ema20_15 <= ema50_15:
            return False
        if macd15 < 0:
            return False
        return True

    else:  # SHORT
        if rsi5 > 50:
            return False
        if rsi15 > 55:
            return False
        if ema20_15 and ema50_15 and ema20_15 >= ema50_15:
            return False
        if macd15 > 0:
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
    FINAL decision for alert.
    Returns:
        (True, reasons[])  or  (False, [])
    """

    reasons: List[str] = []

    # =========================
    # 0. COOLDOWN & SPREAD
    # =========================
    if now_s - last_alert_sec < cooldown_sec:
        return False, []

    if spread > spread_max:
        return False, []

    reasons.append(f"Spread OK ({spread:.4%})")

    # =========================
    # 1. REGIME FILTER (15m)
    # =========================
    ema20_15 = ctx.get("ema20_15m", 0.0)
    ema50_15 = ctx.get("ema50_15m", 0.0)

    if ema20_15 == 0.0 or ema50_15 == 0.0:
        return False, []

    ema_gap = abs(ema20_15 - ema50_15) / mid
    if ema_gap < 0.001:
        return False, []

    if side == "LONG" and ema20_15 > ema50_15:
        reasons.append("EMA20 > EMA50 (15m) → uptrend")
    elif side == "SHORT" and ema20_15 < ema50_15:
        reasons.append("EMA20 < EMA50 (15m) → downtrend")
    else:
        return False, []

    # =========================
    # 1.5 VOLUME SPIKE (CORE)
    # =========================
    #vol_ratio = ctx.get("vol_ratio_15m", 0.0)
    #vol_dir = ctx.get("vol_dir_15m", 0.0)

    vol_ratio = ctx.get("vol_ratio_5m", 0.0)
    vol_dir   = ctx.get("vol_dir_5m", 0.0)
    rsi_5     = ctx.get("rsi_5m", 50.0)

    if vol_ratio < 1.8:
        return False, []

    reasons.append(f"Volume spike {vol_ratio:.2f}x")

    if side == "LONG" and vol_dir > 0:
        reasons.append("Directional volume: BUY pressure")
    elif side == "SHORT" and vol_dir < 0:
        reasons.append("Directional volume: SELL pressure")
    else:
        return False, []

    # =========================
    # 2. HTF TREND (1h)
    # =========================
    ema_htf = ctx.get("ema50_1h", 0.0)
    if ema_htf == 0.0:
        return False, []

    if side == "LONG" and mid > ema_htf:
        reasons.append("Price above EMA50 (1h)")
    elif side == "SHORT" and mid < ema_htf:
        reasons.append("Price below EMA50 (1h)")
    else:
        return False, []

    # =========================
    # 3. RSI TIMING (15m)
    # =========================
    rsi_15 = ctx.get("rsi_15m", 50.0)

    if side == "LONG" and 45 <= rsi_15 <= 55:
        reasons.append(f"RSI(15m)={rsi_15:.1f} in pullback zone")
    elif side == "SHORT" and 50 <= rsi_15 <= 60:
        reasons.append(f"RSI(15m)={rsi_15:.1f} in rally zone")
    else:
        return False, []

    # =========================
    # 3.1 RSI TIMING (15m)
    # =========================

    rsi_5 = ctx.get("rsi_5m", 50.0)

    if side == "LONG" and 45 <= rsi_5 <= 60:
        reasons.append(f"RSI(5m)={rsi_5:.1f} pullback timing")
    elif side == "SHORT" and 40 <= rsi_5 <= 55:
        reasons.append(f"RSI(5m)={rsi_5:.1f} rally timing")
    else:
        return False, []
    # =========================
    # 4. MACD CLAMP
    # =========================
    macd_hist = ctx.get("macd_hist_15m", 0.0)

    if side == "LONG" and macd_hist >= -0.0001:
        reasons.append(f"MACD hist={macd_hist:.5f} acceptable")
    elif side == "SHORT" and macd_hist <= 0.0001:
        reasons.append(f"MACD hist={macd_hist:.5f} acceptable")
    else:
        return False, []

    # =========================
    # CONFIRMED
    # =========================
    return True, reasons
