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
    TEST_MODE,
)

from .symbols import get_top_usdt_symbols, FALLBACK_SYMBOLS
from .telegram import send_telegram
from .resample import TimeframeResampler
from .indicators import RSI, EMA, MACD, VolumeSMA, DirectionalVolume
from .alert_engine import should_alert
from .utils import backoff_s


def log(*args):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), *args, flush=True)


# anti-spam telegram per symbol/key
_last_tg_cycle = {}


async def send_cycle(symbol: str, key: str, text: str, cooldown: int = 30):
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


class SymbolState:
    def __init__(self):
        self.bid: Optional[float] = None
        self.ask: Optional[float] = None

        self.cur_sec: Optional[int] = None
        self.volume: float = 0.0

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

    def mid(self) -> Optional[float]:
        if self.bid is None or self.ask is None:
            return None
        return (self.bid + self.ask) / 2.0

    def spread(self) -> float:
        m = self.mid()
        if not m:
            return 0.0
        return (self.ask - self.bid) / m


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


async def ws_aggtrade(states: Dict[str, SymbolState], url: str):
    await send_telegram(
        TELEGRAM_BOT_TOKEN,
        TELEGRAM_CHAT_ID,
        f"Bot started | TEST_MODE={TEST_MODE}",
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
                                # ===== 5m close =====
                                closed5, did5 = st.r5m.update(st.cur_sec, mid, st.volume)
                                if did5 and closed5:
                                    st.rsi_5m.update(closed5.close)

                                    vol = closed5.volume
                                    sma = st.vol_sma_5m.update(vol)
                                    st.vol_ratio_5m = vol / max(sma, 1e-9)
                                    st.vol_dir_5m_val = st.vol_dir_5m.update(closed5.close, vol)

                                    # debug cycle (optional)
                                    # await send_cycle(sym, "5m", f"5m close {sym} price={closed5.close:.6f} vol={vol:.2f} ratio={st.vol_ratio_5m:.2f} rsi5={st.rsi_5m.value:.1f}")

                                # ===== 15m close =====
                                closed15, did15 = st.r15m.update(st.cur_sec, mid, st.volume)
                                if did15 and closed15:
                                    st.rsi_15m.update(closed15.close)
                                    st.ema20_15m.update(closed15.close)
                                    st.ema50_15m.update(closed15.close)
                                    st.macd_15m.update(closed15.close)
                                    st.ema50_1h.update(closed15.close)

                                # ===== Evaluate at 5m close (khi đã có EMA 15m) =====
                                if did5 and closed5 and st.ema20_15m.value and st.ema50_15m.value:
                                    price = closed5.close
                                    spread = st.spread()
                                    now_s = int(time.time())

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

                                    # thử LONG trước, nếu fail mới thử SHORT
                                    ok, reasons = should_alert(
                                        side="LONG",
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
                                        await send_state(sym, "LONG", price, "📌 Reasons:\n" + "\n".join(f"- {r}" for r in reasons))
                                    else:
                                        ok2, reasons2 = should_alert(
                                            side="SHORT",
                                            mid=price,
                                            spread=spread,
                                            ctx=ctx,
                                            now_s=now_s,
                                            last_alert_sec=st.last_alert_sec,
                                            cooldown_sec=COOLDOWN_SEC,
                                            spread_max=SPREAD_MAX,
                                        )
                                        if ok2:
                                            st.last_alert_sec = now_s
                                            await send_state(sym, "SHORT", price, "📌 Reasons:\n" + "\n".join(f"- {r}" for r in reasons2))
                                        else:
                                            # chỉ log NO ACTION khi có volume spike đáng kể
                                            if st.vol_ratio_5m >= 1.2:
                                                await send_state(
                                                    sym,
                                                    "NO ACTION",
                                                    price,
                                                    (
                                                        f"Volume spike: {st.vol_ratio_5m:.2f}x\n"
                                                        f"RSI 5m / 15m: {st.rsi_5m.value:.1f} / {st.rsi_15m.value:.1f}\n"
                                                        f"EMA20/50: {st.ema20_15m.value:.6f} / {st.ema50_15m.value:.6f}\n"
                                                        f"LONG fail: {', '.join(reasons) if reasons else 'n/a'}\n"
                                                        f"SHORT fail: {', '.join(reasons2) if reasons2 else 'n/a'}"
                                                    ),
                                                )

                            st.cur_sec += 1
                            st.volume = 0.0

                        st.volume += qty

        except Exception as e:
            attempt += 1
            log("aggTrade error", repr(e))
            await asyncio.sleep(backoff_s(attempt))


def build_url(symbols, suffix):
    return BINANCE_FUTURES_WS + "?streams=" + "/".join(f"{s.lower()}@{suffix}" for s in symbols)


async def main():
    log("main start")
    log(f">>> CONFIG TEST_MODE={TEST_MODE}")

    # PROD: dùng top symbols
    # symbols = await get_top_usdt_symbols(BINANCE_FUTURES_REST, TOP_N)

    # TEST: dùng fallback cố định
    symbols = FALLBACK_SYMBOLS

    log(f"Tracking {len(symbols)} symbols: {symbols}")

    states = {s: SymbolState() for s in symbols}

    await asyncio.gather(
        ws_bookticker(states, build_url(symbols, "bookTicker")),
        ws_aggtrade(states, build_url(symbols, "aggTrade")),
    )


if __name__ == "__main__":
    asyncio.run(main())
