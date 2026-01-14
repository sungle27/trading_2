from __future__ import annotations
import asyncio
import aiohttp
import logging

# Giảm log spam của aiohttp
logging.getLogger("aiohttp.client").setLevel(logging.WARNING)

TELEGRAM_API = "https://api.telegram.org"


async def send_telegram(
    bot_token: str,
    chat_id: str | int,
    text: str,
    *,
    parse_mode: str | None = None,
    disable_web_page_preview: bool = True,
    timeout: int = 10,
    retries: int = 2,
):
    """
    Gửi message Telegram một cách an toàn:
    - Không raise exception ra ngoài
    - Retry nhẹ nếu network lỗi
    """

    if not bot_token or not chat_id:
        # Tránh crash nếu quên set env
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
                    # Telegram trả JSON ngay cả khi lỗi
                    if resp.status == 200:
                        return
                    else:
                        # đọc body cho đầy đủ vòng đời request
                        await resp.text()
        except asyncio.CancelledError:
            # task bị cancel thì thoát luôn
            return
        except Exception:
            # lỗi network / DNS / timeout → retry
            if attempt < retries:
                await asyncio.sleep(1.5 * (attempt + 1))
            else:
                return
