from dataclasses import dataclass
from typing import Optional

class EMA:
    def __init__(self, period: int):
        self.alpha = 2.0 / (period + 1)
        self.value = None

    def update(self, x: float):
        self.value = x if self.value is None else self.alpha * x + (1 - self.alpha) * self.value
        return self.value


class RSI:
    def __init__(self, period: int = 14):
        self.period = period
        self.avg_gain = None
        self.avg_loss = None
        self.prev = None
        self.value = None

    def update(self, close: float):
        if self.prev is None:
            self.prev = close
            self.value = 50.0
            return self.value

        ch = close - self.prev
        gain = max(ch, 0)
        loss = max(-ch, 0)

        if self.avg_gain is None:
            self.avg_gain, self.avg_loss = gain, loss
        else:
            self.avg_gain = (self.avg_gain * (self.period - 1) + gain) / self.period
            self.avg_loss = (self.avg_loss * (self.period - 1) + loss) / self.period

        rs = self.avg_gain / (self.avg_loss + 1e-12)
        self.value = 100 - 100 / (1 + rs)
        self.prev = close
        return self.value


@dataclass
class MACDState:
    macd: float
    signal: float
    hist: float


class MACD:
    def __init__(self, fast=12, slow=26, signal=9):
        self.ema_fast = EMA(fast)
        self.ema_slow = EMA(slow)
        self.ema_signal = EMA(signal)
        self.hist = 0.0

    def update(self, close: float):
        macd = self.ema_fast.update(close) - self.ema_slow.update(close)
        sig = self.ema_signal.update(macd)
        self.hist = macd - sig
        return MACDState(macd, sig, self.hist)


class VolumeSMA:
    def __init__(self, period=20):
        self.period = period
        self.buf = []

    def update(self, v):
        self.buf.append(v)
        if len(self.buf) > self.period:
            self.buf.pop(0)
        return sum(self.buf) / len(self.buf)


class DirectionalVolume:
    def __init__(self):
        self.prev = None
        self.value = 0.0

    def update(self, close, volume):
        if self.prev is None:
            self.prev = close
            return 0.0
        self.value = volume if close > self.prev else -volume if close < self.prev else 0.0
        self.prev = close
        return self.value
