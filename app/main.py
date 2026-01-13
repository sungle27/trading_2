from __future__ import annotations
import asyncio, json, time
from typing import Dict

import aiohttp

from .config import (
    BINANCE_FUTURES_WS,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    COOLDOWN_SEC,
    SPREAD_MAX,
)

from .symbols import FALLBACK_SYMBOLS
from .telegram import send_telegram
from .resample import TimeframeResampler
from .indicators import RSI, EMA, MACD, VolumeSMA, DirectionalVolume
from .alert_engine import ctx_filters_signal, should_alert
from .utils import backoff_s


# ============================================================
# SYMBOL STATE
# ============================================================
class SymbolState:
    def __init__(self):
        # ---- market data ----
        self.bid = None
        self.ask = None
        self.cur_sec = None

        # ---- volume accumulators ----
        self.vol_5m_acc = 0.0
        self.vol_15m_acc = 0.0

        # ---- timeframe counters ----
        self.h_counter = 0

        # ---- resamplers ----
        self.r5m = TimeframeResampler(5 * 60)
        self.r15m = TimeframeResampler(15 * 60)

        # ---- indicators ----
        self.rsi_5m = RSI()
        self.rsi_15m = RSI()

        self.ema20_15m = EMA(20)
        self.ema50_15m = EMA(50)
        self.macd_15m = MACD()

        self.ema50_1h = EMA(50)

        # ---- volume logic ----
        self.vol_sma_5m = VolumeSMA(20)
        self.vol_dir_5m = DirectionalVolume()
        self.vol_ratio_5m = 0.0
        self.vol_dir_5m_val = 0.0

        # ---- alert control ----
        self.last_alert_sec = 0

    def mid(self):
        if self.bid is None or self.ask is None:
            return None
        return (self.bid + self.ask) / 2.0

    def spread(self):
        m = self.mid()
        if not m:
            return 0.0
        return (self.ask - self.bid) / m


# ============================================================
# STREAMS
# ============================================================
async def ws_bookticker(states: Dict[str, SymbolState], url: str):
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
        except Exception:
            await asyncio.sleep(5)


async def ws_aggtrade(states: Dict[str, SymbolState], url: str):
    # ---- startup heartbeat ----
    await send_telegram(
        TELEGRAM_BOT_TOKEN,
        TELEGRAM_CHAT_ID,
        "✅ Crypto Alert Bot started (TEST / TRADE MODE ACTIVE)",
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
                        sec = data["T"] // 1000
                        qty = float(data["q"])

                        if st.cur_sec is None:
                            st.cur_sec = int(time.time())

                        # ====================================================
                        # HANDLE SECOND ADVANCE
                        # ====================================================
                        now_sec = int(time.time())

                        if now_sec > st.cur_sec:
                            mid = st.mid()
                            if mid:
                                closed5, did5 = st.r5m.update(st.cur_sec, mid, st.vol_5m_acc)
                                # DEBUG 1: confirm update() is called
                                if st.cur_sec % 60 == 0:  # mỗi phút log 1 lần
                                    asyncio.create_task(
                                        send_telegram(
                                            TELEGRAM_BOT_TOKEN,
                                            TELEGRAM_CHAT_ID,
                                            f"🧪 DEBUG update() called {sym} cur_sec={st.cur_sec}"
                                        )
                                    )
                                    # DEBUG 2: log did5
                                if st.cur_sec % 60 == 0:
                                    asyncio.create_task(
                                        send_telegram(
                                            TELEGRAM_BOT_TOKEN,
                                            TELEGRAM_CHAT_ID,
                                            f"🧪 DEBUG did5={did5} {sym}"
                                        )
                                    )

                                if did5:
                                    asyncio.create_task(
                                        send_telegram(
                                            TELEGRAM_BOT_TOKEN,
                                            TELEGRAM_CHAT_ID,
                                            f"🔥 DEBUG did5=True {sym}"
                                        )
                                    )
                                if did5 and closed5:
                                    # === DEBUG CONFIRM ===
                                    asyncio.create_task(
                                        send_telegram(
                                            TELEGRAM_BOT_TOKEN,
                                            TELEGRAM_CHAT_ID,
                                            f"⏱️ 5M CLOSED {sym} | vol_ratio={st.vol_ratio_5m:.2f}"
                                        )
                                    )

                                    # (giữ nguyên logic alert ở đây)

                                    st.vol_5m_acc = 0.0

                                closed15, did15 = st.r15m.update(st.cur_sec, mid, st.vol_15m_acc)
                                if did15 and closed15:
                                    # giữ nguyên logic 15m
                                    st.vol_15m_acc = 0.0

                            st.cur_sec = now_sec


                        # ====================================================
                        # ACCUMULATE VOLUME
                        # ====================================================
                        st.vol_5m_acc += qty
                        st.vol_15m_acc += qty

        except Exception:
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

    await asyncio.gather(
        ws_bookticker(states, url_book),
        ws_aggtrade(states, url_trade),
    )


if __name__ == "__main__":
    asyncio.run(main())
