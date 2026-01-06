import math
import random
from typing import List

def logret(a: float, b: float) -> float:
    if a <= 0 or b <= 0:
        return 0.0
    return math.log(a / b)

def rolling_std(xs: List[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    m = sum(xs) / n
    v = sum((x - m) ** 2 for x in xs) / (n - 1)
    return math.sqrt(v)

def backoff_s(attempt: int, base: float = 0.5, cap: float = 30.0) -> float:
    # exponential backoff + jitter
    t = min(cap, base * (2 ** attempt))
    return t * (0.7 + 0.6 * random.random())
