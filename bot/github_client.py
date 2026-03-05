"""GitHub API client: repos, issues, comments (for orgs and users)."""

import logging
import time
from datetime import datetime, timezone
from typing import Iterator

import requests

from bot.config import GITHUB_TOKEN

log = logging.getLogger(__name__)

API_BASE = "https://api.github.com"

BASE_HEADERS = {
    "Accept": "application/vnd.github.v3+json",
}

if GITHUB_TOKEN:
    HEADERS = {**BASE_HEADERS, "Authorization": f"token {GITHUB_TOKEN}"}
else:
    HEADERS = BASE_HEADERS


class RateLimitExceeded(Exception):
    """GitHub API rate limit hit; reset_at is Unix timestamp when limit resets."""

    def __init__(self, reset_at: int):
        self.reset_at = reset_at
        super().__init__(reset_at)


def _get(url: str, params: dict | None = None, _retried: bool = False) -> list | dict:
    log.debug("GitHub GET %s %s", url, params or {})
    resp = requests.get(url, headers=HEADERS, params=params or {}, timeout=30)
    if resp.status_code == 403 and _is_rate_limited(resp):
        if not _retried:
            _wait_for_rate_limit_reset(resp)
            return _get(url, params, _retried=True)
        reset_at = _parse_reset_time(resp)
        hint = "Add GITHUB_TOKEN for 5000 req/h. " if not GITHUB_TOKEN else ""
        log.warning(
            "GitHub rate limit exceeded (%s). %sResets at %s UTC.",
            "60 req/h without token" if not GITHUB_TOKEN else "5000 req/h with token",
            hint,
            _format_reset(reset_at),
        )
        raise RateLimitExceeded(reset_at)
    resp.raise_for_status()
    return resp.json()


def _parse_reset_time(resp: requests.Response) -> int:
    raw = resp.headers.get("X-RateLimit-Reset")
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    return int(time.time()) + 3600


def _format_reset(ts: int) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _is_rate_limited(resp: requests.Response) -> bool:
    try:
        data = resp.json()
        return "rate limit" in (data.get("message") or "").lower()
    except Exception:
        return "rate limit" in (resp.text or "").lower()


def _wait_for_rate_limit_reset(resp: requests.Response) -> None:
    """Sleep until GitHub rate limit resets, then return."""
    reset_ts = resp.headers.get("X-RateLimit-Reset")
    if not reset_ts:
        reset_ts = str(int(time.time()) + 3600)
    try:
        reset_at = int(reset_ts)
    except ValueError:
        reset_at = int(time.time()) + 3600
    wait_sec = max(0, reset_at - int(time.time()))
    if wait_sec <= 0:
        return
    hint = " Add GITHUB_TOKEN for 5000 req/h." if not GITHUB_TOKEN else ""
    log.warning(
        "GitHub rate limit exceeded. Waiting %d s until reset.%s",
        wait_sec,
        hint,
    )
    time.sleep(wait_sec)


def check_owner_exists(owner: str) -> bool:
    """Check that the GitHub user or organization exists. Returns True if found."""
    url = f"{API_BASE}/users/{owner}"
    try:
        _get(url)
        return True
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            log.warning("GitHub owner not found: %s", owner)
            return False
        raise


def _get_paged(url: str, params: dict | None = None) -> Iterator[dict]:
    params = dict(params or {})
    params.setdefault("per_page", 100)
    page = 1
    while True:
        params["page"] = page
        data = _get(url, params)
        if not data:
            break
        yield from (data if isinstance(data, list) else [data])
        if not isinstance(data, list) or len(data) < params["per_page"]:
            break
        page += 1
        time.sleep(0.1)


def get_owner_repos(owner: str) -> Iterator[dict]:
    """
    Yield repo dicts (full_name, name, owner) for a GitHub owner.

    Works for both organizations and user profiles.
    """
    log.info("GitHub: fetching repositories for %s", owner)
    info_url = f"{API_BASE}/users/{owner}"
    info = _get(info_url)
    owner_type = info.get("type", "User")
    if owner_type == "Organization":
        url = f"{API_BASE}/orgs/{owner}/repos"
    else:
        url = f"{API_BASE}/users/{owner}/repos"
    repos = list(_get_paged(url))
    log.info("GitHub: found %d repo(s) for %s", len(repos), owner)
    yield from repos


def get_repo_issues(owner: str, repo: str, since: datetime) -> Iterator[dict]:
    """Yield issue dicts; exclude pull requests. Only issues updated since given time."""
    since_iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")
    log.debug("GitHub: fetching issues for %s/%s since %s", owner, repo, since_iso)
    url = f"{API_BASE}/repos/{owner}/{repo}/issues"
    for item in _get_paged(url, {"state": "all", "sort": "updated", "since": since_iso}):
        if "pull_request" in item:
            continue
        yield item


def get_issue_comments(owner: str, repo: str, issue_number: int) -> Iterator[dict]:
    """Yield comment dicts for an issue."""
    url = f"{API_BASE}/repos/{owner}/{repo}/issues/{issue_number}/comments"
    yield from _get_paged(url)


def utc_now_iso() -> str:
    """Current time in ISO format (UTC)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
