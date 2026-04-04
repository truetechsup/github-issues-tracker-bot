"""Configuration from environment variables."""

import os
import re

# GitHub owner name: letters, numbers, hyphens; 1–39 chars (GitHub rules)
GITHUB_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?$")


def _int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


MIN_POLL_INTERVAL_SECONDS = 60

GITHUB_NAME = (os.environ.get("GITHUB_NAME") or os.environ.get("GITHUB_ORG") or "").strip()
GITHUB_TOKEN = (os.environ.get("GITHUB_TOKEN") or "").strip()
TELEGRAM_BOT_TOKEN = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
TELEGRAM_CHAT_ID = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()

_raw_interval = _int("POLL_INTERVAL_SECONDS", 300)
if _raw_interval < MIN_POLL_INTERVAL_SECONDS:
    POLL_INTERVAL_SECONDS = MIN_POLL_INTERVAL_SECONDS
    POLL_INTERVAL_CLAMPED = True
else:
    POLL_INTERVAL_SECONDS = _raw_interval
    POLL_INTERVAL_CLAMPED = False

STATE_PATH = (os.environ.get("STATE_PATH") or "/data/state.json").strip()
BODY_PREVIEW_LENGTH = _int("BODY_PREVIEW_LENGTH", 300)

# Comma-separated GitHub logins: comments from these users are not sent to Telegram.
def _parse_ignore_comment_authors(raw: str | None) -> frozenset[str]:
    if not raw or not raw.strip():
        return frozenset()
    parts = [p.strip().lower() for p in raw.split(",")]
    return frozenset(p for p in parts if p)


IGNORE_COMMENT_AUTHORS = _parse_ignore_comment_authors(
    os.environ.get("IGNORE_COMMENT_AUTHORS")
)

# Cap stored dedup keys so state file does not grow without bound.
SENT_KEYS_MAX = _int("SENT_KEYS_MAX", 10000)

# Log level: DEBUG, INFO, WARNING, ERROR (case-insensitive)
_LOG_LEVEL_NAMES = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}
_raw_log_level = (os.environ.get("LOG_LEVEL") or "INFO").strip().upper()
LOG_LEVEL = _LOG_LEVEL_NAMES.get(_raw_log_level, 20)


def validate_config() -> list[str]:
    """
    Validate required env and formats. Returns list of error messages (empty if OK).
    """
    errors: list[str] = []

    if not GITHUB_NAME:
        errors.append("GITHUB_NAME is empty. Set it to a GitHub organization or username.")
    elif not GITHUB_NAME_PATTERN.fullmatch(GITHUB_NAME) or len(GITHUB_NAME) > 39:
        errors.append(
            f"GITHUB_NAME '{GITHUB_NAME}' is invalid. "
            "Use only letters, numbers, hyphens; 1–39 characters."
        )

    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN is empty. Create a bot via @BotFather and set the token.")

    if not TELEGRAM_CHAT_ID:
        errors.append("TELEGRAM_CHAT_ID is empty. Add the bot to a chat and set the chat ID.")

    if BODY_PREVIEW_LENGTH < 0:
        errors.append("BODY_PREVIEW_LENGTH must be >= 0.")

    if SENT_KEYS_MAX < 100:
        errors.append("SENT_KEYS_MAX must be >= 100.")

    return errors
