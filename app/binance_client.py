import requests
from typing import List, Tuple

class BinanceFuturesClient:
    def __init__(self, rest_base: str):
        self.rest_base = rest_base.rstrip("/")

    def top_symbols_by_quote_volume(self, top_n: int) -> List[str]:
        url = f"{self.rest_base}/fapi/v1/ticker/24hr"
        data = requests.get(url, timeout=10).json()
        data.sort(key=lambda x: float(x.get("quoteVolume", 0.0)), reverse=True)
        syms = [x["symbol"] for x in data if x.get("symbol", "").endswith("USDT")]
        return syms[:top_n]

    def book_ticker(self, symbol: str) -> Tuple[float, float]:
        url = f"{self.rest_base}/fapi/v1/ticker/bookTicker?symbol={symbol}"
        j = requests.get(url, timeout=10).json()
        return float(j["bidPrice"]), float(j["askPrice"])

    def klines_close(self, symbol: str, interval: str = "1m", limit: int = 240) -> List[float]:
        url = f"{self.rest_base}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
        rows = requests.get(url, timeout=10).json()
        return [float(r[4]) for r in rows]  # close
