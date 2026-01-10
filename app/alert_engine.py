from typing import Dict


# ============================================================
# FAST CONTEXT FILTER (OPTIONAL – PRE-FILTER)
# ============================================================
def ctx_filters_signal(ctx: Dict[str, float], side: str) -> bool:
    """
    Lightweight pre-filter to quickly discard weak symbols.
    Does NOT use volume, spread, cooldown.
    """

    rsi5 = ctx.get("rsi_5m", 50.0)
    rsi15 = ctx.get("rsi_15m", 50.0)
    ema20_15 = ctx.get("ema20_15m", 0.0)
    ema50_15 = ctx.get("ema50_15m", 0.0)
    macd15 = ctx.get("macd_hist_15m", 0.0)

    ema_ready = (ema20_15 != 0.0 and ema50_15 != 0.0)

    if side == "LONG":
        if rsi5 < 50:
            return False
        if rsi15 < 45:
            return False
        if ema_ready and ema20_15 <= ema50_15:
            return False
        if macd15 < 0:
            return False
        return True

    else:  # SHORT
        if rsi5 > 50:
            return False
        if rsi15 > 55:
            return False
        if ema_ready and ema20_15 >= ema50_15:
            return False
        if macd15 > 0:
            return False
        return True


# ============================================================
# MAIN ALERT DECISION ENGINE (STRONG SIGNAL)
# ============================================================
def should_alert(
    side: str,               # "LONG" | "SHORT"
    mid: float,              # mid price
    spread: float,           # spread ratio
    ctx: Dict[str, float],   # indicator snapshot
    now_s: int,              # current unix time
    last_alert_sec: int,     # last alert time
    cooldown_sec: int,       # cooldown seconds
    spread_max: float,       # max allowed spread
) -> bool:
    """
    FINAL GATE for alert.
    Emphasizes:
      - trend
      - timing
      - momentum
      - VOLUME SPIKE + DIRECTION
    """

    # ========================================================
    # 0. COOLDOWN & SPREAD
    # ========================================================
    if now_s - last_alert_sec < cooldown_sec:
        return False

    if spread > spread_max:
        return False

    # ========================================================
    # 1. REGIME FILTER (15m EMA GAP)
    # ========================================================
    ema20_15 = ctx.get("ema20_15m", 0.0)
    ema50_15 = ctx.get("ema50_15m", 0.0)

    if ema20_15 == 0.0 or ema50_15 == 0.0:
        return False

    # sideway market
    if abs(ema20_15 - ema50_15) / mid < 0.001:
        return False

    # ========================================================
    # 1.5 VOLUME SPIKE + DIRECTION (CORE REQUIREMENT)
    # ========================================================
    vol_ratio = ctx.get("vol_ratio_15m", 0.0)
    vol_dir = ctx.get("vol_dir_15m", 0.0)

    # no volume expansion → skip
    if vol_ratio < 1.8:
        return False

    # volume must align with direction
    if side == "LONG" and vol_dir <= 0:
        return False
    if side == "SHORT" and vol_dir >= 0:
        return False

    # ========================================================
    # 2. HTF TREND FILTER (1h)
    # ========================================================
    ema_htf = ctx.get("ema50_1h", 0.0)

    if ema_htf == 0.0:
        return False

    if side == "LONG" and mid <= ema_htf:
        return False
    if side == "SHORT" and mid >= ema_htf:
        return False

    # ========================================================
    # 3. RSI TIMING (15m – MEAN ZONE)
    # ========================================================
    rsi_15 = ctx.get("rsi_15m", 50.0)

    if side == "LONG":
        # buy pullback in uptrend
        if not (45.0 <= rsi_15 <= 55.0):
            return False

    if side == "SHORT":
        # sell rally in downtrend
        if not (50.0 <= rsi_15 <= 60.0):
            return False

    # ========================================================
    # 4. MACD MOMENTUM CLAMP (15m)
    # ========================================================
    macd_hist = ctx.get("macd_hist_15m", 0.0)

    if side == "LONG" and macd_hist < -0.0001:
        return False

    if side == "SHORT" and macd_hist > 0.0001:
        return False

    # ========================================================
    # STRONG SIGNAL CONFIRMED
    # ========================================================
    return True
