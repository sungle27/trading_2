import random
import time

__all__ = ["backoff_s"]


def backoff_s(
    attempt: int,
    *,
    base: float = 1.0,
    cap: float = 30.0,
    jitter: bool = True,
) -> float:
    """
    Exponential backoff (seconds)

    attempt: số lần retry (0,1,2...)
    base: thời gian base (giây)
    cap: thời gian chờ tối đa
    jitter: thêm random jitter để tránh reconnect đồng loạt
    """

    delay = min(cap, base * (2 ** attempt))

    if jitter:
        delay = delay * (0.7 + random.random() * 0.6)

    return delay
