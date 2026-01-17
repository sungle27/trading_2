from __future__ import annotations

import asyncio
import json
import time
from typing import Dict

import aiohttp

from .config import (
    BINANCE_FUTURES_WS,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    ALERT_PROFILE,
    COOLDOWN_SEC,
    SPREAD_MAX,
)

from .symbols import FALLBACK_SYMBOLS
from .telegram import send_telegram
from .indicators import RSI, EMA, MACD, VolumeSMA, DirectionalVolume
from .alert_engine import ctx_filters_signal, should_alert
from .utils import backoff_s


# ============================================================
# SYMBOL STATE
# ============================================================
class SymbolState:
    def __init__(self):
        # market
        self.bid = None
        self.ask = None

        # buckets
        self.last_5m_bucket = None
        self.last_15m_bucket = None

        # close price
        self.close_5m = None
        self.close_15m = None

        # volume
        self.vol_5m = 0.0
        self.vol_15m = 0.0

        # indicators
        self.rsi_5m = RSI(14)
        self.rsi_15m = RSI(14)

        self.ema20_15m = EMA(20)
        self.ema50_15m = EMA(50)
        self.macd_15m = MACD()
        self.ema50_1h = EMA(50)

        self.vol_sma_5m = VolumeSMA(20)
        self.vol_dir_5m = DirectionalVolume()

        self.vol_ratio_5m = 0.0
        self.vol_dir_5m_val = 0.0

        # alert control
        self.last_alert_sec = 0

    def mid(self):
        if self.bid is None or self.ask is None:
            return None
        return (self.bid + self.ask) / 2

    def spread(self):
        m = self.mid()
        if not m:
            return 0.0
        return (self.ask - self.bid) / m


# ============================================================
# WS: BOOK TICKER
# ============================================================
async def ws_bookticker(states: Dict[str, SymbolState], url: str):
    print(">>> ws_bookticker started")
    while True:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.ws_connect(url, heartbeat=30) as ws:
                    async for msg in ws:
                        data = json.loads(msg.data).get("data", {})
                        sym = data.get("s")
                        if sym in states:
                            states[sym].bid = float(data["b"])
                            states[sym].ask = float(data["a"])
        except Exception as e:
            print("bookticker error:", e)
            await asyncio.sleep(5)


# ============================================================
# WS: AGG TRADE (CORE LOOP)
# ============================================================
async def ws_aggtrade(states: Dict[str, SymbolState], url: str):
    print(">>> ws_aggtrade started")

    # ---- START MESSAGE (BẮT BUỘC) ----
    await send_telegram(
        TELEGRAM_BOT_TOKEN,
        TELEGRAM_CHAT_ID,
        f"✅ Bot STARTED | PROFILE={ALERT_PROFILE.upper()} | symbols={len(states)}",
    )

    while True:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.ws_connect(url, heartbeat=30) as ws:
                    async for msg in ws:
                        data = json.loads(msg.data).get("data", {})
                        sym = data.get("s")
                        if sym not in states:
                            continue

                        st = states[sym]
                        qty = float(data["q"])
                        mid = st.mid()
                        if mid is None:
                            continue

                        now = int(time.time())

                        # =======================
                        # 5M BUCKET
                        # =======================
                        bucket_5m = now // 300
                        if st.last_5m_bucket is None:
                            st.last_5m_bucket = bucket_5m

                        if bucket_5m != st.last_5m_bucket:
                            if st.close_5m is not None:
                                # update indicators
                                st.rsi_5m.update(st.close_5m)

                                vol = st.vol_5m
                                sma = st.vol_sma_5m.update(vol)
                                st.vol_ratio_5m = vol / sma if sma else 0.0
                                st.vol_dir_5m_val = st.vol_dir_5m.update(
                                    st.close_5m, vol
                                )

                                ctx = {
                                    "rsi": st.rsi_5m.value,
                                    "rsi15": st.rsi_15m.value,
                                    "ema20": st.ema20_15m.value,
                                    "ema50": st.ema50_15m.value,
                                    "ema50_1h": st.ema50_1h.value,
                                    "macd": st.macd_15m.hist,
                                    "vol_ratio": st.vol_ratio_5m,
                                    "vol_dir": st.vol_dir_5m_val,
                                }

                                spread = st.spread()

                                # -------- LONG --------
                                ok_ctx, reasons = ctx_filters_signal(ctx, "LONG")
                                if ok_ctx:
                                    ok_alert, _ = should_alert(
                                        now_s=now,
                                        last_alert_sec=st.last_alert_sec,
                                        spread=spread,
                                    )
                                    if ok_alert:
                                        st.last_alert_sec = now
                                        asyncio.create_task(
                                            send_telegram(
                                                TELEGRAM_BOT_TOKEN,
                                                TELEGRAM_CHAT_ID,
                                                f"🚨 LONG {sym}\nPrice: {st.close_5m:.6f}",
                                            )
                                        )

                                # -------- SHORT --------
                                ok_ctx, reasons = ctx_filters_signal(ctx, "SHORT")
                                if ok_ctx:
                                    ok_alert, _ = should_alert(
                                        now_s=now,
                                        last_alert_sec=st.last_alert_sec,
                                        spread=spread,
                                    )
                                    if ok_alert:
                                        st.last_alert_sec = now
                                        asyncio.create_task(
                                            send_telegram(
                                                TELEGRAM_BOT_TOKEN,
                                                TELEGRAM_CHAT_ID,
                                                f"🚨 SHORT {sym}\nPrice: {st.close_5m:.6f}",
                                            )
                                        )

                            # reset 5m
                            st.last_5m_bucket = bucket_5m
                            st.vol_5m = 0.0

                        st.close_5m = mid

                        # =======================
                        # 15M BUCKET
                        # =======================
                        bucket_15m = now // 900
                        if st.last_15m_bucket is None:
                            st.last_15m_bucket = bucket_15m

                        if bucket_15m != st.last_15m_bucket:
                            if st.close_15m is not None:
                                st.rsi_15m.update(st.close_15m)
                                st.ema20_15m.update(st.close_15m)
                                st.ema50_15m.update(st.close_15m)
                                st.macd_15m.update(st.close_15m)
                                st.ema50_1h.update(st.close_15m)

                            st.last_15m_bucket = bucket_15m
                            st.vol_15m = 0.0

                        st.close_15m = mid

                        # =======================
                        # VOLUME ACCUM
                        # =======================
                        st.vol_5m += qty
                        st.vol_15m += qty

        except Exception as e:
            print("aggtrade error:", e)
            await asyncio.sleep(backoff_s(1))


# ============================================================
# MAIN
# ============================================================
async def main():
    symbols = FALLBACK_SYMBOLS
    states = {s: SymbolState() for s in symbols}

    url_book = f"{BINANCE_FUTURES_WS}?streams=" + "/".join(
        f"{s.lower()}@bookTicker" for s in symbols
    )
    url_trade = f"{BINANCE_FUTURES_WS}?streams=" + "/".join(
        f"{s.lower()}@aggTrade" for s in symbols
    )

    print(f">>> starting bot | symbols={len(symbols)}")

    await asyncio.gather(
        ws_bookticker(states, url_book),
        ws_aggtrade(states, url_trade),
    )


if __name__ == "__main__":
    asyncio.run(main())
