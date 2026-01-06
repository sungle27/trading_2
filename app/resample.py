from dataclasses import dataclass
from typing import Optional, Tuple

@dataclass
class Candle:
    start_sec: int
    end_sec: int
    open: float
    high: float
    low: float
    close: float
    volume: float

class TimeframeResampler:
    def __init__(self, tf_sec: int):
        self.tf_sec = tf_sec
        self.cur_start: Optional[int] = None
        self.cur_end: Optional[int] = None
        self.o = self.h = self.l = self.c = None
        self.v = 0.0

    def update(self, sec: int, price: float, volume: float) -> Tuple[Optional[Candle], bool]:
        # Determine bucket
        start = (sec // self.tf_sec) * self.tf_sec
        end = start + self.tf_sec - 1

        if self.cur_start is None:
            self.cur_start, self.cur_end = start, end
            self.o = self.h = self.l = self.c = price
            self.v = volume
            return None, False

        # still in same candle
        if start == self.cur_start:
            self.h = max(self.h, price)
            self.l = min(self.l, price)
            self.c = price
            self.v += volume
            return None, False

        # candle closed
        closed = Candle(
            start_sec=self.cur_start,
            end_sec=self.cur_end,
            open=self.o,
            high=self.h,
            low=self.l,
            close=self.c,
            volume=self.v,
        )

        # start new candle
        self.cur_start, self.cur_end = start, end
        self.o = self.h = self.l = self.c = price
        self.v = volume
        return closed, True
