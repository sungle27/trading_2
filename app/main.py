from __future__ import annotations
import asyncio, json, time
from collections import deque
from typing import Dict

import aiohttp

from .config import (
    BINANCE_FUTURES_WS, BINANCE_FUTURES_REST, TOP_N,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    ALERT_MODE, COOLDOWN_SEC, SPREAD_MAX,
)

from .symbols import get_top_usdt_symbols
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
        self.bid = self.ask = None
        self.cur_sec = None
        self.volume = 0.0

        self.r15m = TimeframeResampler(15 * 60)

        self.rsi_15m = RSI()
        self.ema20_15m = EMA(20)
        self.ema50_15m = EMA(50)
        self.macd_15m = MACD()

        self.ema50_1h = EMA(50)

        self.vol_sma_15m = VolumeSMA(20)
        self.vol_dir_15m = DirectionalVolume()
        self.vol_ratio_15m = 0.0
        self.vol_dir_val = 0.0

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
    await send_telegram(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, "✅ Bot started (explainable alerts)")

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
                        price = float(data["p"])
                        qty = float(data["q"])

                        if st.cur_sec is None:
                            st.cur_sec = sec

                        while sec > st.cur_sec:
                            mid = st.mid()
                            if mid:
                                closed, did_close = st.r15m.update(st.cur_sec, mid, st.volume)
                                if did_close and closed:
                                    st.rsi_15m.update(closed.close)
                                    st.ema20_15m.update(closed.close)
                                    st.ema50_15m.update(closed.close)
                                    st.macd_15m.update(closed.close)
                                    st.ema50_1h.update(closed.close)

                                    vol = closed.volume
                                    sma = st.vol_sma_15m.update(vol)
                                    st.vol_ratio_15m = vol / max(sma, 1e-9)
                                    st.vol_dir_val = st.vol_dir_15m.update(closed.close, vol)

                                    ctx = {
                                        "rsi_15m": st.rsi_15m.value,
                                        "ema20_15m": st.ema20_15m.value,
                                        "ema50_15m": st.ema50_15m.value,
                                        "ema50_1h": st.ema50_1h.value,
                                        "macd_hist_15m": st.macd_15m.hist,
                                        "vol_ratio_15m": st.vol_ratio_15m,
                                        "vol_dir_15m": st.vol_dir_val,
                                    }

                                    now_s = int(time.time())
                                    spread = st.spread()

                                    if ctx_filters_signal(ctx, "LONG"):
                                        ok, reasons = should_alert(
                                            side="LONG",
                                            mid=mid,
                                            spread=spread,
                                            ctx=ctx,
                                            now_s=now_s,
                                            last_alert_sec=st.last_alert_sec,
                                            cooldown_sec=COOLDOWN_SEC,
                                            spread_max=SPREAD_MAX,
                                        )

                                        if ok:
                                            st.last_alert_sec = now_s
                                            reason_txt = "\n".join(f"- {r}" for r in reasons)

                                            msg = (
                                                f"🚨 STRONG LONG SIGNAL {sym}\n"
                                                f"Price: {mid:.6f}\n\n"
                                                f"📌 Reasons:\n{reason_txt}"
                                            )

                                            asyncio.create_task(
                                                send_telegram(
                                                    TELEGRAM_BOT_TOKEN,
                                                    TELEGRAM_CHAT_ID,
                                                    msg,
                                                )
                                            )

                            st.cur_sec += 1
                            st.volume = 0.0

                        st.volume += qty

        except Exception:
            await asyncio.sleep(backoff_s(1))


# ============================================================
# MAIN
# ============================================================
async def main():
    symbols = await get_top_usdt_symbols(BINANCE_FUTURES_REST, TOP_N)
    states = {s: SymbolState() for s in symbols}

    url_book = f"{BINANCE_FUTURES_WS}?streams=" + "/".join(f"{s.lower()}@bookTicker" for s in symbols)
    url_trade = f"{BINANCE_FUTURES_WS}?streams=" + "/".join(f"{s.lower()}@aggTrade" for s in symbols)

    await asyncio.gather(
        ws_bookticker(states, url_book),
        ws_aggtrade(states, url_trade),
    )


if __name__ == "__main__":
    asyncio.run(main())
