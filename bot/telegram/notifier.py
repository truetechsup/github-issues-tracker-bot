"""Deliver new issues/comments to Telegram with dedup via state sent_keys."""

import logging

from bot.telegram.client import send_message
from bot.telegram.formatter import format_comment, format_issue

log = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Wraps Telegram delivery for one poll.

    sent_keys is the persisted list from state.json; it is appended to in place.
    """

    def __init__(self, sent_keys: list[str]):
        self.sent_keys = sent_keys
        self._sent_set = set(sent_keys)
        self.issues_sent = 0
        self.comments_sent = 0

    def _mark(self, key: str) -> None:
        self.sent_keys.append(key)
        self._sent_set.add(key)

    def notify_issue(
        self,
        repo_full_name: str,
        issue: dict,
        map_key: str,
        swarmica_ticket_url: str | None = None,
    ) -> None:
        key = f"tg:issue:{map_key}"
        if key in self._sent_set:
            return
        text = format_issue(repo_full_name, issue, swarmica_ticket_url=swarmica_ticket_url)
        number = issue.get("number")
        if send_message(text):
            self._mark(key)
            self.issues_sent += 1
            log.info("Telegram: sent issue %s #%s", repo_full_name, number)
        else:
            log.warning(
                "Telegram: issue notification not delivered for %s #%s "
                "(will retry on next poll)",
                repo_full_name,
                number,
            )

    def notify_comment(
        self,
        repo_full_name: str,
        issue: dict,
        comment: dict,
        *,
        author_ignored: bool,
        swarmica_ticket_url: str | None = None,
    ) -> None:
        cid = comment.get("id")
        number = issue.get("number")
        if author_ignored:
            log.info(
                "Telegram: skip comment %s on %s #%s (author in IGNORE_COMMENT_AUTHORS)",
                cid,
                repo_full_name,
                number,
            )
            return
        key = f"tg:comment:{cid}"
        if key in self._sent_set:
            return
        text = format_comment(
            repo_full_name, issue, comment, swarmica_ticket_url=swarmica_ticket_url
        )
        if send_message(text):
            self._mark(key)
            self.comments_sent += 1
            log.info("Telegram: sent comment %s #%s", repo_full_name, number)
        else:
            log.warning(
                "Telegram: comment notification not delivered for %s #%s "
                "(comment id=%s; will retry on next poll)",
                repo_full_name,
                number,
                cid,
            )
