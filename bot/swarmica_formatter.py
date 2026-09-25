"""Format GitHub issue/comment text as HTML for Swarmica API (full text, no truncation)."""

import html


def _normalize(text: str) -> str:
    return (text or "").replace("\r\n", "\n").strip()


def _text_to_html(text: str) -> str:
    escaped = html.escape(text)
    return f"<pre>{escaped}</pre>"


def _issue_url(repo_full_name: str, issue: dict) -> str:
    number = issue.get("number")
    return issue.get("html_url") or f"https://github.com/{repo_full_name}/issues/{number}"


def _comment_url(repo_full_name: str, issue: dict, comment: dict) -> str:
    url = comment.get("html_url")
    if url:
        return url
    cid = comment.get("id")
    base = _issue_url(repo_full_name, issue)
    return f"{base}#issuecomment-{cid}" if cid is not None else base


def _link(url: str) -> str:
    return f'<p><a href="{html.escape(url, quote=True)}">{html.escape(url)}</a></p>'


def format_issue_ticket_subject(issue: dict) -> str:
    return (issue.get("title") or "").strip() or "(no title)"


def _author_line(login: str) -> str:
    return f"<p>Автор: {html.escape(login)}</p>"


def format_issue_ticket_comment(repo_full_name: str, issue: dict) -> str:
    author = ((issue.get("user") or {}).get("login") or "?").strip()
    body = _normalize(issue.get("body") or "")

    parts: list[str] = [_author_line(author)]
    if body:
        parts.append(_text_to_html(body))
    parts.append(_link(_issue_url(repo_full_name, issue)))
    return "\n".join(parts)


def format_comment_body(repo_full_name: str, issue: dict, comment: dict) -> str:
    author = ((comment.get("user") or {}).get("login") or "?").strip()
    body = _normalize(comment.get("body") or "")

    parts: list[str] = [_author_line(author)]
    if body:
        parts.append(_text_to_html(body))
    parts.append(_link(_comment_url(repo_full_name, issue, comment)))
    return "\n".join(parts)
