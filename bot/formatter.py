"""Format notification text and escape Telegram / GitHub content."""

import re

from bot.config import BODY_PREVIEW_LENGTH


def _truncate(text: str, max_len: int) -> str:
    if not text or not text.strip():
        return ""
    text = text.strip().replace("\r\n", "\n").replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _escape_tg(s: str) -> str:
    """Escape for Telegram (MarkdownV2 would need more; plain is safer)."""
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_issue(repo_full_name: str, issue: dict, preview_len: int | None = None) -> str:
    """One notification block for a new issue."""
    preview_len = preview_len or BODY_PREVIEW_LENGTH
    title = _escape_tg((issue.get("title") or "").strip() or "(no title)")
    body = _truncate(issue.get("body") or "", preview_len)
    if body:
        body = _escape_tg(body) + "\n"
    url = issue.get("html_url") or f"https://github.com/{repo_full_name}/issues/{issue.get('number')}"
    lines = [
        "🆕 New issue",
        f"Repo: {_escape_tg(repo_full_name)}",
        f"Title: {title}",
        "",
        body,
        url,
    ]
    return "\n".join(filter(None, lines)).strip()


def format_comment(repo_full_name: str, issue: dict, comment: dict, preview_len: int | None = None) -> str:
    """One notification block for a new comment on an issue."""
    preview_len = preview_len or BODY_PREVIEW_LENGTH
    issue_title = _escape_tg((issue.get("title") or "").strip() or "(no title)")
    body = _truncate(comment.get("body") or "", preview_len)
    if body:
        body = _escape_tg(body) + "\n"
    url = comment.get("html_url") or issue.get("html_url") or f"https://github.com/{repo_full_name}/issues/{issue.get('number')}"
    user = _escape_tg((comment.get("user") or {}).get("login") or "?")
    lines = [
        "💬 New comment",
        f"Repo: {_escape_tg(repo_full_name)}",
        f"Issue: {issue_title}",
        f"By: {user}",
        "",
        body,
        url,
    ]
    return "\n".join(filter(None, lines)).strip()
