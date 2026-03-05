"""Send messages to Telegram chat."""

import logging

import requests

from bot.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

log = logging.getLogger(__name__)

API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def send_message(text: str, parse_mode: str = "HTML") -> bool:
    """Send text to configured chat. Returns True on success."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning(
            "Telegram: cannot send (TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set)"
        )
        return False
    url = API_URL.format(token=TELEGRAM_BOT_TOKEN)
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        log.warning("Telegram: send failed: %s", e)
        return False
