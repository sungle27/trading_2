from __future__ import annotations
import asyncio, json, math, time
from collections import deque
from dataclasses import dataclass
from typing import Dict, Optional, List, Tuple

import aiohttp

from .config import (
    BINANCE_FUTURES_WS, BINANCE_FUTURES_REST, TOP_N,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    MYSQL_ENABLED, MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD,
    MYSQL_DATABASE, MYSQL_BAR_TABLE, MYSQL_ALERT_TABLE,
    ALERT_MODE,
    COOLDOWN_SEC, ALERT_P_UP, ALERT_P_DOWN, FIXED_BPS, K_VOL, SPREAD_MAX,
    RSI_MODE, RSI_TF, RSI_OB, RSI_OS, RSI_COOLDOWN_SEC,
    MACD_MODE, MACD_TF, MACD_COOLDOWN_SEC,
    MODEL_REG_PATH, MODEL_CLF_PATH,
)

from .symbols import get_top_usdt_symbols
from .telegram import send_telegram
from .resample import TimeframeResampler
from .indicators import RSI, EMA, MACD, VolumeSMA, DirectionalVolume
from .alert_engine import ctx_filters_signal, should_alert
from .modeling import load_models, predict
from .mysql_writer import MySQLWriter, MySQLConfig
from .utils import logret, rolling_std, backoff_s

HORIZON_SEC = 120


# ============================================================
# CONTEXT INDICATORS
# ============================================================
@dataclass
class ContextIndicators:
    rsi_5m: RSI
    ema20_5m: EMA
    ema50_5m: EMA
    macd_5m: MACD

    rsi_15m: RSI
    ema20_15m: EMA
    ema50_15m: EMA
    macd_15m: MACD

    rsi_1h: RSI
    ema20_1h: EMA
    ema50_1h: EMA
    macd_1h: MACD

    rsi_4h: RSI
    ema20_4h: EMA
    ema50_4h: EMA
    macd_4h: MACD

    def snapshot(self) -> Dict[str, float]:
        def v(x, d=0.0): return float(x) if x is not None else d
        return {
            "rsi_5m": v(self.rsi_5m.value, 50.0),
            "rsi_15m": v(self.rsi_15m.value, 50.0),
            "rsi_1h": v(self.rsi_1h.value, 50.0),
            "rsi_4h": v(self.rsi_4h.value, 50.0),

            "ema20_5m": v(self.ema20_5m.value),
            "ema50_5m": v(self.ema50_5m.value),
            "ema20_15m": v(self.ema20_15m.value),
            "ema50_15m": v(self.ema50_15m.value),
            "ema20_1h": v(self.ema20_1h.value),
            "ema50_1h": v(self.ema50_1h.value),
            "ema20_4h": v(self.ema20_4h.value),
            "ema50_4h": v(self.ema50_4h.value),

            "macd_hist_5m": v(self.macd_5m.hist),
            "macd_hist_15m": v(self.macd_15m.hist),
            "macd_hist_1h": v(self.macd_1h.hist),
            "macd_hist_4h": v(self.macd_4h.hist),
        }


# ============================================================
# SYMBOL STATE
# ============================================================
class SymbolState:
    def __init__(self):
        self.bid = self.ask = None
        self.bid_qty = self.ask_qty = None

        self.cur_sec = None
        self.o = self.h = self.l = self.c = None
        self.volume = 0.0
        self.buy_volume = 0.0
        self.sell_volume = 0.0
        self.trade_count = 0

        self.mid_hist = deque(maxlen=900)
        self.ret_hist = deque(maxlen=900)

        self.r5m = TimeframeResampler(5 * 60)
        self.r15m = TimeframeResampler(15 * 60)
        self.r1h = TimeframeResampler(60 * 60)
        self.r4h = TimeframeResampler(4 * 60 * 60)

        self.ctx = ContextIndicators(
            rsi_5m=RSI(), ema20_5m=EMA(20), ema50_5m=EMA(50), macd_5m=MACD(),
            rsi_15m=RSI(), ema20_15m=EMA(20), ema50_15m=EMA(50), macd_15m=MACD(),
            rsi_1h=RSI(), ema20_1h=EMA(20), ema50_1h=EMA(50), macd_1h=MACD(),
            rsi_4h=RSI(), ema20_4h=EMA(20), ema50_4h=EMA(50), macd_4h=MACD(),
        )

        # ===== Volume spike state (15m) =====
        self.vol_sma_15m = VolumeSMA(period=20)
        self.vol_dir_15m = DirectionalVolume()
        self.vol_ratio_15m = 0.0
        self.vol_dir_value_15m = 0.0

        self.prev_rsi = None
        self.last_rsi_alert_sec = 0
        self.prev_macd_hist = None
        self.last_macd_alert_sec = 0
        self.last_alert_sec = 0

    def mid(self):
        if self.bid is None or self.ask is None:
            return None
        return (self.bid + self.ask) / 2.0

    def spread_ratio(self):
        m = self.mid()
        if m is None:
            return 0.0
        return (self.ask - self.bid) / m

    def reset_bar(self):
        self.o = self.h = self.l = self.c = None
        self.volume = self.buy_volume = self.sell_volume = 0.0
        self.trade_count = 0


# ============================================================
# HELPERS
# ============================================================
def update_context_from_closed_candle(st: SymbolState, tf: str, close_price: float):
    if tf == "5m":
        st.ctx.rsi_5m.update(close_price)
        st.ctx.ema20_5m.update(close_price)
        st.ctx.ema50_5m.update(close_price)
        st.ctx.macd_5m.update(close_price)
    elif tf == "15m":
        st.ctx.rsi_15m.update(close_price)
        st.ctx.ema20_15m.update(close_price)
        st.ctx.ema50_15m.update(close_price)
        st.ctx.macd_15m.update(close_price)
    elif tf == "1h":
        st.ctx.rsi_1h.update(close_price)
        st.ctx.ema20_1h.update(close_price)
        st.ctx.ema50_1h.update(close_price)
        st.ctx.macd_1h.update(close_price)
    elif tf == "4h":
        st.ctx.rsi_4h.update(close_price)
        st.ctx.ema20_4h.update(close_price)
        st.ctx.ema50_4h.update(close_price)
        st.ctx.macd_4h.update(close_price)


# ============================================================
# STREAMS
# ============================================================
async def ws_bookticker(states: Dict[str, SymbolState], url: str):
    attempt = 0
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(url, heartbeat=30) as ws:
                    attempt = 0
                    async for msg in ws:
                        if msg.type != aiohttp.WSMsgType.TEXT:
                            continue
                        payload = json.loads(msg.data).get("data", {})
                        sym = payload.get("s")
                        if sym in states:
                            st = states[sym]
                            st.bid = float(payload["b"])
                            st.ask = float(payload["a"])
        except Exception:
            attempt += 1
            await asyncio.sleep(backoff_s(attempt))


async def ws_aggtrade(states: Dict[str, SymbolState], url: str):
    attempt = 0
    await send_telegram(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, "✅ Bot started (volume spike enabled)")

    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(url, heartbeat=30) as ws:
                    attempt = 0
                    async for msg in ws:
                        if msg.type != aiohttp.WSMsgType.TEXT:
                            continue
                        payload = json.loads(msg.data).get("data", {})
                        sym = payload.get("s")
                        if sym not in states:
                            continue

                        st = states[sym]
                        sec = payload["T"] // 1000
                        price = float(payload["p"])
                        qty = float(payload["q"])
                        is_sell = payload["m"]

                        if st.cur_sec is None:
                            st.cur_sec = sec
                            st.o = st.h = st.l = st.c = price

                        while sec > st.cur_sec:
                            mid = st.mid()
                            if mid:
                                for tf, res in [("5m", st.r5m), ("15m", st.r15m), ("1h", st.r1h), ("4h", st.r4h)]:
                                    closed, did_close = res.update(st.cur_sec, mid, st.volume)
                                    if did_close and closed:
                                        update_context_from_closed_candle(st, tf, closed.close)
                                        if tf == "15m":
                                            vol = float(getattr(closed, "volume", 0.0))
                                            close = float(getattr(closed, "close", 0.0))
                                            sma = st.vol_sma_15m.update(vol)
                                            st.vol_ratio_15m = vol / max(sma, 1e-9)
                                            st.vol_dir_value_15m = st.vol_dir_15m.update(close, vol)

                                ctx = st.ctx.snapshot()
                                ctx["vol_ratio_15m"] = st.vol_ratio_15m
                                ctx["vol_dir_15m"] = st.vol_dir_value_15m

                                spread = st.spread_ratio()
                                now_s = int(time.time())

                                if should_alert(
                                    side="LONG",
                                    mid=mid,
                                    spread=spread,
                                    ctx=ctx,
                                    now_s=now_s,
                                    last_alert_sec=st.last_alert_sec,
                                    cooldown_sec=COOLDOWN_SEC,
                                    spread_max=SPREAD_MAX,
                                ):
                                    st.last_alert_sec = now_s
                                    asyncio.create_task(
                                        send_telegram(
                                            TELEGRAM_BOT_TOKEN,
                                            TELEGRAM_CHAT_ID,
                                            f"🚨 STRONG SIGNAL {sym}\n"
                                            f"Volume spike={st.vol_ratio_15m:.2f}x"
                                        )
                                    )

                            st.cur_sec += 1
                            st.reset_bar()

                        st.c = price
                        st.volume += qty
                        if is_sell:
                            st.sell_volume += qty
                        else:
                            st.buy_volume += qty

        except Exception:
            attempt += 1
            await asyncio.sleep(backoff_s(attempt))


# ============================================================
# MAIN
# ============================================================
async def run():
    symbols = await get_top_usdt_symbols(BINANCE_FUTURES_REST, TOP_N)
    states = {s: SymbolState() for s in symbols}

    url_book = f"{BINANCE_FUTURES_WS}?streams=" + "/".join(f"{s.lower()}@bookTicker" for s in symbols)
    url_trade = f"{BINANCE_FUTURES_WS}?streams=" + "/".join(f"{s.lower()}@aggTrade" for s in symbols)

    await asyncio.gather(
        ws_bookticker(states, url_book),
        ws_aggtrade(states, url_trade),
    )


if __name__ == "__main__":
    asyncio.run(run())
