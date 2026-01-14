import time
from datetime import datetime, timezone

from config import Config
from telegram import Telegram
from binance_api import get_top_symbols_by_quote_volume, get_book_ticker, get_klines
from filters import MarketSnapshot, evaluate

def now_ts() -> int:
    return int(time.time())

def fmt_time() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def build_profile_overrides(cfg: Config):
    """
    TEST profile: force alerts fast.
    TRADE profile: keep strict.
    """
    if cfg.alert_profile.lower() == "test":
        cfg.enable_regime = 0
        cfg.enable_macd = 0
        cfg.enable_spread = 1
        cfg.enable_rsi = 1
        cfg.spread_max = max(cfg.spread_max, 0.0020)  # 0.2%
        cfg.rsi_long_min, cfg.rsi_long_max = 20, 80
        cfg.rsi_short_min, cfg.rsi_short_max = 20, 80

def main():
    cfg = Config()
    build_profile_overrides(cfg)

    tg = Telegram(cfg.tg_token, cfg.tg_chat_id)

    # startup ping
    tg.send(
        f"✅ Bot started\n"
        f"Profile: <b>{cfg.alert_profile}</b> | Mode: <b>{cfg.alert_mode}</b>\n"
        f"TopN={cfg.top_n} Loop={cfg.loop_sec}s HB={cfg.heartbeat_sec}s\n"
        f"Filters: spread={cfg.enable_spread} regime={cfg.enable_regime} rsi={cfg.enable_rsi} macd={cfg.enable_macd}\n"
        f"Time: {fmt_time()}"
    )

    symbols = get_top_symbols_by_quote_volume(cfg.binance_rest, cfg.top_n)

    last_heartbeat = 0
    last_sent_by_symbol = {}  # symbol -> ts

    while True:
        t0 = now_ts()
        passed = 0
        scanned = 0

        for sym in symbols:
            scanned += 1
            # cooldown per symbol
            last_sent = last_sent_by_symbol.get(sym, 0)
            if (t0 - last_sent) < cfg.cooldown_sec:
                continue

            try:
                bid, ask = get_book_ticker(cfg.binance_rest, sym)
                closes = get_klines(cfg.binance_rest, sym, interval="1m", limit=220)
                last_price = closes[-1] if closes else (bid + ask) / 2

                snap = MarketSnapshot(symbol=sym, bid=bid, ask=ask, closes=closes, last_price=last_price)
                ok, reason = evaluate(cfg, snap)

                if ok:
                    passed += 1
                    last_sent_by_symbol[sym] = t0
                    tg.send(
                        f"🚨 <b>ALERT</b> {sym}\n"
                        f"Price: {last_price}\n"
                        f"{reason}\n"
                        f"Time: {fmt_time()}"
                    )

            except Exception as e:
                if cfg.debug_enabled:
                    tg.send(f"⚠️ Error {sym}: {e}")

        # heartbeat
        if cfg.debug_enabled and (t0 - last_heartbeat) >= cfg.heartbeat_sec:
            last_heartbeat = t0
            tg.send(
                f"💓 Heartbeat\n"
                f"Scanned={scanned} Passed={passed}\n"
                f"Profile={cfg.alert_profile} Filters(spread/regime/rsi/macd)="
                f"{cfg.enable_spread}/{cfg.enable_regime}/{cfg.enable_rsi}/{cfg.enable_macd}\n"
                f"Time: {fmt_time()}"
            )

        time.sleep(cfg.loop_sec)

if __name__ == "__main__":
    main()
