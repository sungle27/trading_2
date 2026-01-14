import requests
from typing import Optional

class Telegram:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id

    def send(self, text: str) -> Optional[dict]:
        if not self.token or not self.chat_id:
            return None

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        return r.json()
