from __future__ import annotations

import asyncio
import aiohttp
import logging

from .config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DEBUG_ENABLED

# Giảm log spam từ aiohttp
logging.getLogger("aiohttp.client").setLevel(logging.WARNING)

TELEGRAM_API = "https://api.telegram.org"


async def send_telegram(
    bot_token: str | None,
    chat_id: str | int | None,
    text: str,
    *,
    parse_mode: str | None = None,
    disable_web_page_preview: bool = True,
    timeout: int = 10,
    retries: int = 2,
):
    """
    Gửi message Telegram an toàn:
    - Không raise exception ra ngoài
    - Retry nhẹ nếu network lỗi
    - Không block event loop
    """

    if not bot_token or not chat_id:
        if DEBUG_ENABLED:
            print("⚠️ Telegram not configured (token/chat_id missing)")
        return

    url = f"{TELEGRAM_API}/bot{bot_token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": disable_web_page_preview,
    }

    if parse_mode:
        payload["parse_mode"] = parse_mode

    for attempt in range(retries + 1):
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        if DEBUG_ENABLED:
                            print("📨 Telegram sent:", text[:80])
                        return
                    else:
                        # đọc body để đóng response đúng cách
                        body = await resp.text()
                        if DEBUG_ENABLED:
                            print(
                                f"❌ Telegram HTTP {resp.status}: {body[:120]}"
                            )
        except asyncio.CancelledError:
            # Task bị cancel → thoát luôn
            return
        except Exception as e:
            if DEBUG_ENABLED:
                print(f"❌ Telegram error (attempt {attempt}):", e)

            if attempt < retries:
                await asyncio.sleep(1.5 * (attempt + 1))
            else:
                return


# ============================================================
# Convenience wrapper (dùng config mặc định)
# ============================================================
async def notify(text: str, **kwargs):
    """
    Wrapper tiện dụng:
    notify("hello")
    """
    await send_telegram(
        TELEGRAM_BOT_TOKEN,
        TELEGRAM_CHAT_ID,
        text,
        **kwargs,
    )
