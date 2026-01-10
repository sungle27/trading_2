import aiohttp
from typing import List

# fallback danh sách USDT thanh khoản cao (futures)
FALLBACK_SYMBOLS = [
    # ==================================================
    # CORE (anchor – luôn nên giữ)
    # ==================================================
    "BTCUSDT", "ETHUSDT",

    # ==================================================
    # STRONG MID-CAP – RẤT HỢP TREND + VOLUME
    # ==================================================
    "SOLUSDT", "AVAXUSDT", "LINKUSDT",
    "INJUSDT", "SEIUSDT", "TIAUSDT",
    "RNDRUSDT", "APTUSDT", "SUIUSDT",

    # ==================================================
    # L2 / INFRA – hay breakout
    # ==================================================
    "ARBUSDT", "OPUSDT", "IMXUSDT",
    "BLURUSDT", "MANTAUSDT", "STRKUSDT",

    # ==================================================
    # HIGH BETA / FAST MOVER (test volume spike)
    # ==================================================
    "WIFUSDT", "PEPEUSDT", "FLOKIUSDT",
    "BONKUSDT", "DOGEUSDT",

    # ==================================================
    # SMALL BUT VERY VOLATILE (FUTURES LIQUID)
    # ==================================================
    "ORDIUSDT", "JUPUSDT", "PYTHUSDT",
    "AEVOUSDT", "DYDXUSDT", "ENAUSDT",

    # ==================================================
    # OLD COINS – vẫn pump mạnh khi có tin
    # ==================================================
    "ETCUSDT", "LTCUSDT", "BCHUSDT",
    "NEARUSDT", "ATOMUSDT",

    # ==================================================
    # EXTREME (chỉ bật khi muốn stress test)
    # ==================================================
    "1000SHIBUSDT",
    "1000FLOKIUSDT",
    "1000BONKUSDT",
]


async def get_top_usdt_symbols(rest_base: str, top_n: int) -> List[str]:
    url = f"{rest_base}/fapi/v1/ticker/24hr"

    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=15) as r:
                # Binance block / legal block
                if r.status != 200:
                    raise RuntimeError(f"Binance REST error {r.status}")
                data = await r.json()

        rows = []
        for it in data:
            sym = it.get("symbol", "")
            if not sym.endswith("USDT"):
                continue
            try:
                qv = float(it.get("quoteVolume", 0.0))
            except Exception:
                qv = 0.0
            rows.append((qv, sym))

        rows.sort(reverse=True, key=lambda x: x[0])
        symbols = [sym for _, sym in rows[:top_n]]

        if not symbols:
            raise RuntimeError("Empty symbol list from Binance")

        print(f"[symbols] Loaded {len(symbols)} symbols from Binance REST")
        return symbols

    except Exception as e:
        # FALLBACK MODE
        fallback = FALLBACK_SYMBOLS[:top_n]
        print(f"[symbols] REST failed ({e}), fallback to {len(fallback)} hardcoded symbols")
        return fallback
