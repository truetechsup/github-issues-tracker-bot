"""Format GitHub issue/comment text as HTML for Swarmica API."""

import html
import re

from bot.config import BODY_PREVIEW_LENGTH


def _truncate_pre(text: str, max_len: int) -> str:
    if not text or not text.strip():
        return ""
    text = text.strip().replace("\r\n", "\n")
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _text_to_html(text: str) -> str:
    escaped = html.escape(text)
    return f"<pre>{escaped}</pre>"


def _issue_state_label(issue: dict) -> str:
    state = (issue.get("state") or "").strip().lower()
    if state == "open":
        return "Открыта"
    if state == "closed":
        return "Закрыта"
    return state or "неизвестно"


def format_issue_ticket_subject(repo_full_name: str, issue: dict) -> str:
    number = issue.get("number")
    title = (issue.get("title") or "").strip() or "(no title)"
    return f"[{repo_full_name}#{number}] {title}"


def format_issue_ticket_comment(
    repo_full_name: str,
    issue: dict,
    preview_len: int | None = None,
) -> str:
    preview_len = preview_len or BODY_PREVIEW_LENGTH
    number = issue.get("number")
    title = (issue.get("title") or "").strip() or "(no title)"
    body_raw = issue.get("body") or ""
    body = _truncate_pre(body_raw, preview_len)
    url = issue.get("html_url") or f"https://github.com/{repo_full_name}/issues/{number}"
    author = ((issue.get("user") or {}).get("login") or "?").strip()
    state_label = _issue_state_label(issue)

    parts = [
        "<p><b>Новая проблема на GitHub</b></p>",
        f"<p><b>Репозиторий</b>: {html.escape(repo_full_name)}</p>",
        f"<p><b>Issue</b>: #{number} — {html.escape(title)}</p>",
        f"<p><b>Автор</b>: {html.escape(author)}</p>",
        f"<p><b>Статус issue</b>: {html.escape(state_label)}</p>",
    ]
    if body:
        parts.append(_text_to_html(body))
    parts.append(f'<p><a href="{html.escape(url, quote=True)}">{html.escape(url)}</a></p>')
    return "\n".join(parts)


def format_comment_body(
    repo_full_name: str,
    issue: dict,
    comment: dict,
    preview_len: int | None = None,
) -> str:
    preview_len = preview_len or BODY_PREVIEW_LENGTH
    number = issue.get("number")
    title = (issue.get("title") or "").strip() or "(no title)"
    body_raw = comment.get("body") or ""
    body = _truncate_pre(body_raw, preview_len)
    url = (
        comment.get("html_url")
        or issue.get("html_url")
        or f"https://github.com/{repo_full_name}/issues/{number}"
    )
    author = ((comment.get("user") or {}).get("login") or "?").strip()
    state_label = _issue_state_label(issue)

    parts = [
        "<p><b>Новый комментарий на GitHub</b></p>",
        f"<p><b>Репозиторий</b>: {html.escape(repo_full_name)}</p>",
        f"<p><b>Issue</b>: #{number} — {html.escape(title)}</p>",
        f"<p><b>Автор</b>: {html.escape(author)}</p>",
        f"<p><b>Статус issue</b>: {html.escape(state_label)}</p>",
    ]
    if body:
        parts.append(_text_to_html(body))
    parts.append(f'<p><a href="{html.escape(url, quote=True)}">{html.escape(url)}</a></p>')
    return "\n".join(parts)


def github_requester_email(login: str) -> str:
    login = re.sub(r"[^a-zA-Z0-9._+-]", "", (login or "unknown").strip()) or "unknown"
    return f"{login}@github-issues.local"
