"""Format GitHub issue/comment text as HTML for Swarmica API."""

import html

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


def _issue_url(repo_full_name: str, issue: dict) -> str:
    number = issue.get("number")
    return issue.get("html_url") or f"https://github.com/{repo_full_name}/issues/{number}"


def format_issue_ticket_subject(issue: dict) -> str:
    return (issue.get("title") or "").strip() or "(no title)"


def _author_line(login: str) -> str:
    return f"<p>Автор: {html.escape(login)}</p>"


def format_issue_ticket_comment(
    repo_full_name: str,
    issue: dict,
    preview_len: int | None = None,
) -> str:
    preview_len = preview_len or BODY_PREVIEW_LENGTH
    author = ((issue.get("user") or {}).get("login") or "?").strip()
    body_raw = issue.get("body") or ""
    body = _truncate_pre(body_raw, preview_len)
    url = _issue_url(repo_full_name, issue)

    parts: list[str] = [_author_line(author)]
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
    author = ((comment.get("user") or {}).get("login") or "?").strip()
    body_raw = comment.get("body") or ""
    body = _truncate_pre(body_raw, preview_len)
    url = _issue_url(repo_full_name, issue)

    parts: list[str] = [_author_line(author)]
    if body:
        parts.append(_text_to_html(body))
    parts.append(f'<p><a href="{html.escape(url, quote=True)}">{html.escape(url)}</a></p>')
    return "\n".join(parts)
