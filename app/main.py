from __future__ import annotations
import asyncio, json, math, time
from collections import deque
from dataclasses import dataclass
from typing import Dict, Optional, List, Tuple

import aiohttp

from .config import (
    BINANCE_FUTURES_WS, BINANCE_FUTURES_REST, TOP_N,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    MYSQL_ENABLED, MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE, MYSQL_BAR_TABLE, MYSQL_ALERT_TABLE,
    ALERT_MODE,
    COOLDOWN_SEC, ALERT_P_UP, ALERT_P_DOWN, FIXED_BPS, K_VOL, SPREAD_MAX,
    RSI_MODE, RSI_TF, RSI_OB, RSI_OS, RSI_COOLDOWN_SEC,
    MACD_MODE, MACD_TF, MACD_COOLDOWN_SEC,
    MODEL_REG_PATH, MODEL_CLF_PATH,
)

from .symbols import get_top_usdt_symbols
from .telegram import send_telegram
from .resample import TimeframeResampler
from .indicators import RSI, EMA, MACD
from .modeling import load_models, predict
from .mysql_writer import MySQLWriter, MySQLConfig
from .utils import logret, rolling_std, backoff_s
#bo sung 10-01-2026 ->
from indicators import VolumeSMA, DirectionalVolume

vol_sma_15m = VolumeSMA(period=20)
vol_dir_15m = DirectionalVolume()
vol = candle.volume
close = candle.close

vol_sma = vol_sma_15m.update(vol)
vol_dir = vol_dir_15m.update(close, vol)

ctx["vol_15m"] = vol
ctx["vol_sma_15m"] = vol_sma
ctx["vol_ratio_15m"] = vol / max(vol_sma, 1e-9)
ctx["vol_dir_15m"] = vol_dir
#<-

HORIZON_SEC = 120

@dataclass
class ContextIndicators:
    # 5m
    rsi_5m: RSI
    ema20_5m: EMA
    ema50_5m: EMA
    macd_5m: MACD
    # 15m
    rsi_15m: RSI
    ema20_15m: EMA
    ema50_15m: EMA
    macd_15m: MACD
    # 1h
    rsi_1h: RSI
    ema20_1h: EMA
    ema50_1h: EMA
    macd_1h: MACD
    # 4h
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

class SymbolState:
    def __init__(self):
        self.bid: Optional[float] = None
        self.ask: Optional[float] = None
        self.bid_qty: Optional[float] = None
        self.ask_qty: Optional[float] = None

        self.cur_sec: Optional[int] = None
        self.o = self.h = self.l = self.c = None
        self.volume = 0.0
        self.buy_volume = 0.0
        self.sell_volume = 0.0
        self.trade_count = 0

        self.mid_hist = deque(maxlen=900)
        self.ret_hist = deque(maxlen=900)

        self.r5m = TimeframeResampler(5*60)
        self.r15m = TimeframeResampler(15*60)
        self.r1h = TimeframeResampler(60*60)
        self.r4h = TimeframeResampler(4*60*60)

        self.prev_rsi: Optional[float] = None
        self.last_rsi_alert_sec = 0

        self.prev_macd_hist: Optional[float] = None
        self.prev_macd_signal: Optional[float] = None
        self.last_macd_alert_sec = 0

        self.ctx = ContextIndicators(
            rsi_5m=RSI(14), ema20_5m=EMA(20), ema50_5m=EMA(50), macd_5m=MACD(),
            rsi_15m=RSI(14), ema20_15m=EMA(20), ema50_15m=EMA(50), macd_15m=MACD(),
            rsi_1h=RSI(14), ema20_1h=EMA(20), ema50_1h=EMA(50), macd_1h=MACD(),
            rsi_4h=RSI(14), ema20_4h=EMA(20), ema50_4h=EMA(50), macd_4h=MACD(),
        )

        self.last_alert_sec = 0

    def mid(self) -> Optional[float]:
        if self.bid is None or self.ask is None:
            return None
        return (self.bid + self.ask) / 2.0

    def spread_ratio(self) -> float:
        m = self.mid()
        if m is None or self.bid is None or self.ask is None:
            return 0.0
        return (self.ask - self.bid) / m

    def reset_bar(self):
        self.o = self.h = self.l = self.c = None
        self.volume = self.buy_volume = self.sell_volume = 0.0
        self.trade_count = 0

def baseline_inference(st: SymbolState) -> Tuple[float, float, float, float, float]:
    rets_10 = [r for _, r in list(st.ret_hist)[-10:]]
    rets_120 = [r for _, r in list(st.ret_hist)[-120:]]
    vol_120 = rolling_std(rets_120)
    mom_10 = sum(rets_10)
    pred_ret = mom_10 * 3.0
    p_up = 1 / (1 + math.exp(-pred_ret * 40))
    p_down = 1 - p_up
    p_flat = 0.05
    s = p_down + p_flat + p_up
    return pred_ret, p_down/s, p_flat/s, p_up/s, vol_120

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

def get_rsi(ctx: Dict[str, float], tf: str) -> float:
    return ctx.get(f"rsi_{tf}", ctx.get("rsi_5m", 50.0))

def get_macd_hist(ctx: Dict[str, float], tf: str) -> float:
    return ctx.get(f"macd_hist_{tf}", ctx.get("macd_hist_15m", 0.0))

def build_stream_url(symbols: List[str], stream_suffix: str) -> str:
    streams = [f"{s.lower()}@{stream_suffix}" for s in symbols]
    return f"{BINANCE_FUTURES_WS}?streams={'/'.join(streams)}"

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
                        data = json.loads(msg.data)
                        payload = data.get("data", {})
                        sym = payload.get("s")
                        if sym not in states:
                            continue
                        st = states[sym]
                        st.bid = float(payload["b"])
                        st.ask = float(payload["a"])
                        st.bid_qty = float(payload["B"])
                        st.ask_qty = float(payload["A"])
        except Exception as e:
            attempt += 1
            await asyncio.sleep(backoff_s(attempt))

async def ws_aggtrade(states: Dict[str, SymbolState], url: str, mysql: MySQLWriter | None):
    attempt = 0
    bar_batch = []
    last_flush = time.time()

    models = load_models(MODEL_REG_PATH, MODEL_CLF_PATH)
    use_ml = (models.reg is not None) or (models.clf is not None)
    print("Using ML models:", use_ml)

    await send_telegram(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, "TEST MESSAGE OK, version 1 [l.l.sung_10-01-2026 v1]")

    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(url, heartbeat=30) as ws:
                    attempt = 0
                    async for msg in ws:
                        if msg.type != aiohttp.WSMsgType.TEXT:
                            continue
                        data = json.loads(msg.data)
                        payload = data.get("data", {})
                        sym = payload.get("s")
                        if sym not in states:
                            continue
                        st = states[sym]

                        t_ms = int(payload["T"])
                        sec = t_ms // 1000
                        price = float(payload["p"])
                        qty = float(payload["q"])
                        is_buyer_maker = payload["m"]

                        if st.cur_sec is None:
                            st.cur_sec = sec
                            st.o = st.h = st.l = st.c = price

                        while st.cur_sec is not None and sec > st.cur_sec:
                            mid = st.mid()
                            if mid is not None:
                                prev_mid = st.mid_hist[-1][1] if st.mid_hist else None
                                r1 = logret(mid, prev_mid) if prev_mid else 0.0
                                st.mid_hist.append((st.cur_sec, mid))
                                st.ret_hist.append((st.cur_sec, r1))

                                for tf, res in [("5m", st.r5m), ("15m", st.r15m), ("1h", st.r1h), ("4h", st.r4h)]:
                                    closed, did_close = res.update(st.cur_sec, mid, st.volume)
                                    if did_close and closed is not None:
                                        update_context_from_closed_candle(st, tf, closed.close)

                                ctx = st.ctx.snapshot()
                                rets_120 = [r for _, r in list(st.ret_hist)[-120:]]
                                vol_120 = rolling_std(rets_120)
                                spread = st.spread_ratio()

                                # --- Predict (for signal mode) ---
                                if use_ml:
                                    pred_ret, proba = predict(models, {})
                                    if pred_ret is None or proba is None:
                                        pred_ret, p_down, p_flat, p_up, _ = baseline_inference(st)
                                    else:
                                        p_down, p_flat, p_up = proba
                                else:
                                    pred_ret, p_down, p_flat, p_up, _ = baseline_inference(st)

                                now_s = int(time.time())

                                # ========== ALERT MODES ==========
                                if ALERT_MODE == "rsi":
                                    rsi = get_rsi(ctx, RSI_TF)
                                    if (now_s - st.last_rsi_alert_sec) >= RSI_COOLDOWN_SEC:
                                        if RSI_MODE == "threshold":
                                            if rsi <= RSI_OS:
                                                st.last_rsi_alert_sec = now_s
                                                txt = f"🟢 RSI Oversold ({RSI_TF}) {sym}\nRSI={rsi:.1f} mid={mid:.6f}"
                                                asyncio.create_task(send_telegram(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, txt))
                                                if mysql:
                                                    mysql.insert_alert(sym, st.cur_sec, "LONG", 1.0, 0.0, 0.0, float(mid), float(spread), txt)
                                            elif rsi >= RSI_OB:
                                                st.last_rsi_alert_sec = now_s
                                                txt = f"🔴 RSI Overbought ({RSI_TF}) {sym}\nRSI={rsi:.1f} mid={mid:.6f}"
                                                asyncio.create_task(send_telegram(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, txt))
                                                if mysql:
                                                    mysql.insert_alert(sym, st.cur_sec, "SHORT", 1.0, 0.0, 0.0, float(mid), float(spread), txt)
                                        elif RSI_MODE == "cross50":
                                            if st.prev_rsi is not None and st.prev_rsi < 50 <= rsi:
                                                st.last_rsi_alert_sec = now_s
                                                txt = f"🟢 RSI Cross Up 50 ({RSI_TF}) {sym}\nRSI={rsi:.1f} mid={mid:.6f}"
                                                asyncio.create_task(send_telegram(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, txt))
                                            elif st.prev_rsi is not None and st.prev_rsi > 50 >= rsi:
                                                st.last_rsi_alert_sec = now_s
                                                txt = f"🔴 RSI Cross Down 50 ({RSI_TF}) {sym}\nRSI={rsi:.1f} mid={mid:.6f}"
                                                asyncio.create_task(send_telegram(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, txt)
                                                )
                                    st.prev_rsi = rsi

                                elif ALERT_MODE == "macd":
                                    hist = get_macd_hist(ctx, MACD_TF)
                                    if (now_s - st.last_macd_alert_sec) >= MACD_COOLDOWN_SEC:
                                        if MACD_MODE == "hist_cross0":
                                            # hist crosses 0
                                            if st.prev_macd_hist is not None and st.prev_macd_hist <= 0 < hist:
                                                st.last_macd_alert_sec = now_s
                                                txt = f"🟢 MACD Hist Cross Up 0 ({MACD_TF}) {sym}\nhist={hist:.6f} mid={mid:.6f}"
                                                asyncio.create_task(send_telegram(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, txt))
                                                if mysql:
                                                    mysql.insert_alert(sym, st.cur_sec, "LONG", 1.0, 0.0, 0.0, float(mid), float(spread), txt)
                                            elif st.prev_macd_hist is not None and st.prev_macd_hist >= 0 > hist:
                                                st.last_macd_alert_sec = now_s
                                                txt = f"🔴 MACD Hist Cross Down 0 ({MACD_TF}) {sym}\nhist={hist:.6f} mid={mid:.6f}"
                                                asyncio.create_task(send_telegram(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, txt))
                                                if mysql:
                                                    mysql.insert_alert(sym, st.cur_sec, "SHORT", 1.0, 0.0, 0.0, float(mid), float(spread), txt)
                                        st.prev_macd_hist = hist

                                else:
                                    # signal mode
                                    thr = max(FIXED_BPS, K_VOL * vol_120)
                                    can_alert = (now_s - st.last_alert_sec) >= COOLDOWN_SEC
                                    spread_ok = spread <= SPREAD_MAX

                                    if can_alert and spread_ok:
                                        if (p_up >= ALERT_P_UP) and (pred_ret >= thr) and ctx_filters_signal(ctx, "LONG"):
                                            st.last_alert_sec = now_s
                                            txt = (f"🟢 LONG bias {sym}\n"
                                                   f"mid={mid:.6f} spread={spread:.5f}\n"
                                                   f"pred_ret_120s={pred_ret:.5f} thr={thr:.5f}\n"
                                                   f"P(UP)={p_up:.2f} RSI5={ctx['rsi_5m']:.1f} MACD15m={ctx['macd_hist_15m']:.5f}")
                                            asyncio.create_task(send_telegram(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, txt))
                                            if mysql:
                                                mysql.insert_alert(sym, st.cur_sec, "LONG", float(p_up), float(pred_ret), float(thr), float(mid), float(spread), txt)

                                        elif (p_down >= ALERT_P_DOWN) and (pred_ret <= -thr) and ctx_filters_signal(ctx, "SHORT"):
                                            st.last_alert_sec = now_s
                                            txt = (f"🔴 SHORT bias {sym}\n"
                                                   f"mid={mid:.6f} spread={spread:.5f}\n"
                                                   f"pred_ret_120s={pred_ret:.5f} thr={thr:.5f}\n"
                                                   f"P(DOWN)={p_down:.2f} RSI5={ctx['rsi_5m']:.1f} MACD15m={ctx['macd_hist_15m']:.5f}")
                                            asyncio.create_task(send_telegram(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, txt))
                                            if mysql:
                                                mysql.insert_alert(sym, st.cur_sec, "SHORT", float(p_down), float(pred_ret), float(thr), float(mid), float(spread), txt)

                                # --- store bar ---
                                bar_batch.append({
                                    "symbol": sym, "sec": st.cur_sec,
                                    "open": st.o, "high": st.h, "low": st.l, "close": st.c,
                                    "mid": mid,
                                    "volume": st.volume,
                                    "buy_volume": st.buy_volume,
                                    "sell_volume": st.sell_volume,
                                    "trade_count": st.trade_count,
                                    "bid": st.bid, "ask": st.ask,
                                    "spread": (st.ask - st.bid) if (st.ask and st.bid) else None,
                                    "bid_qty": st.bid_qty, "ask_qty": st.ask_qty
                                })

                            st.cur_sec += 1
                            st.reset_bar()

                            if mysql and (time.time() - last_flush) >= 3.0:
                                try:
                                    mysql.insert_bars(bar_batch)
                                except Exception as e:
                                    print("MySQL insert error:", e)
                                bar_batch.clear()
                                last_flush = time.time()

                        # update current second accum
                        if st.o is None:
                            st.o = st.h = st.l = st.c = price
                        st.h = max(st.h, price)
                        st.l = min(st.l, price)
                        st.c = price
                        st.volume += qty
                        st.trade_count += 1
                        if is_buyer_maker:
                            st.sell_volume += qty
                        else:
                            st.buy_volume += qty

        except Exception:
            attempt += 1
            await asyncio.sleep(backoff_s(attempt))

async def run():
    symbols = await get_top_usdt_symbols(BINANCE_FUTURES_REST, TOP_N)
    print(f"Tracking {len(symbols)} symbols.")

    states: Dict[str, SymbolState] = {s: SymbolState() for s in symbols}

    mysql = None
    if MYSQL_ENABLED:
        mysql = MySQLWriter(MySQLConfig(
            host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER, password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE, bar_table=MYSQL_BAR_TABLE, alert_table=MYSQL_ALERT_TABLE
        ))

    url_book = build_stream_url(symbols, "bookTicker")
    url_trade = build_stream_url(symbols, "aggTrade")

    await send_telegram(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
                        f"✅ Bot started. Tracking {len(symbols)} symbols. MODE={ALERT_MODE}")

    await asyncio.gather(
        ws_bookticker(states, url_book),
        ws_aggtrade(states, url_trade, mysql),
    )

async def main():
    await run()

if __name__ == "__main__":
    asyncio.run(main())





