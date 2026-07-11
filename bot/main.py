"""Main loop: poll GitHub, notify Telegram channel and Swarmica helpdesk."""

import logging
import sys
import time
from datetime import datetime, timezone

from bot.config import (
    GITHUB_NAME,
    IGNORE_COMMENT_AUTHORS,
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
from bot import swarmica_client
from bot.state import issue_map_key, load, maybe_trim_sent_keys_in_place, save
from bot.telegram_client import send_message

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)


def _comment_author(comment: dict) -> str:
    return ((comment.get("user") or {}).get("login") or "").strip().lower()


def _ensure_swarmica_ticket(
    repo_full_name: str,
    issue: dict,
    issue_tickets: dict[str, int],
    swarmica_sent_keys: list[str],
    swarmica_sent_set: set[str],
) -> int | None:
    number = issue.get("number")
    if number is None:
        return None

    map_key = issue_map_key(repo_full_name, number)
    existing = issue_tickets.get(map_key)
    if existing is not None:
        return existing

    create_key = f"swarmica:issue:{map_key}"
    if create_key in swarmica_sent_set:
        return issue_tickets.get(map_key)

    try:
        ticket_id = swarmica_client.create_ticket_from_issue(
            repo_full_name,
            issue,
            idempotency_key=create_key,
        )
    except swarmica_client.SwarmicaError:
        log.warning(
            "Swarmica: ticket not created for %s #%s (will retry on next poll)",
            repo_full_name,
            number,
        )
        return None

    issue_tickets[map_key] = ticket_id
    swarmica_sent_keys.append(create_key)
    swarmica_sent_set.add(create_key)
    return ticket_id


def _sync_issue_closed(
    repo_full_name: str,
    issue: dict,
    issue_tickets: dict[str, int],
    issue_closed_synced: list[str],
    closed_synced_set: set[str],
) -> None:
    if (issue.get("state") or "").strip().lower() != "closed":
        return

    number = issue.get("number")
    if number is None:
        return

    map_key = issue_map_key(repo_full_name, number)
    if map_key in closed_synced_set:
        return

    ticket_id = issue_tickets.get(map_key)
    if ticket_id is None:
        return

    close_key = f"swarmica:closed:{map_key}"
    try:
        swarmica_client.set_ticket_solved(ticket_id, idempotency_key=close_key)
    except swarmica_client.SwarmicaError:
        log.warning(
            "Swarmica: failed to mark ticket %s solved for closed issue %s (will retry)",
            ticket_id,
            map_key,
        )
        return

    issue_closed_synced.append(map_key)
    closed_synced_set.add(map_key)
    log.info("Swarmica: issue %s closed, ticket %s marked solved", map_key, ticket_id)


def run_once(
    last_poll_at: str,
    sent_keys: list[str],
    swarmica_sent_keys: list[str],
    issue_tickets: dict[str, int],
    issue_closed_synced: list[str],
) -> str:
    """
    Fetch issues updated since last_poll_at; deliver new events to Telegram and Swarmica.

    Telegram uses sent_keys; Swarmica uses swarmica_sent_keys and issue_tickets mapping.
    """
    since_dt = datetime.fromisoformat(last_poll_at.replace("Z", "+00:00"))
    tg_sent_set = set(sent_keys)
    swarmica_sent_set = set(swarmica_sent_keys)
    closed_synced_set = set(issue_closed_synced)
    swarmica_on = swarmica_client.is_enabled()

    total_issues_tg = 0
    total_comments_tg = 0
    total_issues_swarmica = 0
    total_comments_swarmica = 0
    repos_checked = 0

    log.info("Polling GitHub since %s (owner=%s)", last_poll_at, GITHUB_NAME)

    for repo in get_owner_repos(GITHUB_NAME):
        full_name = repo["full_name"]
        owner = repo["owner"]["login"]
        name = repo["name"]
        repos_checked += 1
        issues_tg = 0
        comments_tg = 0
        issues_swarmica = 0
        comments_swarmica = 0

        try:
            log.debug("Checking repo: %s", full_name)
            for issue in get_repo_issues(owner, name, since_dt):
                number = issue.get("number")
                map_key = issue_map_key(full_name, number) if number is not None else None
                is_new_issue = (issue.get("created_at") or "") >= last_poll_at

                if swarmica_on and is_new_issue and map_key is not None:
                    create_key = f"swarmica:issue:{map_key}"
                    if create_key not in swarmica_sent_set:
                        ticket_id = _ensure_swarmica_ticket(
                            full_name,
                            issue,
                            issue_tickets,
                            swarmica_sent_keys,
                            swarmica_sent_set,
                        )
                        if ticket_id is not None:
                            issues_swarmica += 1

                if is_new_issue and map_key is not None:
                    tg_key = f"tg:issue:{map_key}"
                    if tg_key not in tg_sent_set:
                        text = format_issue(full_name, issue)
                        if send_message(text):
                            sent_keys.append(tg_key)
                            tg_sent_set.add(tg_key)
                            issues_tg += 1
                            log.info("Telegram: sent issue %s #%s", full_name, number)
                        else:
                            log.warning(
                                "Telegram: issue notification not delivered for %s #%s "
                                "(will retry on next poll)",
                                full_name,
                                number,
                            )

                for comment in get_issue_comments(owner, name, issue["number"]):
                    if (comment.get("created_at") or "") < last_poll_at:
                        continue
                    cid = comment.get("id")
                    if cid is None:
                        log.warning(
                            "Skipping comment without id on %s #%s",
                            full_name,
                            issue["number"],
                        )
                        continue

                    author = _comment_author(comment)
                    ignored_for_tg = author in IGNORE_COMMENT_AUTHORS

                    if swarmica_on and map_key is not None:
                        swarmica_comment_key = f"swarmica:comment:{cid}"
                        if swarmica_comment_key not in swarmica_sent_set:
                            ticket_id = _ensure_swarmica_ticket(
                                full_name,
                                issue,
                                issue_tickets,
                                swarmica_sent_keys,
                                swarmica_sent_set,
                            )
                            if ticket_id is not None:
                                set_pending = author in IGNORE_COMMENT_AUTHORS
                                try:
                                    swarmica_client.add_issue_comment(
                                        ticket_id,
                                        full_name,
                                        issue,
                                        comment,
                                        idempotency_key=swarmica_comment_key,
                                        set_pending=set_pending,
                                    )
                                    swarmica_sent_keys.append(swarmica_comment_key)
                                    swarmica_sent_set.add(swarmica_comment_key)
                                    comments_swarmica += 1
                                    log.info(
                                        "Swarmica: sent comment on %s #%s (ticket %s, pending=%s)",
                                        full_name,
                                        number,
                                        ticket_id,
                                        set_pending,
                                    )
                                except swarmica_client.SwarmicaError:
                                    log.warning(
                                        "Swarmica: comment not delivered for %s #%s "
                                        "(comment id=%s; will retry on next poll)",
                                        full_name,
                                        number,
                                        cid,
                                    )

                    if not ignored_for_tg:
                        tg_comment_key = f"tg:comment:{cid}"
                        if tg_comment_key not in tg_sent_set:
                            text = format_comment(full_name, issue, comment)
                            if send_message(text):
                                sent_keys.append(tg_comment_key)
                                tg_sent_set.add(tg_comment_key)
                                comments_tg += 1
                                log.info("Telegram: sent comment %s #%s", full_name, number)
                            else:
                                log.warning(
                                    "Telegram: comment notification not delivered for %s #%s "
                                    "(comment id=%s; will retry on next poll)",
                                    full_name,
                                    number,
                                    cid,
                                )
                    else:
                        log.info(
                            "Telegram: skip comment %s on %s #%s (author %s in IGNORE_COMMENT_AUTHORS)",
                            cid,
                            full_name,
                            number,
                            author or "?",
                        )

                if swarmica_on and map_key is not None:
                    _sync_issue_closed(
                        full_name,
                        issue,
                        issue_tickets,
                        issue_closed_synced,
                        closed_synced_set,
                    )

            total_issues_tg += issues_tg
            total_comments_tg += comments_tg
            total_issues_swarmica += issues_swarmica
            total_comments_swarmica += comments_swarmica

            if (
                issues_tg == 0
                and comments_tg == 0
                and issues_swarmica == 0
                and comments_swarmica == 0
            ):
                log.info("GitHub request done for %s: no new issues or comments", full_name)

            save(
                STATE_PATH,
                last_poll_at,
                sent_keys,
                swarmica_sent_keys=swarmica_sent_keys,
                issue_tickets=issue_tickets,
                issue_closed_synced=issue_closed_synced,
            )
        except RateLimitExceeded:
            raise
        except Exception as e:
            log.warning("Repo %s: %s", full_name, e)

    maybe_trim_sent_keys_in_place(sent_keys)
    maybe_trim_sent_keys_in_place(swarmica_sent_keys)
    maybe_trim_sent_keys_in_place(issue_closed_synced)

    if (
        total_issues_tg == 0
        and total_comments_tg == 0
        and total_issues_swarmica == 0
        and total_comments_swarmica == 0
    ):
        log.info(
            "Poll complete: %d repo(s) checked, no new issues or comments",
            repos_checked,
        )
    else:
        log.info(
            "Poll complete: %d repo(s), TG %d issue(s) + %d comment(s), "
            "Swarmica %d issue(s) + %d comment(s)",
            repos_checked,
            total_issues_tg,
            total_comments_tg,
            total_issues_swarmica,
            total_comments_swarmica,
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
        log.error(
            "GitHub owner '%s' not found or inaccessible. Check GITHUB_NAME and GITHUB_TOKEN.",
            GITHUB_NAME,
        )
        sys.exit(1)

    log.info(
        "Starting bot for owner=%s, poll_interval=%ss",
        GITHUB_NAME,
        POLL_INTERVAL_SECONDS,
    )
    if IGNORE_COMMENT_AUTHORS:
        log.info(
            "Ignoring GitHub comment authors in Telegram only: %s",
            ", ".join(sorted(IGNORE_COMMENT_AUTHORS)),
        )
    if swarmica_client.is_enabled():
        log.info("Swarmica integration enabled")
    else:
        log.info("Swarmica integration disabled (set SWARMICA_API_URL and SWARMICA_API_TOKEN)")
    if POLL_INTERVAL_CLAMPED:
        log.warning(
            "Specified poll interval is invalid (less than minimum). "
            "Interval is set to minimum: 60 seconds"
        )

    while True:
        try:
            state = load(STATE_PATH)
            if state is None:
                last_poll_at = utc_now_iso()
                save(
                    STATE_PATH,
                    last_poll_at,
                    [],
                    swarmica_sent_keys=[],
                    issue_tickets={},
                    issue_closed_synced=[],
                )
                log.info("First run: state initialized, no old issues sent")
            else:
                last_poll_at = state["last_poll_at"] or utc_now_iso()
                sent_keys = list(state["sent_keys"])
                swarmica_sent_keys = list(state.get("swarmica_sent_keys", []))
                issue_tickets = dict(state.get("issue_tickets", {}))
                issue_closed_synced = list(state.get("issue_closed_synced", []))
                new_ts = run_once(
                    last_poll_at,
                    sent_keys,
                    swarmica_sent_keys,
                    issue_tickets,
                    issue_closed_synced,
                )
                save(
                    STATE_PATH,
                    new_ts,
                    sent_keys,
                    swarmica_sent_keys=swarmica_sent_keys,
                    issue_tickets=issue_tickets,
                    issue_closed_synced=issue_closed_synced,
                )
        except KeyboardInterrupt:
            log.info("Stopping")
            break
        except RateLimitExceeded as e:
            wait_sec = max(0, e.reset_at - int(time.time()))
            if wait_sec > 0:
                log.warning(
                    "Waiting %d s until GitHub rate limit resets, then retrying.",
                    wait_sec,
                )
                time.sleep(wait_sec)
        except Exception as e:
            log.exception("Poll error: %s", e)
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
