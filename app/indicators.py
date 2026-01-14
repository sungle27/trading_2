from __future__ import annotations
from collections import deque


# ============================================================
# RSI
# ============================================================
class RSI:
    """
    RSI chuẩn Wilder, update theo giá đóng cửa.
    - value = None khi chưa đủ dữ liệu
    """

    def __init__(self, period: int = 14):
        self.period = period
        self.gains = deque(maxlen=period)
        self.losses = deque(maxlen=period)
        self.prev_close = None
        self.value = None

    def update(self, close: float):
        if self.prev_close is None:
            self.prev_close = close
            return self.value

        change = close - self.prev_close
        self.prev_close = close

        gain = max(change, 0.0)
        loss = max(-change, 0.0)

        self.gains.append(gain)
        self.losses.append(loss)

        if len(self.gains) < self.period:
            self.value = None
            return self.value

        avg_gain = sum(self.gains) / self.period
        avg_loss = sum(self.losses) / self.period

        if avg_loss == 0:
            self.value = 100.0
        else:
            rs = avg_gain / avg_loss
            self.value = 100.0 - (100.0 / (1.0 + rs))

        return self.value


# ============================================================
# EMA
# ============================================================
class EMA:
    """
    EMA đơn giản cho realtime.
    - value = None khi chưa warm-up
    """

    def __init__(self, period: int):
        self.period = period
        self.mult = 2.0 / (period + 1.0)
        self.value = None

    def update(self, price: float):
        if self.value is None:
            # seed bằng giá đầu tiên
            self.value = price
        else:
            self.value = (price - self.value) * self.mult + self.value
        return self.value


# ============================================================
# MACD
# ============================================================
class MACD:
    """
    MACD chuẩn (12, 26, 9)
    Dùng hist làm momentum filter
    """

    def __init__(
        self,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ):
        self.ema_fast = EMA(fast)
        self.ema_slow = EMA(slow)
        self.ema_signal = EMA(signal)

        self.macd = None
        self.signal = None
        self.hist = None

    def update(self, price: float):
        fast_val = self.ema_fast.update(price)
        slow_val = self.ema_slow.update(price)

        if fast_val is None or slow_val is None:
            self.macd = None
            self.signal = None
            self.hist = None
            return self.hist

        self.macd = fast_val - slow_val
        sig = self.ema_signal.update(self.macd)

        if sig is None:
            self.signal = None
            self.hist = None
            return self.hist

        self.signal = sig
        self.hist = self.macd - self.signal
        return self.hist


# ============================================================
# Volume SMA
# ============================================================
class VolumeSMA:
    """
    SMA cho volume (dùng cho volume spike)
    """

    def __init__(self, period: int = 20):
        self.period = period
        self.values = deque(maxlen=period)

    def update(self, vol: float):
        self.values.append(vol)
        if len(self.values) < self.period:
            return None
        return sum(self.values) / self.period


# ============================================================
# Directional Volume
# ============================================================
class DirectionalVolume:
    """
    Đo hướng volume:
    +vol nếu giá tăng
    -vol nếu giá giảm

    Dùng để biết volume đang ủng hộ LONG hay SHORT
    """

    def __init__(self):
        self.prev_close = None
        self.value = 0.0

    def update(self, close: float, volume: float):
        if self.prev_close is None:
            self.prev_close = close
            self.value = 0.0
            return self.value

        if close > self.prev_close:
            self.value = abs(volume)
        elif close < self.prev_close:
            self.value = -abs(volume)
        else:
            self.value = 0.0

        self.prev_close = close
        return self.value
