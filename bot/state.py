"""Persistent state: last poll time and keys of successfully sent notifications."""

import json
import os
from typing import Any

from bot.config import SENT_KEYS_MAX


def _ensure_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)


def _trim_keys(keys: list[str]) -> list[str]:
    if len(keys) <= SENT_KEYS_MAX:
        return keys
    keep = max(SENT_KEYS_MAX * 4 // 5, SENT_KEYS_MAX - 2000)
    return keys[-keep:]


def load(path: str) -> dict[str, Any] | None:
    """
    Load state. Returns None if first run (no file).

    Keys: last_poll_at (str | None), sent_keys (list[str]).
    """
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, TypeError):
        return None
    last_poll_at = data.get("last_poll_at")
    if last_poll_at is not None and not isinstance(last_poll_at, str):
        last_poll_at = None
    raw_keys = data.get("sent_keys", [])
    if isinstance(raw_keys, list):
        sent_keys = [str(k) for k in raw_keys if k is not None]
    else:
        sent_keys = []
    return {"last_poll_at": last_poll_at, "sent_keys": _trim_keys(sent_keys)}


def save(path: str, last_poll_at: str, sent_keys: list[str]) -> None:
    """Persist last_poll_at and successfully delivered notification keys."""
    _ensure_dir(path)
    keys = _trim_keys(sent_keys)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"last_poll_at": last_poll_at, "sent_keys": keys}, f, indent=0)


def maybe_trim_sent_keys_in_place(keys: list[str]) -> None:
    """Drop oldest keys when the list exceeds SENT_KEYS_MAX (keeps newest tail)."""
    if len(keys) <= SENT_KEYS_MAX:
        return
    keep = max(SENT_KEYS_MAX * 4 // 5, SENT_KEYS_MAX - 2000)
    keys[:] = keys[-keep:]
