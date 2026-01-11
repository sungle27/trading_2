from __future__ import annotations

import asyncio
import json
import time
from typing import Dict, Optional

import aiohttp

from .config import (
    BINANCE_FUTURES_WS,
    BINANCE_FUTURES_REST,
    TOP_N,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    COOLDOWN_SEC,
    SPREAD_MAX,
)


from .symbols import get_top_usdt_symbols
from .telegram import send_telegram
from .resample import TimeframeResampler
from .indicators import RSI, EMA, MACD, VolumeSMA, DirectionalVolume
from .alert_engine import ctx_filters_signal, should_alert
from .utils import backoff_s

from .symbols import FALLBACK_SYMBOLS
from .config import TEST_MODE

print(f">>> ALERT ENGINE MODE = {TEST_MODE}")

# ============================================================
# BASIC LOGGER
# ============================================================
def log(*args):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), *args, flush=True)


# ============================================================
# TELEGRAM HELPERS (ANTI-SPAM)
# ============================================================
_last_tg_cycle = {}

async def send_cycle(symbol: str, key: str, text: str, cooldown: int = 20):
    now = int(time.time())
    k = f"{symbol}:{key}"
    if now - _last_tg_cycle.get(k, 0) < cooldown:
        return
    _last_tg_cycle[k] = now
    await send_telegram(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, text)


async def send_state(symbol: str, state: str, price: float, body: str):
    emoji = {"LONG": "🟢", "SHORT": "🔴", "NO ACTION": "⚪"}.get(state, "❔")
    msg = (
        f"{emoji} STATE {state} {symbol}\n"
        f"Price: {price:.6f}\n\n"
        f"{body}"
    )
    await send_telegram(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, msg)


# ============================================================
# SYMBOL STATE
# ============================================================
class SymbolState:
    def __init__(self):
        self.bid: Optional[float] = None
        self.ask: Optional[float] = None

        self.cur_sec: Optional[int] = None
        self.volume: float = 0.0

        # Resample
        self.r5m = TimeframeResampler(5 * 60)
        self.r15m = TimeframeResampler(15 * 60)

        # Indicators
        self.rsi_5m = RSI()
        self.rsi_15m = RSI()
        self.ema20_15m = EMA(20)
        self.ema50_15m = EMA(50)
        self.macd_15m = MACD()
        self.ema50_1h = EMA(50)

        # Volume (5m)
        self.vol_sma_5m = VolumeSMA(20)
        self.vol_dir_5m = DirectionalVolume()
        self.vol_ratio_5m = 0.0
        self.vol_dir_5m_val = 0.0

        self.last_alert_sec = 0

    def mid(self) -> Optional[float]:
        if self.bid is None or self.ask is None:
            return None
        return (self.bid + self.ask) / 2.0

    def spread(self) -> float:
        m = self.mid()
        if not m:
            return 0.0
        return (self.ask - self.bid) / m


# ============================================================
# BOOK TICKER
# ============================================================
async def ws_bookticker(states: Dict[str, SymbolState], url: str):
    attempt = 0
    while True:
        try:
            log("bookTicker connecting")
            async with aiohttp.ClientSession() as s:
                async with s.ws_connect(url, heartbeat=30) as ws:
                    attempt = 0
                    log("bookTicker connected")
                    async for msg in ws:
                        if msg.type != aiohttp.WSMsgType.TEXT:
                            continue
                        data = json.loads(msg.data).get("data", {})
                        sym = data.get("s")
                        if sym in states:
                            states[sym].bid = float(data["b"])
                            states[sym].ask = float(data["a"])
        except Exception as e:
            attempt += 1
            log("bookTicker error", repr(e))
            await asyncio.sleep(backoff_s(attempt))


# ============================================================
# AGGTRADE CORE
# ============================================================
async def ws_aggtrade(states: Dict[str, SymbolState], url: str):
    await send_telegram(
        TELEGRAM_BOT_TOKEN,
        TELEGRAM_CHAT_ID,
        "🚀 Bot started | TEST_MODE = {TEST_MODE}",
    )

    attempt = 0
    while True:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.ws_connect(url, heartbeat=30) as ws:
                    attempt = 0
                    log("aggTrade connected")

                    async for msg in ws:
                        if msg.type != aiohttp.WSMsgType.TEXT:
                            continue

                        data = json.loads(msg.data).get("data", {})
                        sym = data.get("s")
                        if sym not in states:
                            continue

                        st = states[sym]
                        sec = int(data["T"]) // 1000
                        qty = float(data["q"])

                        if st.cur_sec is None:
                            st.cur_sec = sec

                        while sec > st.cur_sec:
                            mid = st.mid()

                            if mid:
                                # ===== 5M =====
                                closed5, did5 = st.r5m.update(st.cur_sec, mid, st.volume)
                                if did5 and closed5:
                                    st.rsi_5m.update(closed5.close)
                                    vol = closed5.volume
                                    sma = st.vol_sma_5m.update(vol)
                                    st.vol_ratio_5m = vol / max(sma, 1e-9)
                                    st.vol_dir_5m_val = st.vol_dir_5m.update(closed5.close, vol)

                                    # await send_cycle(
                                    #     sym,
                                    #     "5m",
                                    #     (
                                    #         f"🕔 5M CLOSE {sym}\n"
                                    #         f"Price: {closed5.close:.6f}\n"
                                    #         f"Volume: {vol:.4f}\n"
                                    #         f"Vol ratio: {st.vol_ratio_5m:.2f}x\n"
                                    #         f"Vol dir: {st.vol_dir_5m_val:+.2f}\n"
                                    #         f"RSI(5m): {st.rsi_5m.value:.1f}"
                                    #     ),
                                    # )

                                # ===== 15M =====
                                closed15, did15 = st.r15m.update(st.cur_sec, mid, st.volume)
                                if did15 and closed15:
                                    st.rsi_15m.update(closed15.close)
                                    st.ema20_15m.update(closed15.close)
                                    st.ema50_15m.update(closed15.close)
                                    st.macd_15m.update(closed15.close)
                                    st.ema50_1h.update(closed15.close)

                                    # await send_cycle(
                                    #     sym,
                                    #     "15m",
                                    #     (
                                    #         f"🕒 15M CLOSE {sym}\n"
                                    #         f"Price: {closed15.close:.6f}\n"
                                    #         f"RSI(15m): {st.rsi_15m.value:.1f}\n"
                                    #         f"EMA20/50: {st.ema20_15m.value:.6f} / {st.ema50_15m.value:.6f}\n"
                                    #         f"MACD hist: {st.macd_15m.hist:.6f}"
                                    #     ),
                                    # )

                                # ===== STATE / ALERT =====
                                if did5 and closed5 and st.ema20_15m.value and st.ema50_15m.value:
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
                                    price = closed5.close

                                    for side in ("LONG", "SHORT"):
                                        ok, reasons = should_alert(
                                            side=side,
                                            mid=price,
                                            spread=spread,
                                            ctx=ctx,
                                            now_s=now_s,
                                            last_alert_sec=st.last_alert_sec,
                                            cooldown_sec=COOLDOWN_SEC,
                                            spread_max=SPREAD_MAX,
                                        )

                                        if ok:
                                            st.last_alert_sec = now_s
                                            await send_state(
                                                sym,
                                                side,
                                                price,
                                                "📌 Reasons:\n" + "\n".join(f"- {r}" for r in reasons),
                                            )
                                            break
                                    else:
                                        if st.vol_ratio_5m >= 1.2:
                                            await send_state(
                                                sym,
                                                "NO ACTION",
                                                price,
                                                (
                                                    f"Volume spike: {st.vol_ratio_5m:.2f}x\n"
                                                    f"RSI 5m / 15m: {st.rsi_5m.value:.1f} / {st.rsi_15m.value:.1f}\n"
                                                    f"EMA20/50: {st.ema20_15m.value:.6f} / {st.ema50_15m.value:.6f}"
                                                ),
                                            )

                            st.cur_sec += 1
                            st.volume = 0.0

                        st.volume += qty

        except Exception as e:
            attempt += 1
            log("aggTrade error", repr(e))
            await asyncio.sleep(backoff_s(attempt))


# ============================================================
# MAIN
# ============================================================
def build_url(symbols, suffix):
    return BINANCE_FUTURES_WS + "?streams=" + "/".join(f"{s.lower()}@{suffix}" for s in symbols)


async def main():
    log("main start")
    # symbols = await get_top_usdt_symbols(BINANCE_FUTURES_REST, TOP_N)
    symbols = FALLBACK_SYMBOLS
    log(f"Tracking {len(symbols)} symbols")

    states = {s: SymbolState() for s in symbols}

    await asyncio.gather(
        ws_bookticker(states, build_url(symbols, "bookTicker")),
        ws_aggtrade(states, build_url(symbols, "aggTrade")),
    )


if __name__ == "__main__":
    asyncio.run(main())
