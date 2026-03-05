"""Main loop: poll GitHub since last run, send only new issues/comments to Telegram."""

import logging
import sys
import time
from datetime import datetime, timezone

from bot.config import (
    GITHUB_NAME,
    LOG_LEVEL,
    POLL_INTERVAL_CLAMPED,
    POLL_INTERVAL_SECONDS,
    STATE_PATH,
    validate_config,
)
from bot.formatter import format_comment, format_issue
from bot.github_client import (
    check_owner_exists,
    get_issue_comments,
    get_owner_repos,
    get_repo_issues,
    RateLimitExceeded,
    utc_now_iso,
)
from bot.state import load, save
from bot.telegram_client import send_message

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)


def run_once(last_poll_at: str) -> str:
    """Fetch issues updated since last_poll_at; send only created after it. Return new timestamp."""
    since_dt = datetime.fromisoformat(last_poll_at.replace("Z", "+00:00"))
    total_issues_sent = 0
    total_comments_sent = 0
    repos_checked = 0

    log.info("Polling GitHub since %s (owner=%s)", last_poll_at, GITHUB_NAME)

    for repo in get_owner_repos(GITHUB_NAME):
        full_name = repo["full_name"]
        owner = repo["owner"]["login"]
        name = repo["name"]
        repos_checked += 1
        issues_sent = 0
        comments_sent = 0

        try:
            log.debug("Checking repo: %s", full_name)
            for issue in get_repo_issues(owner, name, since_dt):
                if (issue.get("created_at") or "") >= last_poll_at:
                    text = format_issue(full_name, issue)
                    if send_message(text):
                        issues_sent += 1
                        log.info("Sent issue %s #%s", full_name, issue["number"])
                for comment in get_issue_comments(owner, name, issue["number"]):
                    if (comment.get("created_at") or "") >= last_poll_at:
                        text = format_comment(full_name, issue, comment)
                        if send_message(text):
                            comments_sent += 1
                            log.info("Sent comment %s #%s", full_name, issue["number"])

            total_issues_sent += issues_sent
            total_comments_sent += comments_sent

            if issues_sent == 0 and comments_sent == 0:
                log.info("GitHub request done for %s: no new issues or comments", full_name)
        except Exception as e:
            log.warning("Repo %s: %s", full_name, e)

    if total_issues_sent == 0 and total_comments_sent == 0:
        log.info(
            "Poll complete: %d repo(s) checked, no new issues or comments",
            repos_checked,
        )
    else:
        log.info(
            "Poll complete: %d repo(s) checked, %d issue(s) and %d comment(s) sent",
            repos_checked,
            total_issues_sent,
            total_comments_sent,
        )

    return utc_now_iso()


def main() -> None:
    errors = validate_config()
    if errors:
        for msg in errors:
            log.error("Config: %s", msg)
        log.error("Fix the configuration and restart.")
        sys.exit(1)

    if not check_owner_exists(GITHUB_NAME):
        log.error("GitHub owner '%s' not found or inaccessible. Check GITHUB_NAME and GITHUB_TOKEN.", GITHUB_NAME)
        sys.exit(1)

    log.info(
        "Starting bot for owner=%s, poll_interval=%ss",
        GITHUB_NAME,
        POLL_INTERVAL_SECONDS,
    )
    if POLL_INTERVAL_CLAMPED:
        log.warning(
            "Specified poll interval is invalid (less than minimum). "
            "Interval is set to minimum: 60 seconds"
        )

    while True:
        try:
            last_poll_at = load(STATE_PATH)
            if last_poll_at is None:
                last_poll_at = utc_now_iso()
                save(STATE_PATH, last_poll_at)
                log.info("First run: state initialized, no old issues sent")
            else:
                last_poll_at = run_once(last_poll_at)
                save(STATE_PATH, last_poll_at)
        except KeyboardInterrupt:
            log.info("Stopping")
            break
        except RateLimitExceeded as e:
            wait_sec = max(0, e.reset_at - int(time.time()))
            if wait_sec > 0:
                log.warning("Waiting %d s until GitHub rate limit resets, then retrying.", wait_sec)
                time.sleep(wait_sec)
        except Exception as e:
            log.exception("Poll error: %s", e)
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
