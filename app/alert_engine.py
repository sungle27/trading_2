from typing import Dict, List, Tuple


def ctx_filters_signal(ctx: Dict[str, float], side: str) -> bool:
    rsi5 = ctx.get("rsi_5m", 50.0)
    rsi15 = ctx.get("rsi_15m", 50.0)
    ema20 = ctx.get("ema20_15m", 0.0)
    ema50 = ctx.get("ema50_15m", 0.0)
    macd = ctx.get("macd_hist_15m", 0.0)

    if side == "LONG":
        return rsi5 > 45 and rsi15 > 45 and ema20 > ema50 and macd > -0.002
    else:
        return rsi5 < 55 and rsi15 < 55 and ema20 < ema50 and macd < 0.002


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

    reasons: List[str] = [f"Spread OK ({spread:.4%})"]

    ema20 = ctx["ema20_15m"]
    ema50 = ctx["ema50_15m"]
    gap = abs(ema20 - ema50) / mid
    if gap < 0.001:
        return False, []
    reasons.append("Trend OK (EMA gap)")

    vol_ratio = ctx["vol_ratio_5m"]
    if vol_ratio < 1.5:
        return False, []
    reasons.append(f"Volume spike {vol_ratio:.2f}x")

    vol_dir = ctx["vol_dir_5m"]
    if side == "LONG" and vol_dir <= 0:
        return False, []
    if side == "SHORT" and vol_dir >= 0:
        return False, []

    rsi15 = ctx["rsi_15m"]
    if not (40 <= rsi15 <= 60):
        return False, []
    reasons.append(f"RSI15={rsi15:.1f}")

    rsi5 = ctx["rsi_5m"]
    if not (40 <= rsi5 <= 65):
        return False, []
    reasons.append(f"RSI5={rsi5:.1f}")

    macd = ctx["macd_hist_15m"]
    if side == "LONG" and macd < -0.001:
        return False, []
    if side == "SHORT" and macd > 0.001:
        return False, []
    reasons.append(f"MACD hist={macd:.5f}")

    ema1h = ctx["ema50_1h"]
    if side == "LONG" and mid <= ema1h:
        return False, []
    if side == "SHORT" and mid >= ema1h:
        return False, []

    reasons.append("HTF trend confirmed")
    return True, reasons
