"""Telegram-only configuration from environment variables."""

import os

from bot.config import _int

TELEGRAM_BOT_TOKEN = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
TELEGRAM_CHAT_ID = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
# How many characters of issue/comment text to show in a notification.
BODY_PREVIEW_LENGTH = _int("BODY_PREVIEW_LENGTH", 300)


def validate_config() -> list[str]:
    """Validate Telegram env. Returns list of error messages (empty if OK)."""
    errors: list[str] = []
    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN is empty. Create a bot via @BotFather and set the token.")
    if not TELEGRAM_CHAT_ID:
        errors.append("TELEGRAM_CHAT_ID is empty. Add the bot to a chat and set the chat ID.")
    if BODY_PREVIEW_LENGTH < 0:
        errors.append("BODY_PREVIEW_LENGTH must be >= 0.")
    return errors
