"""Persistent state: poll checkpoint, Telegram/Swarmica dedup, issue→ticket mapping."""

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


def _normalize_issue_tickets(raw: Any) -> dict[str, int]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, int] = {}
    for key, value in raw.items():
        if key is None:
            continue
        try:
            out[str(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return out


def _normalize_str_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if item is not None]


def issue_map_key(repo_full_name: str, issue_number: int) -> str:
    return f"{repo_full_name}#{issue_number}"


def load(path: str) -> dict[str, Any] | None:
    """
    Load state. Returns None if first run (no file).

    Keys:
      last_poll_at (str | None)
      sent_keys (list[str]) — Telegram dedup
      swarmica_sent_keys (list[str]) — Swarmica dedup
      issue_tickets (dict[str, int]) — GitHub issue key → Swarmica ticket id
      issue_closed_synced (list[str]) — issues already marked solved in Swarmica
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

    sent_keys = _normalize_str_list(data.get("sent_keys", []))
    swarmica_sent_keys = _normalize_str_list(data.get("swarmica_sent_keys", []))
    issue_closed_synced = _normalize_str_list(data.get("issue_closed_synced", []))
    issue_tickets = _normalize_issue_tickets(data.get("issue_tickets", {}))

    return {
        "last_poll_at": last_poll_at,
        "sent_keys": _trim_keys(sent_keys),
        "swarmica_sent_keys": _trim_keys(swarmica_sent_keys),
        "issue_tickets": issue_tickets,
        "issue_closed_synced": _trim_keys(issue_closed_synced),
    }


def save(
    path: str,
    last_poll_at: str,
    sent_keys: list[str],
    *,
    swarmica_sent_keys: list[str] | None = None,
    issue_tickets: dict[str, int] | None = None,
    issue_closed_synced: list[str] | None = None,
) -> None:
    """Persist poll checkpoint and delivery/mapping state."""
    _ensure_dir(path)
    payload: dict[str, Any] = {
        "last_poll_at": last_poll_at,
        "sent_keys": _trim_keys(sent_keys),
    }
    if swarmica_sent_keys is not None:
        payload["swarmica_sent_keys"] = _trim_keys(swarmica_sent_keys)
    if issue_tickets is not None:
        payload["issue_tickets"] = issue_tickets
    if issue_closed_synced is not None:
        payload["issue_closed_synced"] = _trim_keys(issue_closed_synced)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=0)


def maybe_trim_sent_keys_in_place(keys: list[str]) -> None:
    """Drop oldest keys when the list exceeds SENT_KEYS_MAX (keeps newest tail)."""
    if len(keys) <= SENT_KEYS_MAX:
        return
    keep = max(SENT_KEYS_MAX * 4 // 5, SENT_KEYS_MAX - 2000)
    keys[:] = keys[-keep:]
