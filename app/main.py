from __future__ import annotations
import asyncio, json, time
from typing import Dict

import aiohttp

from .config import (
    BINANCE_FUTURES_WS, BINANCE_FUTURES_REST, TOP_N,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    COOLDOWN_SEC, SPREAD_MAX,
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

        # === Resamplers ===
        self.r5m = TimeframeResampler(5 * 60)
        self.r15m = TimeframeResampler(15 * 60)

        # === Indicators ===
        self.rsi_5m = RSI()
        self.rsi_15m = RSI()

        self.ema20_15m = EMA(20)
        self.ema50_15m = EMA(50)
        self.macd_15m = MACD()
        
        self.ema50_1h = EMA(50)

        # === Volume spike (5m) ===
        self.vol_sma_5m = VolumeSMA(20)
        self.vol_dir_5m = DirectionalVolume()
        self.vol_ratio_5m = 0.0
        self.vol_dir_5m_val = 0.0

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
    await send_telegram(
        TELEGRAM_BOT_TOKEN,
        TELEGRAM_CHAT_ID,
         f"✅ Bot started LLSUNG_VERSION_"
    )
    print(">>> ws_aggtrade STARTED")

    while True:
        try:
            print(">>> TICK RECEIVED", data.get("s"))

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
                                # ===== 5m trigger =====
                                closed5, did5 = st.r5m.update(st.cur_sec, mid, st.volume)
                                if did5:
                                    print(f">>> 5M CLOSED {sym} close={closed5.close if closed5 else None}")
                                if did5 and closed5:
                                    st.rsi_5m.update(closed5.close)

                                    vol = closed5.volume
                                    sma = st.vol_sma_5m.update(vol)
                                    st.vol_ratio_5m = vol / max(sma, 1e-9)
                                    st.vol_dir_5m_val = st.vol_dir_5m.update(closed5.close, vol)

                                # ===== 15m trend =====
                                closed15, did15 = st.r15m.update(st.cur_sec, mid, st.volume)
                                if did15 and closed15:
                                    st.rsi_15m.update(closed15.close)
                                    st.ema20_15m.update(closed15.close)
                                    st.ema50_15m.update(closed15.close)
                                    st.macd_15m.update(closed15.close)
                                    st.ema50_1h.update(closed15.close)

                                    ctx = {
                                        "rsi_5m": st.rsi_5m.value,
                                        "rsi_15m": st.rsi_15m.value,
                                        "ema20_15m": st.ema20_15m.value,
                                        "ema50_15m": st.ema50_15m.value,
                                        "ema50_1h": st.ema50_1h.value,
                                        "macd_hist_15m": st.macd_15m.hist,
                                        "vol_ratio_5m": st.vol_ratio_5m,
                                        "vol_dir_5m": st.vol_dir_5m_val,
                                    }

                                    now_s = int(time.time())
                                    spread = st.spread()
                                    print(
                                        f">>> CTX {sym}",
                                        f"rsi5={ctx.get('rsi_5m')}",
                                        f"rsi15={ctx.get('rsi_15m')}",
                                        f"vol_ratio={ctx.get('vol_ratio_5m')}",
                                        f"ema20={ctx.get('ema20_15m')}",
                                        f"ema50={ctx.get('ema50_15m')}",
                                    )
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
                                        ok, reasons = should_alert(...)
                                        if not ok:
                                            print(">>> ALERT FAIL REASON:", reasons)
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
