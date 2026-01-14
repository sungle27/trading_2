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

        # ---- bucket trackers ----
        self.last_5m_bucket = None
        self.last_15m_bucket = None

        # ---- running closes for bucket (proxy candle close) ----
        self.close_5m = None
        self.close_15m = None

        # ---- volume accumulators per bucket ----
        self.vol_5m_acc = 0.0
        self.vol_15m_acc = 0.0

        # ---- indicators ----
        self.rsi_5m = RSI()
        self.rsi_15m = RSI()

        self.ema20_15m = EMA(20)
        self.ema50_15m = EMA(50)
        self.macd_15m = MACD()

        # NOTE: bạn đang dùng EMA50_1h như HTF filter
        # Ở đây update theo 15m close (mỗi 15m), đủ dùng cho alert bot
        self.ema50_1h = EMA(50)

        # ---- volume features (5m) ----
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
                        qty = float(data["q"])

                        mid = st.mid()
                        if mid is None:
                            continue

                        now = int(time.time())

                        # ====================================================
                        # 5M BUCKET (TRIGGER)
                        # ====================================================
                        bucket_5m = now // 300  # 300s = 5 minutes
                        if st.last_5m_bucket is None:
                            st.last_5m_bucket = bucket_5m

                        # bucket changed => close previous 5m "candle"
                        if bucket_5m != st.last_5m_bucket:
                            asyncio.create_task(
                            send_telegram(
                                TELEGRAM_BOT_TOKEN,
                                TELEGRAM_CHAT_ID,
                                f"""🧪 TRADE DEBUG {sym}
                        RSI5={st.rsi_5m.value}
                        RSI15={st.rsi_15m.value}
                        EMA20/50={st.ema20_15m.value:.4f}/{st.ema50_15m.value:.4f}
                        MACD_hist={st.macd_15m.hist}
                        VOL_ratio={st.vol_ratio_5m:.2f}
                        Spread={st.spread():.5f}
                        """
                            )
                        )

                            if st.close_5m is not None:
                                # ---- update 5m RSI ----
                                st.rsi_5m.update(st.close_5m)

                                # ---- volume features ----
                                vol = st.vol_5m_acc
                                sma = st.vol_sma_5m.update(vol)
                                st.vol_ratio_5m = vol / max(sma, 1e-9)
                                st.vol_dir_5m_val = st.vol_dir_5m.update(st.close_5m, vol)

                                # ---- build ctx ----
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

                                now_s = now
                                spread = st.spread()

                                # ---- LONG (giữ đúng cấu trúc cũ) ----
                                if ctx_filters_signal(ctx, "LONG"):
                                    ok, reasons = should_alert(
                                        side="LONG",
                                        mid=st.close_5m,          # dùng close của bucket 5m
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
                                            f"🚨 LONG SIGNAL {sym}\n"
                                            f"Price: {st.close_5m:.6f}\n\n"
                                            "📌 Reasons:\n" + "\n".join(f"- {r}" for r in reasons)
                                        )
                                        asyncio.create_task(
                                            send_telegram(
                                                TELEGRAM_BOT_TOKEN,
                                                TELEGRAM_CHAT_ID,
                                                msg,
                                            )
                                        )

                                    if not ok_ctx:
                                        asyncio.create_task(
                                            send_telegram(
                                                TELEGRAM_BOT_TOKEN,
                                                TELEGRAM_CHAT_ID,
                                                f"❌ CTX REJECT {sym}: {', '.join(ctx_reasons)}"
                                            )
                                        )

                                # ---- SHORT SIGNAL ----
                                if ctx_filters_signal(ctx, "SHORT"):
                                    ok, reasons = should_alert(
                                        side="SHORT",
                                        mid=st.close_5m,
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
                                            f"🚨 SHORT SIGNAL {sym}\n"
                                            f"Price: {st.close_5m:.6f}\n\n"
                                            "📌 Reasons:\n" + "\n".join(f"- {r}" for r in reasons)
                                        )
                                        asyncio.create_task(
                                            send_telegram(
                                                TELEGRAM_BOT_TOKEN,
                                                TELEGRAM_CHAT_ID,
                                                msg,
                                            )
                                        )

                            # reset for new 5m bucket
                            st.last_5m_bucket = bucket_5m
                            st.vol_5m_acc = 0.0

                        # update running close for current 5m bucket
                        st.close_5m = mid

                        # ====================================================
                        # 15M BUCKET (CONTEXT)
                        # ====================================================
                        bucket_15m = now // 900  # 900s = 15 minutes
                        if st.last_15m_bucket is None:
                            st.last_15m_bucket = bucket_15m

                        if bucket_15m != st.last_15m_bucket:
                            if st.close_15m is not None:
                                st.rsi_15m.update(st.close_15m)
                                st.ema20_15m.update(st.close_15m)
                                st.ema50_15m.update(st.close_15m)
                                st.macd_15m.update(st.close_15m)

                                # HTF proxy: update EMA50_1h theo 15m close
                                st.ema50_1h.update(st.close_15m)

                            st.last_15m_bucket = bucket_15m
                            st.vol_15m_acc = 0.0

                        st.close_15m = mid

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
