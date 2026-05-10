# Discord Ticket Bot

Python-бот для Discord, который создает приватные тикеты поддержки через кнопку.

## Возможности

- slash-команда `/ticket-panel` создает панель поддержки и сообщение с покупкой подписки;
- slash-команда `/remnawave-active` показывает активных и онлайн пользователей Remnawave;
- slash-команда `/remnawave-panel` создает постоянную панель Remnawave со списком серверов онлайн;
- пользователь нажимает кнопку и получает приватный канал тикета;
- поддержку автоматически пингует роль из `SUPPORT_ROLE_ID`;
- у пользователя может быть только один открытый тикет;
- тикет закрывается кнопкой внутри канала.

## Запуск через Docker Compose

1. Создай файл `.env` на основе примера:

```bash
cp .env.example .env
```

2. Заполни `.env`:

```env
DISCORD_TOKEN=токен_бота
GUILD_ID=id_сервера
SUPPORT_ROLE_ID=id_роли_поддержки
TICKET_CATEGORY_ID=id_категории_тикетов_или_оставь_пустым
LOG_LEVEL=INFO
COMMAND_SYNC_TIMEOUT=60
REMNAWAVE_BASE_URL=https://panel.example.com
REMNAWAVE_API_TOKEN=токен_api_из_remnawave
REMNAWAVE_CADDY_API_KEY=api_key_caddy_если_используется_или_оставь_пустым
REMNAWAVE_STATS_PATH=/api/system/stats/recap
REMNAWAVE_NODES_PATH=/api/nodes
REMNAWAVE_REQUEST_TIMEOUT=15
REMNAWAVE_X_FORWARDED_FOR=127.0.0.1
REMNAWAVE_X_FORWARDED_PROTO=https
REMNAWAVE_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36
REMNAWAVE_PANEL_CHANNEL_ID=
REMNAWAVE_PANEL_MESSAGE_ID=
REMNAWAVE_CONTACTS_MESSAGE_ID=
REMNAWAVE_PANEL_REFRESH_SECONDS=60
REMNAWAVE_PANEL_TOP_LIMIT=10
```

3. Privileged intents в Discord Developer Portal включать не нужно.

4. Собери и запусти бота:

```bash
docker compose up --build -d
```

Если в логах запускается старая версия бота, пересобери образ без кэша:

```bash
docker compose down
docker compose build --no-cache bot
docker compose up -d --force-recreate bot
```

5. Посмотреть логи:

```bash
docker compose logs -f bot
```

После запуска в логах должно быть:

```text
Synced 3 slash command(s) for guild ...: ticket-panel, remnawave-active, remnawave-panel
```

6. Остановить бота:

```bash
docker compose down
```

7. На сервере от имени администратора напиши команду:

```text
/ticket-panel
```

Команда сразу отправит два сообщения: панель поддержки с кнопкой тикета и контакты покупки подписки.

## Локальная установка без Docker

1. Создай виртуальное окружение и установи зависимости:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Создай файл `.env` на основе примера:

```bash
cp .env.example .env
```

3. Заполни `.env`:

```env
DISCORD_TOKEN=токен_бота
GUILD_ID=id_сервера
SUPPORT_ROLE_ID=id_роли_поддержки
TICKET_CATEGORY_ID=id_категории_тикетов_или_оставь_пустым
LOG_LEVEL=INFO
COMMAND_SYNC_TIMEOUT=60
REMNAWAVE_BASE_URL=https://panel.example.com
REMNAWAVE_API_TOKEN=токен_api_из_remnawave
REMNAWAVE_CADDY_API_KEY=api_key_caddy_если_используется_или_оставь_пустым
REMNAWAVE_STATS_PATH=/api/system/stats/recap
REMNAWAVE_NODES_PATH=/api/nodes
REMNAWAVE_REQUEST_TIMEOUT=15
REMNAWAVE_X_FORWARDED_FOR=127.0.0.1
REMNAWAVE_X_FORWARDED_PROTO=https
REMNAWAVE_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36
REMNAWAVE_PANEL_CHANNEL_ID=
REMNAWAVE_PANEL_MESSAGE_ID=
REMNAWAVE_CONTACTS_MESSAGE_ID=
REMNAWAVE_PANEL_REFRESH_SECONDS=60
REMNAWAVE_PANEL_TOP_LIMIT=10
```

4. Privileged intents в Discord Developer Portal включать не нужно.

5. Запусти бота:

```bash
python bot.py
```

6. На сервере от имени администратора напиши команду:

```text
/ticket-panel
```

Команда сразу отправит два сообщения: панель поддержки с кнопкой тикета и контакты покупки подписки.

## Права бота

Боту нужны права на сервере, а если указан `TICKET_CATEGORY_ID`, то и в этой категории:

- `Manage Channels`;
- `Manage Roles` не нужен;
- `View Channels`;
- `Send Messages`;
- `Embed Links`;
- `Read Message History`;

Если Discord пишет `Missing Permissions`, проверь:

- роль бота находится выше ролей, с которыми он должен работать;
- в категории тикетов нет запрета на `Manage Channels` для роли бота;
- при приглашении бота были выданы нужные permissions.

## Remnawave

Команда `/remnawave-active` доступна только администраторам сервера и отвечает приватно.
Команда `/remnawave-panel` отправляет постоянную публичную панель в канал, а вторым сообщением — контакты для покупки подписки.
Подробности подключения к Remnawave пишутся в логи бота без вывода токенов.

Для нее нужны:

- `REMNAWAVE_BASE_URL` — URL панели Remnawave, например `https://panel.example.com`;
- `REMNAWAVE_API_TOKEN` — API token из Remnawave Settings;
- `REMNAWAVE_CADDY_API_KEY` — необязательно, если перед Remnawave стоит Caddy Auth;
- `REMNAWAVE_STATS_PATH` — путь статистики, по умолчанию `/api/system/stats/recap`.
- `REMNAWAVE_NODES_PATH` — путь списка серверов, по умолчанию `/api/nodes`; используется для списка серверов онлайн.
- `REMNAWAVE_REQUEST_TIMEOUT` — таймаут API-запросов к Remnawave в секундах.
- `REMNAWAVE_X_FORWARDED_FOR` и `REMNAWAVE_X_FORWARDED_PROTO` — заголовки для прокси Remnawave, обычно можно оставить `127.0.0.1` и `https`.
- `REMNAWAVE_USER_AGENT` — браузерный User-Agent для Cloudflare, чтобы API-запросы не выглядели как стандартный `Python-urllib`.
- `REMNAWAVE_PANEL_CHANNEL_ID`, `REMNAWAVE_PANEL_MESSAGE_ID` и `REMNAWAVE_CONTACTS_MESSAGE_ID` — ID канала, онлайн-панели и сообщения с контактами для восстановления после перезапуска бота. Если указан только канал, бот создаст сообщения сам и напишет ID в логи.
- `REMNAWAVE_PANEL_REFRESH_SECONDS` — интервал обновления панели, минимум 30 секунд.
- `REMNAWAVE_PANEL_TOP_LIMIT` — оставлено для совместимости; панель показывает полный список серверов, где онлайн больше 0.
- `LOG_LEVEL` — уровень логов, обычно `INFO`; для более подробной диагностики можно поставить `DEBUG`.
- `COMMAND_SYNC_TIMEOUT` — сколько секунд ждать синхронизацию slash-команд с Discord.

Чтобы создать постоянную панель, вызови `/remnawave-panel` в нужном канале. Бот отправит онлайн-панель и второе сообщение с контактами: Telegram-бот `@elix_vpn_robot` и веб-кабинет `https://cabinet.elix.ink/login`. В приватном ответе он покажет `REMNAWAVE_PANEL_CHANNEL_ID`, `REMNAWAVE_PANEL_MESSAGE_ID` и `REMNAWAVE_CONTACTS_MESSAGE_ID`; добавь их в `.env`, чтобы бот редактировал эти же сообщения после перезапуска контейнера.
