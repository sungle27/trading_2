import time
from datetime import datetime, timezone

def now_ts() -> int:
    return int(time.time())

def utc_now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
