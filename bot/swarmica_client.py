"""Swarmica Helpdesk API: create tickets, add comments, update statuses."""

import logging
from typing import Any
from urllib.parse import urljoin

import requests

from bot.config import (
    SWARMICA_API_TOKEN,
    SWARMICA_API_URL,
    SWARMICA_ASSIGNEE_EMAIL,
    SWARMICA_REQUESTER_EMAIL,
    SWARMICA_STATUS_PENDING,
    SWARMICA_STATUS_SOLVED,
)
from bot.swarmica_formatter import (
    format_comment_body,
    format_issue_ticket_comment,
    format_issue_ticket_subject,
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


_assignee_lookup_done = False
_assignee_uid: str | None = None


def _lookup_user_uid_by_email(email: str) -> str | None:
    url = _api_url("/api/users/")
    try:
        resp = requests.get(
            url,
            headers=_headers(),
            params={"email": email, "limit": 1},
            timeout=30,
        )
    except requests.RequestException as e:
        log.warning("Swarmica: assignee lookup failed for %s: %s", email, e)
        return None
    if resp.status_code >= 400:
        log.warning(
            "Swarmica: assignee lookup for %s returned %s: %s",
            email,
            resp.status_code,
            (resp.text or "")[:400],
        )
        return None
    try:
        payload = resp.json()
    except ValueError:
        log.warning("Swarmica: assignee lookup for %s returned invalid JSON", email)
        return None
    results = payload.get("results") if isinstance(payload, dict) else None
    if not results:
        return None
    first = results[0]
    if not isinstance(first, dict):
        return None
    uid = first.get("uid")
    return uid if isinstance(uid, str) and uid.strip() else None


def get_assignee_uid() -> str | None:
    """Resolve SWARMICA_ASSIGNEE_EMAIL to Swarmica user uid (cached)."""
    global _assignee_lookup_done, _assignee_uid
    if not SWARMICA_ASSIGNEE_EMAIL:
        return None
    if not _assignee_lookup_done:
        _assignee_uid = _lookup_user_uid_by_email(SWARMICA_ASSIGNEE_EMAIL)
        _assignee_lookup_done = True
        if _assignee_uid:
            log.info(
                "Swarmica: assignee %s resolved to uid %s",
                SWARMICA_ASSIGNEE_EMAIL,
                _assignee_uid,
            )
        else:
            log.warning(
                "Swarmica: assignee email %s not found; tickets will use default assignment",
                SWARMICA_ASSIGNEE_EMAIL,
            )
    return _assignee_uid


def warm_assignee_cache() -> None:
    """Look up assignee uid at startup so misconfiguration shows up early in logs."""
    get_assignee_uid()


def create_ticket_from_issue(
    repo_full_name: str,
    issue: dict,
    *,
    idempotency_key: str,
) -> int:
    """Create a Swarmica ticket for a GitHub issue. Returns ticket id."""
    payload: dict[str, Any] = {
        "subject": format_issue_ticket_subject(issue),
        "comment": format_issue_ticket_comment(repo_full_name, issue),
        "is_external": True,
        "public": True,
        "idempotency_key": idempotency_key,
    }
    if SWARMICA_REQUESTER_EMAIL:
        payload["requester_email"] = SWARMICA_REQUESTER_EMAIL
        payload["requester_is_robot"] = True
    assignee_uid = get_assignee_uid()
    if assignee_uid:
        payload["assignee"] = assignee_uid
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
    status: str | None = None,
) -> None:
    """Add a comment; optionally set ticket status (OPEN, PENDING, etc.)."""
    if status:
        payload = {
            "comment": body_html,
            "status": status,
            "public": True,
            "idempotency_key": idempotency_key,
        }
        _request("PATCH", f"/api/tickets/{ticket_id}/", payload)
        log.info("Swarmica: comment + status %s on ticket %s", status, ticket_id)
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
    status: str,
) -> None:
    body_html = format_comment_body(repo_full_name, issue, comment)
    add_comment(
        ticket_id,
        body_html,
        idempotency_key=idempotency_key,
        status=status,
    )


def set_ticket_solved(ticket_id: int, *, idempotency_key: str) -> None:
    payload = {
        "status": SWARMICA_STATUS_SOLVED,
        "idempotency_key": idempotency_key,
    }
    _request("PATCH", f"/api/tickets/{ticket_id}/", payload)
    log.info("Swarmica: ticket %s set to %s", ticket_id, SWARMICA_STATUS_SOLVED)
