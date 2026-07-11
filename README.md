# GitHub Issues → Telegram bot + Swarmica

Отслеживает новые issues и комментарии в репозиториях организации GitHub и:
- шлёт уведомления в чат Telegram;
- создаёт заявки в Swarmica (helpdesk) через API.

Старые issues не подгружаются — уведомления только о том, что появилось после старта контейнера.

## Настройка

1. Создайте бота в Telegram (@BotFather), получите `TELEGRAM_BOT_TOKEN`.
2. Создайте группу, добавьте бота и участников. Узнайте `TELEGRAM_CHAT_ID` (например, напишите в группу боту @userinfobot или получите из `getUpdates` после сообщения в группу).
3. **GitHub Personal Access Token** — настоятельно рекомендуется. Без токена лимит 60 запросов в час; один опрос при нескольких репо и issue уже даёт десятки запросов, лимит быстро кончается. С токеном — 5000 запросов в час. Для приватных репо нужен scope `repo`.
4. Создайте в каталоге с `docker-compose.yml` файл `.env` и заполните переменные (пример ниже). При старте бот проверяет корректность настроек (в том числе существование владельца на GitHub) и выводит ошибки в лог при неверных данных.

Пример `.env`:

```env
GITHUB_NAME=my-org
# GITHUB_TOKEN=ghp_xxxxxxxxxxxx
TELEGRAM_BOT_TOKEN=123456:ABC-def...
TELEGRAM_CHAT_ID=-1001234567890
# Swarmica (опционально; если не заданы оба — интеграция отключена)
# SWARMICA_API_URL=https://your-instance.swarmica.ru
# SWARMICA_API_TOKEN=your_api_token
# SWARMICA_REQUESTER_EMAIL=github-issues@testit.software
# SWARMICA_ASSIGNEE_EMAIL=agent@company.com
# SWARMICA_TICKET_URL=https://help.testit.software/tickets/{id}
# Необязательно: через запятую логины GitHub — их комментарии не уходят в Telegram,
# но в Swarmica уходят; для таких авторов статус заявки → PENDING (ожидает ответа клиента)
# IGNORE_COMMENT_AUTHORS=bot-user,dependabot
```

## Запуск в Docker

```bash
docker compose up -d
```

Состояние (`state.json`: время последнего опроса и дедуп ключей) хранится в папке **`./data`** рядом с `docker-compose.yml` и `.env` (bind mount в контейнер на `/data`). При обновлении образа данные не теряются. Папку `data/` не коммитьте в git (она в `.gitignore`). Чтобы сменить организацию GitHub — поменяйте `GITHUB_NAME` в `.env` и перезапустите контейнер (при необходимости удалите или отредактируйте `data/state.json`).

## Переменные окружения

Все настройки задаются через переменные окружения (файл `.env` или `env_file` в Docker).

| Переменная | Обязательная | Описание | По умолчанию |
|------------|--------------|----------|--------------|
| `GITHUB_NAME` | да | Владелец репозиториев: **организация** или **пользователь** GitHub | — |
| `GITHUB_TOKEN` | нет* | GitHub Personal Access Token. **Рекомендуется:** без него 60 req/час, одного цикла опроса хватает на 1–2 раза; с токеном 5000 req/час | — |
| `TELEGRAM_BOT_TOKEN` | да | Токен бота Telegram (от @BotFather) | — |
| `TELEGRAM_CHAT_ID` | да | ID чата или группы для уведомлений | — |
| `POLL_INTERVAL_SECONDS` | нет | Интервал между опросами GitHub, в секундах. **Минимум 60** | `300` |
| `STATE_PATH` | нет | Путь к файлу состояния (время последнего опроса) | `/data/state.json` |
| `BODY_PREVIEW_LENGTH` | нет | Сколько символов текста issue/комментария показывать в уведомлении | `300` |
| `IGNORE_COMMENT_AUTHORS` | нет | Через запятую логины GitHub (без `@`); комментарии этих пользователей **не** отправляются в Telegram, но **отправляются** в Swarmica; для них статус заявки меняется на «ожидает ответа клиента» (`PENDING`) | — |
| `SWARMICA_API_URL` | нет* | URL вашей инсталляции Swarmica (без завершающего `/`) | — |
| `SWARMICA_API_TOKEN` | нет* | Постоянный API-токен из Swarmica: Настройки → API и интеграции ([документация](https://support.swarmica.com/article/ru/941-sozdanie-tokena-dlya-podklyucheniya-po-api.html)) | — |
| `SWARMICA_REQUESTER_EMAIL` | нет | Email робота-заявителя в Swarmica, если инстанс требует поле получателя (письма не отправляются) | — |
| `SWARMICA_ASSIGNEE_EMAIL` | нет | Email сотрудника Swarmica — назначается ответственным при создании заявки; если не задан, ответственный выбирает Swarmica | — |
| `SWARMICA_TICKET_URL` | нет | Шаблон ссылки на заявку в интерфейсе Swarmica; `{id}` заменяется на id тикета | `{SWARMICA_API_URL}/tickets/{id}` |
| `SWARMICA_STATUS_OPEN` | нет | Код статуса Swarmica при комментарии клиента на GitHub (заявка снова открыта) | `OPEN` |
| `SWARMICA_STATUS_PENDING` | нет | Код статуса Swarmica при ответе сотрудника (ожидает ответа клиента) | `PENDING` |
| `SWARMICA_STATUS_SOLVED` | нет | Код статуса Swarmica при закрытии GitHub issue (решение предоставлено) | `SOLVED` |
| `SENT_KEYS_MAX` | нет | Максимум ключей успешно доставленных уведомлений в файле состояния (дедуп и повтор при сбое Telegram) | `10000` |
| `LOG_LEVEL` | нет | Уровень логирования: `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |

\* Без `GITHUB_TOKEN` бот работает только с публичными репо; лимит 60 req/час — при нескольких репо и issue исчерпывается за 1–2 цикла. При упоре в лимит бот ждёт сброса и пишет в лог рекомендацию добавить токен.

\* Swarmica включается только если заданы **оба** `SWARMICA_API_URL` и `SWARMICA_API_TOKEN`. В `state.json` хранится связка `org/repo#issue_number` → id заявки в Swarmica.

## Поведение Swarmica

- **Новый GitHub issue** → новая заявка в Swarmica (один issue = одна заявка).
- **Новый комментарий** → комментарий в существующую заявку (новая заявка не создаётся).
- **Комментарий от обычного пользователя GitHub** → комментарий в Swarmica + статус заявки `OPEN`.
- **Комментарий от пользователя из `IGNORE_COMMENT_AUTHORS`** → комментарий в Swarmica + статус `PENDING` (в Telegram не уходит).
- **GitHub issue закрыт** → статус заявки `SOLVED`.

API Swarmica: [документация](https://support.swarmica.ru/api/schema/doc/). Авторизация: заголовок `Authorization: Token <токен>`.
