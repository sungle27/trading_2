import math
from dataclasses import dataclass
from typing import Optional

class EMA:
    def __init__(self, period: int):
        self.period = period
        self.alpha = 2.0 / (period + 1)
        self.value: Optional[float] = None

    def update(self, x: float) -> float:
        if self.value is None:
            self.value = x
        else:
            self.value = self.alpha * x + (1 - self.alpha) * self.value
        return self.value

class RSI:
    def __init__(self, period: int = 14):
        self.period = period
        self.avg_gain: Optional[float] = None
        self.avg_loss: Optional[float] = None
        self.prev: Optional[float] = None
        self.value: Optional[float] = None

    def update(self, close: float) -> float:
        if self.prev is None:
            self.prev = close
            self.value = 50.0
            return self.value

        ch = close - self.prev
        gain = max(ch, 0.0)
        loss = max(-ch, 0.0)

        if self.avg_gain is None:
            self.avg_gain = gain
            self.avg_loss = loss
        else:
            self.avg_gain = (self.avg_gain * (self.period - 1) + gain) / self.period
            self.avg_loss = (self.avg_loss * (self.period - 1) + loss) / self.period

        rs = self.avg_gain / (self.avg_loss + 1e-12)
        self.value = 100.0 - (100.0 / (1.0 + rs))
        self.prev = close
        return self.value

@dataclass
class MACDState:
    macd: float
    signal: float
    hist: float

class MACD:
    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.ema_fast = EMA(fast)
        self.ema_slow = EMA(slow)
        self.ema_signal = EMA(signal)
        self.macd: Optional[float] = None
        self.signal: Optional[float] = None
        self.hist: Optional[float] = None

    def update(self, close: float) -> MACDState:
        f = self.ema_fast.update(close)
        s = self.ema_slow.update(close)
        self.macd = f - s
        self.signal = self.ema_signal.update(self.macd)
        self.hist = self.macd - self.signal
        return MACDState(macd=self.macd, signal=self.signal, hist=self.hist)
