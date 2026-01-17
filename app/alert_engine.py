from dataclasses import dataclass
from typing import List, Tuple

from config import Config
from indicators import ema, rsi, macd

@dataclass
class MarketData:
    symbol: str
    bid: float
    ask: float
    closes: List[float]
    last_price: float

def spread_ratio(bid: float, ask: float) -> float:
    if bid <= 0:
        return 1.0
    return (ask - bid) / bid

def evaluate_signal(cfg: Config, m: MarketData) -> Tuple[bool, str]:
    """
    returns: (should_alert, reason_text)
    """
    reasons: List[str] = []

    # 1) SPREAD
    if cfg.ENABLE_SPREAD:
        sp = spread_ratio(m.bid, m.ask)
        if sp > cfg.SPREAD_MAX:
            return False, f"SPREAD_FAIL sp={sp:.5f} > {cfg.SPREAD_MAX:.5f}"
        reasons.append(f"SPREAD_OK sp={sp:.5f}")
    else:
        reasons.append("SPREAD_OFF")

    # 2) REGIME / TREND by EMA gap (%)
    # gap = |EMAfast - EMAslow| / price
    if cfg.ENABLE_REGIME:
        ef = ema(m.closes, cfg.EMA_FAST)
        es = ema(m.closes, cfg.EMA_SLOW)
        denom = m.last_price if m.last_price > 0 else 1.0
        gap = abs(ef - es) / denom
        if gap < cfg.REGIME_EMA_GAP:
            return False, f"REGIME_FAIL gap={gap:.5f} < {cfg.REGIME_EMA_GAP:.5f}"
        trend = "UP" if ef >= es else "DOWN"
        reasons.append(f"REGIME_OK {trend} gap={gap:.5f}")
    else:
        reasons.append("REGIME_OFF")

    # 3) RSI (entry zone)
    side = "BOTH"
    r = rsi(m.closes, cfg.RSI_PERIOD)

    if cfg.ENABLE_RSI:
        long_ok = cfg.RSI_LONG_MIN <= r <= cfg.RSI_LONG_MAX
        short_ok = cfg.RSI_SHORT_MIN <= r <= cfg.RSI_SHORT_MAX
        if not (long_ok or short_ok):
            return False, f"RSI_FAIL rsi={r:.2f}"
        side = "LONG" if long_ok else "SHORT"
        reasons.append(f"RSI_OK {side} rsi={r:.2f}")
    else:
        reasons.append(f"RSI_OFF rsi={r:.2f}")

    # 4) MACD histogram confirm
    if cfg.ENABLE_MACD:
        _, _, hist = macd(m.closes, cfg.MACD_FAST, cfg.MACD_SLOW, cfg.MACD_SIGNAL)

        # Rule theo config của bạn:
        # - LONG: hist >= MACD_HIST_MIN_LONG (không quá âm)
        # - SHORT: hist <= MACD_HIST_MAX_SHORT (không quá dương)
        # Nếu RSI OFF => cho pass theo “near 0 avoidance” nhẹ.
        if side == "LONG":
            if hist < cfg.MACD_HIST_MIN_LONG:
                return False, f"MACD_FAIL_LONG hist={hist:.6f} < {cfg.MACD_HIST_MIN_LONG:.6f}"
        elif side == "SHORT":
            if hist > cfg.MACD_HIST_MAX_SHORT:
                return False, f"MACD_FAIL_SHORT hist={hist:.6f} > {cfg.MACD_HIST_MAX_SHORT:.6f}"
        else:
            # RSI OFF: chỉ chặn chop cực mạnh (hist rất gần 0)
            if -1e-6 < hist < 1e-6:
                return False, f"MACD_FAIL hist={hist:.6f} near0"

        reasons.append(f"MACD_OK hist={hist:.6f}")
    else:
        reasons.append("MACD_OFF")

    return True, " | ".join(reasons)
