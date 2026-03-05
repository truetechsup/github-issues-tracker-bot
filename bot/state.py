"""Persistent state: timestamp of last poll (only notify about events after this)."""

import json
import os


def _ensure_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)


def load(path: str) -> str | None:
    """Load last_poll_at (ISO UTC). Returns None if first run."""
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("last_poll_at")
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def save(path: str, last_poll_at: str) -> None:
    """Persist last_poll_at (ISO UTC)."""
    _ensure_dir(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"last_poll_at": last_poll_at}, f)
