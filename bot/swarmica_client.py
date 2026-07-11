"""Swarmica Helpdesk API: create tickets, add comments, update statuses."""

import logging
from typing import Any
from urllib.parse import urljoin

import requests

from bot.config import (
    SWARMICA_API_TOKEN,
    SWARMICA_API_URL,
    SWARMICA_STATUS_PENDING,
    SWARMICA_STATUS_SOLVED,
)
from bot.swarmica_formatter import (
    format_comment_body,
    format_issue_ticket_comment,
    format_issue_ticket_subject,
    github_requester_email,
)

log = logging.getLogger(__name__)


class SwarmicaError(Exception):
    """Swarmica API request failed."""


def is_enabled() -> bool:
    return bool(SWARMICA_API_URL and SWARMICA_API_TOKEN)


def _headers() -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Token {SWARMICA_API_TOKEN}",
    }


def _api_url(path: str) -> str:
    base = SWARMICA_API_URL.rstrip("/") + "/"
    return urljoin(base, path.lstrip("/"))


def _request(method: str, path: str, json_body: dict | None = None) -> dict | list | None:
    url = _api_url(path)
    try:
        resp = requests.request(
            method,
            url,
            headers=_headers(),
            json=json_body,
            timeout=30,
        )
    except requests.RequestException as e:
        log.warning("Swarmica: request failed %s %s: %s", method, path, e)
        raise SwarmicaError(str(e)) from e

    if resp.status_code >= 400:
        detail = (resp.text or "")[:800]
        log.warning(
            "Swarmica: %s %s returned %s: %s",
            method,
            path,
            resp.status_code,
            detail or "(empty)",
        )
        raise SwarmicaError(f"HTTP {resp.status_code}")

    if resp.status_code == 204 or not resp.content:
        return None
    try:
        return resp.json()
    except ValueError as e:
        log.warning("Swarmica: invalid JSON from %s %s", method, path)
        raise SwarmicaError("invalid JSON response") from e


def _ticket_id_from_response(data: Any) -> int | None:
    if isinstance(data, dict):
        raw = data.get("id")
        if isinstance(raw, int):
            return raw
        if isinstance(raw, str) and raw.isdigit():
            return int(raw)
    return None


def create_ticket_from_issue(
    repo_full_name: str,
    issue: dict,
    *,
    idempotency_key: str,
) -> int:
    """Create a Swarmica ticket for a GitHub issue. Returns ticket id."""
    author_login = ((issue.get("user") or {}).get("login") or "unknown").strip()
    payload: dict[str, Any] = {
        "subject": format_issue_ticket_subject(repo_full_name, issue),
        "comment": format_issue_ticket_comment(repo_full_name, issue),
        "requester_email": github_requester_email(author_login),
        "requester_is_robot": True,
        "comment_from_requester": True,
        "is_external": True,
        "public": True,
        "idempotency_key": idempotency_key,
    }
    data = _request("POST", "/api/tickets/", payload)
    ticket_id = _ticket_id_from_response(data)
    if ticket_id is None:
        raise SwarmicaError("create ticket: response without id")
    log.info("Swarmica: created ticket %s for %s #%s", ticket_id, repo_full_name, issue.get("number"))
    return ticket_id


def add_comment(
    ticket_id: int,
    body_html: str,
    *,
    idempotency_key: str,
    set_pending: bool = False,
) -> None:
    """Add a comment; optionally move ticket to pending (waiting for client)."""
    if set_pending:
        payload = {
            "comment": body_html,
            "status": SWARMICA_STATUS_PENDING,
            "public": True,
            "idempotency_key": idempotency_key,
        }
        _request("PATCH", f"/api/tickets/{ticket_id}/", payload)
        log.info("Swarmica: comment + status %s on ticket %s", SWARMICA_STATUS_PENDING, ticket_id)
        return

    payload = {
        "body": body_html,
        "public": True,
        "idempotency_key": idempotency_key,
    }
    _request("POST", f"/api/tickets/{ticket_id}/comments/", payload)
    log.info("Swarmica: comment added to ticket %s", ticket_id)


def add_issue_comment(
    ticket_id: int,
    repo_full_name: str,
    issue: dict,
    comment: dict,
    *,
    idempotency_key: str,
    set_pending: bool = False,
) -> None:
    body_html = format_comment_body(repo_full_name, issue, comment)
    add_comment(
        ticket_id,
        body_html,
        idempotency_key=idempotency_key,
        set_pending=set_pending,
    )


def set_ticket_solved(ticket_id: int, *, idempotency_key: str) -> None:
    payload = {
        "status": SWARMICA_STATUS_SOLVED,
        "idempotency_key": idempotency_key,
    }
    _request("PATCH", f"/api/tickets/{ticket_id}/", payload)
    log.info("Swarmica: ticket %s set to %s", ticket_id, SWARMICA_STATUS_SOLVED)
