# Архитектура бота

## Схема

```mermaid
flowchart TB
    subgraph env["Конфиг (переменные окружения)"]
        GITHUB_NAME
        GITHUB_TOKEN
        TELEGRAM_BOT_TOKEN
        TELEGRAM_CHAT_ID
        POLL_INTERVAL
        STATE_PATH
    end

    subgraph main["main.py — главный цикл"]
        direction TB
        load_state["load(state)"]
        run_once["run_once(since)"]
        save_state["save(state)"]
        sleep["sleep(POLL_INTERVAL)"]
        load_state --> run_once --> save_state --> sleep --> load_state
    end

    subgraph github["github_client.py"]
        get_repos["get_owner_repos()"]
        get_issues["get_repo_issues()"]
        get_comments["get_issue_comments()"]
    end

    subgraph state["state.py"]
        state_file["/data/state.json\nlast_poll_at"]
    end

    subgraph formatter["formatter.py"]
        format_issue["format_issue()"]
        format_comment["format_comment()"]
    end

    subgraph telegram["telegram_client.py"]
        send["send_message()"]
    end

    env --> main
    env --> github
    env --> telegram

    main --> load_state
    run_once --> get_repos
    get_repos --> get_issues
    get_issues --> get_comments
    run_once --> format_issue
    run_once --> format_comment
    format_issue --> send
    format_comment --> send
    main --> state_file
    run_once --> state_file

    github --> api["GitHub API\n(rest)"]
    send --> tg["Telegram API\n(sendMessage)"]
```

## Поток данных

1. **Старт** — загрузка конфига, проверка владельца GitHub, загрузка `last_poll_at` из `state.json`.
2. **Цикл (каждые POLL_INTERVAL сек):**
   - Запрос списка репозиториев владельца (GitHub).
   - Для каждого репо — запрос issues, обновлённых после `last_poll_at`.
   - Для каждого issue — запрос комментариев.
   - Новые issue/комментарии (created_at ≥ last_poll_at) форматируются и отправляются в Telegram.
   - Запись нового `last_poll_at` в `state.json`.
3. **Ожидание** — `sleep(POLL_INTERVAL)`, затем повтор цикла.

## Модули

| Модуль | Роль |
|--------|------|
| `main.py` | Цикл опроса, вызов клиентов, сохранение состояния, обработка RateLimitExceeded |
| `github_client.py` | Запросы к GitHub API (repos, issues, comments), обработка 403 rate limit |
| `telegram_client.py` | Отправка сообщений в чат (sendMessage) |
| `formatter.py` | Формирование текста уведомлений, экранирование HTML |
| `state.py` | Чтение/запись `last_poll_at` в JSON-файл |
| `config.py` | Чтение и валидация переменных окружения |

## Внешние зависимости

- **GitHub API** — получение репозиториев, issues, комментариев (REST, с пагинацией).
- **Telegram Bot API** — отправка сообщений в заданный чат (односторонняя).
