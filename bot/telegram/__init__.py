"""
Telegram notifications — DISABLED.

The package is kept but not imported by the main app (Telegram API is unreachable from
the deployment network). Nothing here runs unless it is wired back into bot/main.py.

How to re-enable:
  1. In bot/main.py uncomment the lines marked "Telegram (disabled)".
  2. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID (optionally BODY_PREVIEW_LENGTH) in .env.

Telegram dedup keys ("tg:issue:…", "tg:comment:…") are still persisted in state.json
under "sent_keys", so re-enabling does not resend old events.

Modules:
  config.py    — TELEGRAM_* / BODY_PREVIEW_LENGTH env and validation
  client.py    — sendMessage to the configured chat
  formatter.py — HTML text of issue/comment notifications
  notifier.py  — dedup + delivery used by the poll loop
"""
