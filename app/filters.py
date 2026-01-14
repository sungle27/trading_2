from dataclasses import dataclass
from typing import List, Dict, Tuple

from config import Config
from indicators import ema, rsi, macd

@dataclass
class MarketSnapshot:
    symbol: str
    bid: float
    ask: float
    closes: List[float]   # close series (timeframe bạn chọn)
    last_price: float

def spread_ratio(bid: float, ask: float) -> float:
    if bid <= 0:
        return 1.0
    return (ask - bid) / bid

def evaluate(cfg: Config, m: MarketSnapshot) -> Tuple[bool, str]:
    """
    returns (pass, reason_text)
    """
    reasons: List[str] = []

    # 1) Spread
    if cfg.enable_spread:
        sp = spread_ratio(m.bid, m.ask)
        if sp > cfg.spread_max:
            return False, f"SPREAD_FAIL sp={sp:.5f} > {cfg.spread_max:.5f}"
        reasons.append(f"SPREAD_OK sp={sp:.5f}")

    # 2) Regime / Trend (EMA gap as %)
    if cfg.enable_regime:
        ef = ema(m.closes, cfg.ema_fast)
        es = ema(m.closes, cfg.ema_slow)
        gap = abs(ef - es) / (m.last_price if m.last_price > 0 else 1.0)
        if gap < cfg.regime_ema_gap:
            return False, f"REGIME_FAIL gap={gap:.5f} < {cfg.regime_ema_gap:.5f}"
        # direction (optional)
        trend = "UP" if ef >= es else "DOWN"
        reasons.append(f"REGIME_OK {trend} gap={gap:.5f}")

    # 3) RSI zone
    r = rsi(m.closes, cfg.rsi_period)
    if cfg.enable_rsi:
        long_ok = cfg.rsi_long_min <= r <= cfg.rsi_long_max
        short_ok = cfg.rsi_short_min <= r <= cfg.rsi_short_max
        if not (long_ok or short_ok):
            return False, f"RSI_FAIL rsi={r:.2f}"
        side = "LONG" if long_ok else "SHORT"
