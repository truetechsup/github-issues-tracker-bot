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


def _get(url: str, params: dict | None = None) -> list | dict:
    log.debug("GitHub GET %s %s", url, params or {})
    resp = requests.get(url, headers=HEADERS, params=params or {}, timeout=30)
    resp.raise_for_status()
    return resp.json()


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
