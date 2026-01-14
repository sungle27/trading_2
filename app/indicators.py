from typing import List, Tuple

def ema(values: List[float], period: int) -> float:
    if len(values) < period or period <= 1:
        return values[-1] if values else 0.0
    k = 2 / (period + 1)
    e = values[0]
    for v in values[1:]:
        e = v * k + e * (1 - k)
    return e

def rsi(values: List[float], period: int = 14) -> float:
    if len(values) < period + 1:
        return 50.0
    gains = 0.0
    losses = 0.0
    for i in range(-period, 0):
        diff = values[i] - values[i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    if losses == 0:
        return 100.0
    rs = gains / losses
    return 100 - (100 / (1 + rs))

def macd(values: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[float, float, float]:
    """
    returns (macd_line, signal_line, hist)
    """
    if len(values) < slow + signal + 5:
        return 0.0, 0.0, 0.0
    macd_line = ema(values, fast) - ema(values, slow)

    # build a small macd series for signal EMA
    # (simple approach: approximate by applying EMA to last N macd points)
    macd_series = []
    for i in range(- (signal + 30), 0):
        sub = values[:i] if i != 0 else values
        macd_series.append(ema(sub, fast) - ema(sub, slow))
    signal_line = ema(macd_series, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist
