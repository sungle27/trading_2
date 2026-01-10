from typing import Dict


def should_alert(
    side: str,               # "LONG" | "SHORT"
    mid: float,
    spread: float,
    ctx: dict,
    now_s: int,
    last_alert_sec: int,
    cooldown_sec: int,
    spread_max: float,
):
    """
    Return True nếu được phép alert
    """

    # =========================
    # 0. Cooldown & Spread
    # =========================
    if now_s - last_alert_sec < cooldown_sec:
        return False

    if spread > spread_max:
        return False

    # =========================
    # 1. REGIME FILTER (15m)
    # =========================
    ema20_15 = ctx.get("ema20_15m", 0.0)
    ema50_15 = ctx.get("ema50_15m", 0.0)

    if ema20_15 == 0 or ema50_15 == 0:
        return False

    if abs(ema20_15 - ema50_15) / mid < 0.001:
        return False

    # =========================
    # 1.5 VOLUME SPIKE FILTER (NEW)
    # =========================
    vol_ratio = ctx.get("vol_ratio_15m", 0.0)
    vol_dir = ctx.get("vol_dir_15m", 0.0)

    if vol_ratio < 1.8:
        return False

    if side == "LONG" and vol_dir <= 0:
        return False

    if side == "SHORT" and vol_dir >= 0:
        return False

    # =========================
    # 2. HTF TREND FILTER (1h)
    # =========================
    ema_htf = ctx.get("ema50_1h", 0.0)

    if ema_htf == 0:
        return False

    if side == "LONG" and mid <= ema_htf:
        return False

    if side == "SHORT" and mid >= ema_htf:
        return False

    # =========================
    # 3. RSI TIMING (15m)
    # =========================
    rsi_15 = ctx.get("rsi_15m", 50.0)

    if side == "LONG":
        if not (45 <= rsi_15 <= 55):
            return False

    if side == "SHORT":
        if not (50 <= rsi_15 <= 60):
            return False

    # =========================
    # 4. MACD STRENGTH (15m)
    # =========================
    macd_hist = ctx.get("macd_hist_15m", 0.0)

    if side == "LONG" and macd_hist < -0.0001:
        return False

    if side == "SHORT" and macd_hist > 0.0001:
        return False

    # =========================
    # OK – ALERT
    # =========================
    return True
