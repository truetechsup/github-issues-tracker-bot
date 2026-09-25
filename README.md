# GitHub Issues → Swarmica

Отслеживает новые issues и комментарии в репозиториях организации GitHub и переносит их в заявки Swarmica (helpdesk) через API.

> **Telegram-уведомления отключены** (Telegram API недоступен из сети развёртывания). Код сохранён в пакете `bot/telegram/` и не подключён к основному приложению; как включить обратно — см. docstring в `bot/telegram/__init__.py`.

Старые issues не подгружаются — в Swarmica переносится только то, что появилось после первого старта контейнера.

## Настройка

1. Получите API-токен Swarmica (Настройки → API и интеграции) — `SWARMICA_API_URL` и `SWARMICA_API_TOKEN` обязательны.
2. **GitHub Personal Access Token** — настоятельно рекомендуется. Без токена лимит 60 запросов в час; один опрос при нескольких репо и issue уже даёт десятки запросов, лимит быстро кончается. С токеном — 5000 запросов в час. Для приватных репо нужен scope `repo`.
3. Скопируйте `.env.example` в `.env` в каталоге с `docker-compose.yml` (`cp .env.example .env`) и заполните переменные — в файле есть описание и пример для каждой (краткий пример ниже). При старте бот проверяет корректность настроек (в том числе существование владельца на GitHub) и выводит ошибки в лог при неверных данных.

Пример `.env`:

```env
GITHUB_NAME=my-org
# GITHUB_TOKEN=ghp_xxxxxxxxxxxx
SWARMICA_API_URL=https://your-instance.swarmica.ru
SWARMICA_API_TOKEN=your_api_token
# SWARMICA_REQUESTER_EMAIL=github-issues@testit.software
# SWARMICA_ASSIGNEE_EMAIL=agent@company.com
# SWARMICA_TICKET_URL=https://help.testit.software/tickets/{id}
# Необязательно: через запятую логины GitHub сотрудников — после их ответа
# статус заявки → PENDING (ожидает ответа клиента), для закрытого issue → SOLVED
# IGNORE_COMMENT_AUTHORS=support-den,taipoxinous
```

## Установка из релиза

Архив релиза (`X.Y.Z.zip` на странице Releases) содержит:

- `docker-compose.yml` — запуск готового образа из GitHub Container Registry;
- `.env.example` — все переменные с описанием и примерами;
- `README.md`.

```bash
cp .env.example .env
```

Заполните `.env` (как минимум `GITHUB_NAME`, `SWARMICA_API_URL`, `SWARMICA_API_TOKEN`) и запустите:

```bash
docker compose up -d
```

При обновлении распакуйте новый архив поверх старого: ваш `.env` и папка `data/` не затрагиваются, так как в архиве лежит только `.env.example`.

## Запуск из исходников в Docker

```bash
docker compose up -d --build
```

Состояние (`state.json`: время последнего опроса и дедуп ключей) хранится в папке **`./data`** рядом с `docker-compose.yml` и `.env` (bind mount в контейнер на `/data`). При обновлении образа данные не теряются. Папку `data/` не коммитьте в git (она в `.gitignore`). Чтобы сменить организацию GitHub — поменяйте `GITHUB_NAME` в `.env` и перезапустите контейнер (при необходимости удалите или отредактируйте `data/state.json`).

## Переменные окружения

Все настройки задаются через переменные окружения (файл `.env` или `env_file` в Docker).

| Переменная | Обязательная | Описание | По умолчанию |
|------------|--------------|----------|--------------|
| `GITHUB_NAME` | да | Владелец репозиториев: **организация** или **пользователь** GitHub | — |
| `GITHUB_TOKEN` | нет* | GitHub Personal Access Token. **Рекомендуется:** без него 60 req/час, одного цикла опроса хватает на 1–2 раза; с токеном 5000 req/час | — |
| `POLL_INTERVAL_SECONDS` | нет | Интервал между опросами GitHub, в секундах. **Минимум 60** | `300` |
| `STATE_PATH` | нет | Путь к файлу состояния (время последнего опроса) | `/data/state.json` |
| `IGNORE_COMMENT_AUTHORS` | нет | Через запятую логины GitHub сотрудников (без `@`). Их комментарии уходят в Swarmica, после чего статус заявки → «ожидает ответа клиента» (`PENDING`), для закрытого issue → `SOLVED`. Issue, открытые ими, заявку не создают | — |
| `SWARMICA_API_URL` | да | URL вашей инсталляции Swarmica (без завершающего `/`) | — |
| `SWARMICA_API_TOKEN` | да | Постоянный API-токен из Swarmica: Настройки → API и интеграции ([документация](https://support.swarmica.com/article/ru/941-sozdanie-tokena-dlya-podklyucheniya-po-api.html)) | — |
| `SWARMICA_REQUESTER_EMAIL` | нет | Email робота-заявителя в Swarmica, если инстанс требует поле получателя (письма не отправляются) | — |
| `SWARMICA_ASSIGNEE_EMAIL` | нет | Email сотрудника Swarmica — назначается ответственным при создании заявки; если не задан, ответственный выбирает Swarmica | — |
| `SWARMICA_TICKET_URL` | нет | Шаблон ссылки на заявку в интерфейсе Swarmica; `{id}` заменяется на id тикета | `{SWARMICA_API_URL}/tickets/{id}` |
| `SWARMICA_STATUS_OPEN` | нет | Код статуса Swarmica при комментарии клиента на GitHub (заявка снова открыта) | `OPEN` |
| `SWARMICA_STATUS_PENDING` | нет | Код статуса Swarmica при ответе сотрудника (ожидает ответа клиента) | `PENDING` |
| `SWARMICA_STATUS_SOLVED` | нет | Код статуса Swarmica при закрытии GitHub issue (решение предоставлено) | `SOLVED` |
| `SENT_KEYS_MAX` | нет | Максимум ключей успешно доставленных уведомлений в файле состояния (дедуп и повтор при сбое) | `10000` |
| `LOG_LEVEL` | нет | Уровень логирования: `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |

\* Без `GITHUB_TOKEN` бот работает только с публичными репо; лимит 60 req/час — при нескольких репо и issue исчерпывается за 1–2 цикла. При упоре в лимит бот ждёт сброса и пишет в лог рекомендацию добавить токен.

Переменные отключённого Telegram (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `BODY_PREVIEW_LENGTH`) сейчас не читаются; их можно оставить в `.env`.

В `state.json` хранится связка `org/repo#issue_number` → id заявки в Swarmica.

## Поведение Swarmica

Текст issue и комментариев переносится в Swarmica **полностью**, без обрезки. Под каждым комментарием — ссылка на сам комментарий в GitHub (`...#issuecomment-N`).

- **Новый GitHub issue** (автор не из `IGNORE_COMMENT_AUTHORS`) → новая заявка в Swarmica: заголовок issue = тема заявки, текст issue = первое сообщение (один issue = одна заявка). Для issue, открытых пользователями из `IGNORE_COMMENT_AUTHORS`, заявка создаётся только при первом комментарии клиента.
- **Комментарий от обычного пользователя GitHub** → комментарий в Swarmica + статус заявки `OPEN` (в том числе если issue закрыт — заявка остаётся открытой, даже если issue закрыли и клиент ответил в пределах одного опроса).
- **Комментарий от пользователя из `IGNORE_COMMENT_AUTHORS`** → комментарий в Swarmica, затем отдельным запросом статус принудительно ставится в `PENDING` (если issue уже закрыт — `SOLVED`, чтобы заявка не переоткрывалась).
- **GitHub issue закрыт** → статус заявки `SOLVED`.

API Swarmica: [документация](https://support.swarmica.ru/api/schema/doc/). Авторизация: заголовок `Authorization: Token <токен>`.
