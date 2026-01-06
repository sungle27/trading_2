from typing import Dict, Tuple
import time

def get_rsi(ctx: Dict[str, float], tf: str) -> float:
    return ctx.get(f"rsi_{tf}", ctx.get("rsi_5m", 50.0))

def get_macd_hist(ctx: Dict[str, float], tf: str) -> float:
    return ctx.get(f"macd_hist_{tf}", ctx.get("macd_hist_15m", 0.0))

def ctx_filters_signal(ctx: Dict[str, float], side: str) -> bool:
    rsi5 = ctx["rsi_5m"]
    rsi15 = ctx["rsi_15m"]
    ema20_15 = ctx["ema20_15m"]
    ema50_15 = ctx["ema50_15m"]
    macd15 = ctx["macd_hist_15m"]
    ema_ready = (ema20_15 != 0.0 and ema50_15 != 0.0)

    if side == "LONG":
        if rsi5 < 50: return False
        if rsi15 < 45: return False
        if ema_ready and not (ema20_15 > ema50_15): return False
        if macd15 < 0: return False
        return True
    else:
        if rsi5 > 50: return False
        if rsi15 > 55: return False
        if ema_ready and not (ema20_15 < ema50_15): return False
        if macd15 > 0: return False
        return True

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
    Return True nếu được phép alert, False nếu bị chặn
    """

    # =========================
    # 0. Cooldown & spread
    # =========================
    if now_s - last_alert_sec < cooldown_sec:
        return False

    if spread > spread_max:
        return False

    # =========================
    # 1. REGIME FILTER (15m)
    # =========================
    ema20_15 = ctx["ema20_15m"]
    ema50_15 = ctx["ema50_15m"]

    if ema20_15 == 0 or ema50_15 == 0:
        return False

    # sideway nếu EMA quá sát nhau
    if abs(ema20_15 - ema50_15) / mid < 0.001:
        return False

    # =========================
    # 2. HTF TREND FILTER (1h)
    # =========================
    ema200_1h = ctx.get("ema50_1h")  # nếu có EMA200_1h thì thay ở đây

    if ema200_1h == 0:
        return False

    if side == "LONG" and mid <= ema200_1h:
        return False

    if side == "SHORT" and mid >= ema200_1h:
        return False

    # =========================
    # 3. RSI TIMING (15m)
    # =========================
    rsi_15 = ctx["rsi_15m"]

    if side == "LONG":
        # buy dip trong uptrend
        if not (45 <= rsi_15 <= 55):
            return False

    if side == "SHORT":
        # sell rally trong downtrend
        if not (50 <= rsi_15 <= 60):
            return False

    # =========================
    # 4. MACD STRENGTH (15m)
    # =========================
    macd_hist = ctx["macd_hist_15m"]

    if side == "LONG":
        # lực tăng, không quá âm
        if macd_hist < -0.0001:
            return False

    if side == "SHORT":
        # lực giảm, không quá dương
        if macd_hist > 0.0001:
            return False

    # =========================
    # OK – ĐỦ ĐIỀU KIỆN ALERT
    # =========================
    return True
