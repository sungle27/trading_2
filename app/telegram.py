import aiohttp

async def send_telegram(token: str, chat_id: str, text: str) -> None:
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    
    async with aiohttp.ClientSession() as s:
        try:
            await s.post(url, json=payload, timeout=10)
        except Exception:
            pass
