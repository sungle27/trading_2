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


class SymbolState:
    def __init__(self):
        self.bid = self.ask = None
        self.cur_sec = None

        self.vol_5m_acc = 0.0
        self.vol_15m_acc = 0.0
        self.h_counter = 0

        self.r5m = TimeframeResampler(5 * 60)
        self.r15m = TimeframeResampler(15 * 60)

        self.rsi_5m = RSI()
        self.rsi_15m = RSI()

        self.ema20_15m = EMA(20)
        self.ema50_15m = EMA(50)
        self.macd_15m = MACD()
        self.ema50_1h = EMA(50)

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
        "✅ Bot started – ALERT ENGINE ACTIVE"
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
                        price = float(data["p"])
                        qty = float(data["q"])

                        if st.cur_sec is None:
                            st.cur_sec = sec

                        while sec > st.cur_sec:
                            mid = st.mid()
                            if mid:
                                # ===== 5m =====
                                closed5, did5 = st.r5m.update(st.cur_sec, mid, st.vol_5m_acc)
                                if did5 and closed5:
                                    st.rsi_5m.update(closed5.close)

                                    vol = closed5.volume
                                    sma = st.vol_sma_5m.update(vol)
                                    st.vol_ratio_5m = vol / max(sma, 1e-9)
                                    st.vol_dir_5m_val = st.vol_dir_5m.update(closed5.close, vol)

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
                                            msg = (
                                                f"🚨 STRONG LONG SIGNAL {sym}\n"
                                                f"Price: {mid:.6f}\n\n"
                                                + "\n".join(f"- {r}" for r in reasons)
                                            )
                                            asyncio.create_task(
                                                send_telegram(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, msg)
                                            )

                                    st.vol_5m_acc = 0.0

                                # ===== 15m =====
                                closed15, did15 = st.r15m.update(st.cur_sec, mid, st.vol_15m_acc)
                                if did15 and closed15:
                                    st.rsi_15m.update(closed15.close)
                                    st.ema20_15m.update(closed15.close)
                                    st.ema50_15m.update(closed15.close)
                                    st.macd_15m.update(closed15.close)

                                    st.h_counter += 1
                                    if st.h_counter % 4 == 0:
                                        st.ema50_1h.update(closed15.close)

                                    st.vol_15m_acc = 0.0

                            st.cur_sec += 1

                        st.vol_5m_acc += qty
                        st.vol_15m_acc += qty

        except Exception:
            await asyncio.sleep(backoff_s(1))


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
