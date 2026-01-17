import time

from dotenv import load_dotenv

from config import Config
from utils import now_ts, utc_now_str
from telegram import TelegramNotifier
from binance_client import BinanceFuturesClient
from alert_engine import MarketData, evaluate_signal

def apply_profile_overrides(cfg: Config) -> None:
    """
    test: mục tiêu ra alert nhanh để test flow
    trade: dùng strict theo env
    """
    if cfg.ALERT_PROFILE.lower() == "test":
        cfg.ENABLE_REGIME = 0
        cfg.ENABLE_MACD = 0
        cfg.ENABLE_SPREAD = 1
        cfg.ENABLE_RSI = 1

        # nới RSI để pass dễ
        cfg.RSI_LONG_MIN, cfg.RSI_LONG_MAX = 20, 80
        cfg.RSI_SHORT_MIN, cfg.RSI_SHORT_MAX = 20, 80

        # nới spread để tránh bị chặn
        cfg.SPREAD_MAX = max(cfg.SPREAD_MAX, 0.0020)  # 0.2%

def main():
    load_dotenv()  # đọc .env

    cfg = Config()
    apply_profile_overrides(cfg)

    tg = TelegramNotifier(cfg.TELEGRAM_BOT_TOKEN, cfg.TELEGRAM_CHAT_ID)
    bx = BinanceFuturesClient(cfg.BINANCE_FUTURES_REST)

    # Startup ping (để biết chắc telegram OK)
    tg.send(
        f"✅ Bot started\n"
        f"Profile=<b>{cfg.ALERT_PROFILE}</b> Mode=<b>{cfg.ALERT_MODE}</b>\n"
        f"TopN={cfg.TOP_N} Loop={cfg.LOOP_SEC}s Cooldown={cfg.COOLDOWN_SEC}s\n"
        f"Filters spread/regime/rsi/macd="
        f"{cfg.ENABLE_SPREAD}/{cfg.ENABLE_REGIME}/{cfg.ENABLE_RSI}/{cfg.ENABLE_MACD}\n"
        f"Time={utc_now_str()}"
    )

    symbols = bx.top_symbols_by_quote_volume(cfg.TOP_N)

    last_heartbeat = 0
    last_sent = {}  # symbol -> ts

    while True:
        t = now_ts()
        scanned = 0
        passed = 0

        # refresh top symbols mỗi 10 phút cho sát volume (optional)
        if t % 600 < cfg.LOOP_SEC:
            try:
                symbols = bx.top_symbols_by_quote_volume(cfg.TOP_N)
            except Exception:
                pass

        for sym in symbols:
            scanned += 1

            # cooldown theo symbol
            prev = last_sent.get(sym, 0)
            if (t - prev) < cfg.COOLDOWN_SEC:
                continue

            try:
                bid, ask = bx.book_ticker(sym)
                closes = bx.klines_close(sym, interval="1m", limit=240)
                last_price = closes[-1] if closes else (bid + ask) / 2

                md = MarketData(symbol=sym, bid=bid, ask=ask, closes=closes, last_price=last_price)
                ok, reason = evaluate_signal(cfg, md)

                if ok:
                    passed += 1
                    last_sent[sym] = t
                    tg.send(
                        f"🚨 <b>ALERT</b> {sym}\n"
                        f"Price={last_price}\n"
                        f"{reason}\n"
                        f"Time={utc_now_str()}"
                    )

            except Exception as e:
                if cfg.DEBUG_ENABLED:
                    tg.send(f"⚠️ Error {sym}: {e}")

        # Heartbeat (để bạn biết bot đang chạy dù không có signal)
        if cfg.DEBUG_ENABLED and (t - last_heartbeat) >= cfg.HEARTBEAT_SEC:
            last_heartbeat = t
            tg.send(
                f"💓 Heartbeat\n"
                f"Scanned={scanned} Passed={passed} Symbols={len(symbols)}\n"
                f"Filters spread/regime/rsi/macd="
                f"{cfg.ENABLE_SPREAD}/{cfg.ENABLE_REGIME}/{cfg.ENABLE_RSI}/{cfg.ENABLE_MACD}\n"
                f"Time={utc_now_str()}"
            )

        time.sleep(cfg.LOOP_SEC)

if __name__ == "__main__":
    main()
