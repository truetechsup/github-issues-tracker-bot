# Архитектура бота

## Схема

```mermaid
flowchart TB
    subgraph env["Конфиг (переменные окружения)"]
        GITHUB_NAME
        GITHUB_TOKEN
        TELEGRAM_BOT_TOKEN
        TELEGRAM_CHAT_ID
        SWARMICA_API_URL
        SWARMICA_API_TOKEN
        POLL_INTERVAL
        STATE_PATH
    end

    subgraph main["main.py — оркестрация"]
        direction TB
        load_state["load(state)"]
        run_once["run_once()"]
        save_state["save(state)"]
        sleep["sleep(POLL_INTERVAL)"]
        load_state --> run_once --> save_state --> sleep --> load_state
    end

    subgraph github["github_client.py — опрос GitHub"]
        get_repos["get_owner_repos()"]
        get_issues["get_repo_issues()"]
        get_comments["get_issue_comments()"]
    end

    subgraph state["state.py"]
        state_file["/data/state.json\nlast_poll_at, sent_keys,\nissue_tickets, ..."]
    end

    subgraph tg_fmt["formatter.py — Telegram HTML"]
        format_issue["format_issue()"]
        format_comment["format_comment()"]
    end

    subgraph telegram["telegram_client.py — канал Telegram"]
        send["send_message()"]
    end

    subgraph swarm_fmt["swarmica_formatter.py — Swarmica HTML"]
        swarm_issue["format_issue_ticket_*()"]
        swarm_comment["format_comment_body()"]
    end

    subgraph swarmica["swarmica_client.py — заявки Swarmica"]
        create_ticket["create_ticket_from_issue()"]
        add_comment["add_issue_comment()"]
        set_solved["set_ticket_solved()"]
    end

    env --> main
    env --> github
    env --> telegram
    env --> swarmica

    main --> load_state
    run_once --> get_repos
    get_repos --> get_issues
    get_issues --> get_comments
    run_once --> format_issue
    run_once --> format_comment
    format_issue --> send
    format_comment --> send
    run_once --> swarm_issue
    run_once --> swarm_comment
    swarm_issue --> create_ticket
    swarm_comment --> add_comment
    run_once --> set_solved
    main --> state_file
    run_once --> state_file

    github --> api["GitHub API\n(REST)"]
    send --> tg["Telegram API\n(sendMessage)"]
    create_ticket --> sw["Swarmica API\n(/api/tickets/)"]
    add_comment --> sw
    set_solved --> sw
```

## Поток данных

1. **Старт** — загрузка конфига, проверка владельца GitHub, загрузка состояния из `state.json`.
2. **Цикл (каждые POLL_INTERVAL сек):**
   - Запрос списка репозиториев владельца (GitHub).
   - Для каждого репо — запрос issues, обновлённых после `last_poll_at`.
   - Для каждого issue — запрос комментариев.
   - **Новый issue** (`created_at ≥ last_poll_at`):
     - Swarmica: создать заявку, сохранить `org/repo#N → ticket_id`.
     - Telegram: отправить уведомление.
   - **Новый комментарий**:
     - Swarmica: добавить в заявку (создать заявку, если ещё нет); для авторов из `IGNORE_COMMENT_AUTHORS` — статус `PENDING`.
     - Telegram: отправить, кроме авторов из `IGNORE_COMMENT_AUTHORS`.
   - **Issue закрыт** (`state == closed`): Swarmica — статус `SOLVED` (один раз).
   - Запись нового `last_poll_at` и чекпоинтов в `state.json`.
3. **Ожидание** — `sleep(POLL_INTERVAL)`, затем повтор цикла.

## Модули

| Модуль | Роль |
|--------|------|
| `main.py` | Цикл опроса, оркестрация Telegram и Swarmica, сохранение состояния |
| `github_client.py` | Запросы к GitHub API (repos, issues, comments), обработка rate limit |
| `telegram_client.py` | Отправка уведомлений в Telegram-канал |
| `formatter.py` | Текст уведомлений для Telegram (HTML) |
| `swarmica_client.py` | Создание заявок, комментариев и смена статусов в Swarmica API |
| `swarmica_formatter.py` | Текст заявок/комментариев для Swarmica (HTML) |
| `state.py` | `last_poll_at`, дедуп-ключи, маппинг issue → ticket |
| `config.py` | Чтение и валидация переменных окружения |

## Внешние зависимости

- **GitHub API** — репозитории, issues, комментарии (REST, пагинация).
- **Telegram Bot API** — `sendMessage` в заданный чат.
- **Swarmica API** — `POST /api/tickets/`, `POST /api/tickets/{id}/comments/`, `PATCH /api/tickets/{id}/` ([схема](https://support.swarmica.ru/api/schema/doc/)).
