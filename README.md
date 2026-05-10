# Discord Ticket Bot

Python-бот для Discord, который создает приватные тикеты поддержки через кнопку.

## Возможности

- slash-команда `/ticket-panel` создает панель поддержки;
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

6. Остановить бота:

```bash
docker compose down
```

7. На сервере напиши команду:

```text
/ticket-panel
```

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
```

4. Privileged intents в Discord Developer Portal включать не нужно.

5. Запусти бота:

```bash
python bot.py
```

6. На сервере напиши команду:

```text
/ticket-panel
```

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
