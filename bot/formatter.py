"""Format notification text (Telegram HTML) and escape content."""

import re

from bot.config import BODY_PREVIEW_LENGTH


def _truncate_plain(text: str, max_len: int) -> str:
    if not text or not text.strip():
        return ""
    text = text.strip().replace("\r\n", "\n").replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _truncate_pre(text: str, max_len: int) -> str:
    """Preserve newlines; trim by character count."""
    if not text or not text.strip():
        return ""
    text = text.strip().replace("\r\n", "\n")
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _escape_tg_html(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _issue_state_ru(issue: dict) -> str:
    s = (issue.get("state") or "").strip().lower()
    if s == "open":
        return "Проблема актуальна"
    if s == "closed":
        return "Проблема решена"
    return _escape_tg_html(s or "неизвестно")


def format_issue(repo_full_name: str, issue: dict, preview_len: int | None = None) -> str:
    """One notification block for a new issue (HTML parse mode)."""
    preview_len = preview_len or BODY_PREVIEW_LENGTH
    title = _escape_tg_html((issue.get("title") or "").strip() or "(no title)")
    body_raw = issue.get("body") or ""
    body = _truncate_pre(body_raw, preview_len)
    url = issue.get("html_url") or f"https://github.com/{repo_full_name}/issues/{issue.get('number')}"
    state_line = _issue_state_ru(issue)

    lines: list[str] = [
        "<b>Новая проблема</b>",
        f"<b>Репозиторий</b>: {_escape_tg_html(repo_full_name)}",
        f"<b>Статус issue</b>: {state_line}",
        f"<b>Заголовок</b>: {title}",
        "",
    ]
    if body:
        lines.append(f"<pre>{_escape_tg_html(body)}</pre>")
        lines.append("")
    lines.append(_escape_tg_html(url))
    return "\n".join(lines).strip()


def format_comment(repo_full_name: str, issue: dict, comment: dict, preview_len: int | None = None) -> str:
    """One notification block for a new comment (HTML parse mode)."""
    preview_len = preview_len or BODY_PREVIEW_LENGTH
    issue_title = _escape_tg_html((issue.get("title") or "").strip() or "(no title)")
    body_raw = comment.get("body") or ""
    body = _truncate_pre(body_raw, preview_len)
    url = comment.get("html_url") or issue.get("html_url") or f"https://github.com/{repo_full_name}/issues/{issue.get('number')}"
    user = _escape_tg_html((comment.get("user") or {}).get("login") or "?")
    state_line = _issue_state_ru(issue)

    lines: list[str] = [
        "<b>Новый комментарий</b>",
        f"<b>Репозиторий</b>: {_escape_tg_html(repo_full_name)}",
        f"<b>Статус issue</b>: {state_line}",
        f"<b>Issue</b>: {issue_title}",
        f"<b>Автор</b>: {user}",
        "",
    ]
    if body:
        lines.append(f"<pre>{_escape_tg_html(body)}</pre>")
        lines.append("")
    lines.append(_escape_tg_html(url))
    return "\n".join(lines).strip()
