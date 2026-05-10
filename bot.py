import asyncio
import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any, Optional

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv


load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("tickets-bot")

BOT_VERSION = "2026-05-10-remnawave-active"
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
SUPPORT_ROLE_ID = int(os.getenv("SUPPORT_ROLE_ID", "0"))
TICKET_CATEGORY_ID = os.getenv("TICKET_CATEGORY_ID")
REMNAWAVE_BASE_URL = os.getenv("REMNAWAVE_BASE_URL", "").rstrip("/")
REMNAWAVE_API_TOKEN = os.getenv("REMNAWAVE_API_TOKEN", "")
REMNAWAVE_CADDY_API_KEY = os.getenv("REMNAWAVE_CADDY_API_KEY", "")
REMNAWAVE_STATS_PATH = os.getenv("REMNAWAVE_STATS_PATH", "/api/system/stats/recap")
REMNAWAVE_REQUEST_TIMEOUT = float(os.getenv("REMNAWAVE_REQUEST_TIMEOUT", "15"))
REMNAWAVE_X_FORWARDED_FOR = os.getenv("REMNAWAVE_X_FORWARDED_FOR", "127.0.0.1")
REMNAWAVE_X_FORWARDED_PROTO = os.getenv("REMNAWAVE_X_FORWARDED_PROTO", "https")
COMMAND_SYNC_TIMEOUT = float(os.getenv("COMMAND_SYNC_TIMEOUT", "60"))


intents = discord.Intents.default()
intents.guilds = True

bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)


def get_ticket_category(guild: discord.Guild) -> Optional[discord.CategoryChannel]:
    if not TICKET_CATEGORY_ID:
        return None

    category = guild.get_channel(int(TICKET_CATEGORY_ID))
    if isinstance(category, discord.CategoryChannel):
        return category

    return None


def bot_can_manage_channels(guild: discord.Guild, category: Optional[discord.CategoryChannel]) -> bool:
    bot_member = guild.me
    if not bot_member:
        return False

    if category:
        return category.permissions_for(bot_member).manage_channels

    return bot_member.guild_permissions.manage_channels


async def find_existing_ticket(guild: discord.Guild, user: discord.Member) -> Optional[discord.TextChannel]:
    topic_marker = f"ticket_owner:{user.id}"

    for channel in guild.text_channels:
        if channel.topic and topic_marker in channel.topic:
            return channel

    return None


def normalize_key(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def find_value(payload: Any, names: set[str]) -> Any:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if normalize_key(str(key)) in names:
                return value

        for value in payload.values():
            found = find_value(value, names)
            if found is not None:
                return found

    if isinstance(payload, list):
        for value in payload:
            found = find_value(value, names)
            if found is not None:
                return found

    return None


def find_path(payload: Any, path: tuple[str, ...]) -> Any:
    current = payload
    for key in path:
        if not isinstance(current, dict):
            return None

        normalized_key = normalize_key(key)
        matching_key = next(
            (
                item_key
                for item_key in current
                if normalize_key(str(item_key)) == normalized_key
            ),
            None,
        )
        if matching_key is None:
            return None

        current = current[matching_key]

    return current


def first_available(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value

    return None


def format_stat(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:,.0f}".replace(",", " ")

    if isinstance(value, str) and value.strip():
        return value

    return "нет данных"


def remnawave_request_json(path: str) -> dict[str, Any]:
    if not REMNAWAVE_BASE_URL or not REMNAWAVE_API_TOKEN:
        raise RuntimeError(
            "REMNAWAVE_BASE_URL and REMNAWAVE_API_TOKEN must be configured."
        )

    if not path.startswith("/"):
        path = f"/{path}"

    request_url = f"{REMNAWAVE_BASE_URL}{path}"
    started_at = time.monotonic()
    logger.info("Remnawave request started: GET %s", request_url)

    request = urllib.request.Request(
        request_url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {REMNAWAVE_API_TOKEN}",
            "x-forwarded-for": REMNAWAVE_X_FORWARDED_FOR,
            "x-forwarded-proto": REMNAWAVE_X_FORWARDED_PROTO,
        },
        method="GET",
    )
    if REMNAWAVE_CADDY_API_KEY:
        request.add_header("X-Api-Key", REMNAWAVE_CADDY_API_KEY)

    try:
        with urllib.request.urlopen(request, timeout=REMNAWAVE_REQUEST_TIMEOUT) as response:
            response_body = response.read().decode("utf-8")
            duration_ms = (time.monotonic() - started_at) * 1000
            logger.info(
                "Remnawave request completed: GET %s -> HTTP %s in %.0fms",
                path,
                response.status,
                duration_ms,
            )
    except urllib.error.HTTPError as error:
        duration_ms = (time.monotonic() - started_at) * 1000
        logger.warning(
            "Remnawave request rejected: GET %s -> HTTP %s in %.0fms",
            path,
            error.code,
            duration_ms,
        )
        raise
    except urllib.error.URLError as error:
        duration_ms = (time.monotonic() - started_at) * 1000
        logger.warning(
            "Remnawave connection failed: GET %s in %.0fms: %s",
            path,
            duration_ms,
            error.reason,
        )
        raise
    except TimeoutError:
        duration_ms = (time.monotonic() - started_at) * 1000
        logger.warning(
            "Remnawave request timed out: GET %s in %.0fms",
            path,
            duration_ms,
        )
        raise

    try:
        payload = json.loads(response_body)
    except json.JSONDecodeError:
        logger.warning(
            "Remnawave returned invalid JSON: GET %s, body length %s",
            path,
            len(response_body),
        )
        raise

    if not isinstance(payload, dict):
        logger.warning(
            "Remnawave returned unexpected JSON type: GET %s -> %s",
            path,
            type(payload).__name__,
        )
        raise RuntimeError("Remnawave returned an unexpected response format.")

    logger.info("Remnawave response parsed: GET %s, top-level keys: %s", path, sorted(payload.keys()))
    return payload


async def fetch_remnawave_stats() -> dict[str, Any]:
    try:
        return await asyncio.to_thread(remnawave_request_json, REMNAWAVE_STATS_PATH)
    except urllib.error.HTTPError as error:
        if error.code != 404 or REMNAWAVE_STATS_PATH == "/api/system/stats":
            raise

    return await asyncio.to_thread(remnawave_request_json, "/api/system/stats")


def format_http_error(error: urllib.error.HTTPError) -> str:
    try:
        response_body = error.read().decode("utf-8").strip()
    except Exception:
        response_body = ""

    if len(response_body) > 300:
        response_body = f"{response_body[:300]}..."

    hint = "Проверь URL, токен и права API."
    if error.code == 403:
        hint = (
            "Доступ запрещен. Чаще всего это API-токен без нужных прав, IP-ограничение"
            " токена или включенный Caddy/Auth Portal без `REMNAWAVE_CADDY_API_KEY`."
        )

    if response_body:
        return f"Remnawave вернул HTTP {error.code}: `{response_body}`\n{hint}"

    return f"Remnawave вернул HTTP {error.code}. {hint}"


def build_remnawave_embed(stats: dict[str, Any]) -> discord.Embed:
    online_now = first_available(
        find_path(stats, ("online", "total")),
        find_path(stats, ("onlineStats", "onlineNow")),
        find_value(stats, {"onlinenow", "onlineusers", "uniqueonlineusers", "totalonline"}),
    )
    last_day = first_available(
        find_path(stats, ("onlineStats", "lastDay")),
        find_value(stats, {"lastday", "onlinelastday"}),
    )
    last_week = first_available(
        find_path(stats, ("onlineStats", "lastWeek")),
        find_value(stats, {"lastweek", "onlinelastweek"}),
    )
    never_online = first_available(
        find_path(stats, ("onlineStats", "neverOnline")),
        find_value(stats, {"neveronline", "neveronlineusers"}),
    )
    active_users = first_available(
        find_path(stats, ("users", "statusCounts", "active")),
        find_path(stats, ("users", "status", "active")),
        find_path(stats, ("users", "statuses", "active")),
        find_path(stats, ("users", "active")),
    )
    total_users = first_available(
        find_path(stats, ("users", "total")),
        find_value(stats, {"totalusers", "userscount"}),
    )
    total_online_on_nodes = find_value(
        stats,
        {"totalonlineonnodes", "nodesonlineusers", "onlineonnodes"},
    )

    embed = discord.Embed(
        title="Remnawave: активные пользователи",
        color=discord.Color.teal(),
    )
    embed.add_field(name="Онлайн сейчас", value=format_stat(online_now), inline=True)
    embed.add_field(name="Активные", value=format_stat(active_users), inline=True)
    embed.add_field(name="Всего пользователей", value=format_stat(total_users), inline=True)
    embed.add_field(name="За 24 часа", value=format_stat(last_day), inline=True)
    embed.add_field(name="За неделю", value=format_stat(last_week), inline=True)
    embed.add_field(name="Никогда онлайн", value=format_stat(never_online), inline=True)

    if total_online_on_nodes is not None:
        embed.add_field(
            name="Подключений на нодах",
            value=format_stat(total_online_on_nodes),
            inline=True,
        )

    embed.set_footer(text="Данные Remnawave могут обновляться с задержкой до 1 минуты.")
    return embed


class TicketCreateView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Создать тикет",
        style=discord.ButtonStyle.green,
        custom_id="ticket:create",
    )
    async def create_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Тикеты можно создавать только на сервере.",
                ephemeral=True,
            )
            return

        existing_ticket = await find_existing_ticket(interaction.guild, interaction.user)
        if existing_ticket:
            await interaction.response.send_message(
                f"У тебя уже есть открытый тикет: {existing_ticket.mention}",
                ephemeral=True,
            )
            return

        category = get_ticket_category(interaction.guild)
        if not bot_can_manage_channels(interaction.guild, category):
            await interaction.response.send_message(
                (
                    "Не могу создать тикет: у бота нет права `Manage Channels`"
                    " на сервере или в категории тикетов."
                ),
                ephemeral=True,
            )
            return

        support_role = interaction.guild.get_role(SUPPORT_ROLE_ID)
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            ),
        }

        if interaction.guild.me:
            overwrites[interaction.guild.me] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                read_message_history=True,
            )

        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
            )

        ticket_name = f"ticket-{interaction.user.name}".lower().replace(" ", "-")[:90]
        try:
            channel = await interaction.guild.create_text_channel(
                name=ticket_name,
                category=category,
                overwrites=overwrites,
                topic=f"ticket_owner:{interaction.user.id}",
                reason=f"Ticket created by {interaction.user}",
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                (
                    "Discord запретил создать канал тикета. Проверь, что у роли бота есть"
                    " `Manage Channels`, `View Channels`, `Send Messages`, `Embed Links`"
                    " и что категория тикетов не запрещает эти права."
                ),
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="Тикет поддержки",
            description=(
                f"{interaction.user.mention}, опиши свою проблему как можно подробнее.\n"
                "Команда поддержки скоро ответит."
            ),
            color=discord.Color.green(),
        )
        embed.set_footer(text="Закрыть тикет можно кнопкой ниже.")

        await channel.send(
            content=support_role.mention if support_role else None,
            embed=embed,
            view=TicketCloseView(),
            allowed_mentions=discord.AllowedMentions(roles=True),
        )
        await interaction.response.send_message(
            f"Тикет создан: {channel.mention}",
            ephemeral=True,
        )


class TicketCloseView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Закрыть тикет",
        style=discord.ButtonStyle.red,
        custom_id="ticket:close",
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if not interaction.channel or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                "Эту кнопку можно использовать только в канале тикета.",
                ephemeral=True,
            )
            return

        if not interaction.channel.topic or "ticket_owner:" not in interaction.channel.topic:
            await interaction.response.send_message(
                "Этот канал не похож на тикет.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message("Тикет закроется через 5 секунд.")
        await asyncio.sleep(5)
        await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")


@bot.event
async def setup_hook() -> None:
    logger.info("Starting ticket bot version %s", BOT_VERSION)

    bot.add_view(TicketCreateView())
    bot.add_view(TicketCloseView())
    logger.info("Persistent ticket views registered")

    guild = discord.Object(id=GUILD_ID)
    local_commands = bot.tree.get_commands(guild=guild)
    local_command_names = ", ".join(command.name for command in local_commands)
    logger.info(
        "Starting slash command sync for guild %s. Local commands: %s",
        GUILD_ID,
        local_command_names or "none",
    )

    try:
        synced_commands = await asyncio.wait_for(
            bot.tree.sync(guild=guild),
            timeout=COMMAND_SYNC_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.exception(
            "Slash command sync timed out after %.0f seconds for guild %s",
            COMMAND_SYNC_TIMEOUT,
            GUILD_ID,
        )
        raise
    except discord.HTTPException:
        logger.exception("Discord rejected slash command sync for guild %s", GUILD_ID)
        raise

    command_names = ", ".join(command.name for command in synced_commands)
    logger.info(
        "Synced %s slash command(s) for guild %s: %s",
        len(synced_commands),
        GUILD_ID,
        command_names or "none",
    )


@bot.event
async def on_ready() -> None:
    logger.info("Logged in as %s (%s)", bot.user, bot.user.id)


@bot.tree.command(
    name="ticket-panel",
    description="Отправить панель создания тикетов.",
    guild=discord.Object(id=GUILD_ID),
)
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def ticket_panel(interaction: discord.Interaction) -> None:
    if not interaction.channel or not isinstance(interaction.channel, discord.abc.Messageable):
        await interaction.response.send_message(
            "Панель можно отправить только в текстовый канал сервера.",
            ephemeral=True,
        )
        return

    embed = discord.Embed(
        title="Поддержка",
        description="Нажми кнопку ниже, чтобы создать приватный тикет для связи с поддержкой.",
        color=discord.Color.blurple(),
    )
    await interaction.channel.send(embed=embed, view=TicketCreateView())
    await interaction.response.send_message(
        "Панель тикетов отправлена.",
        ephemeral=True,
    )


@ticket_panel.error
async def ticket_panel_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
) -> None:
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "Эту команду может использовать только администратор.",
            ephemeral=True,
        )
        return

    raise error


@bot.tree.command(
    name="remnawave-active",
    description="Показать активных и онлайн пользователей Remnawave.",
    guild=discord.Object(id=GUILD_ID),
)
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def remnawave_active(interaction: discord.Interaction) -> None:
    if not REMNAWAVE_BASE_URL or not REMNAWAVE_API_TOKEN:
        await interaction.response.send_message(
            (
                "Remnawave не настроен. Заполни `REMNAWAVE_BASE_URL`"
                " и `REMNAWAVE_API_TOKEN` в `.env`."
            ),
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True, thinking=True)

    try:
        stats = await fetch_remnawave_stats()
    except urllib.error.HTTPError as error:
        await interaction.followup.send(
            format_http_error(error),
            ephemeral=True,
        )
        return
    except urllib.error.URLError as error:
        await interaction.followup.send(
            f"Не удалось подключиться к Remnawave: `{error.reason}`",
            ephemeral=True,
        )
        return
    except (json.JSONDecodeError, RuntimeError) as error:
        await interaction.followup.send(
            f"Не удалось прочитать ответ Remnawave: `{error}`",
            ephemeral=True,
        )
        return

    await interaction.followup.send(embed=build_remnawave_embed(stats), ephemeral=True)


@remnawave_active.error
async def remnawave_active_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
) -> None:
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "Эту команду может использовать только администратор.",
            ephemeral=True,
        )
        return

    raise error


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing. Create .env from .env.example first.")

if not GUILD_ID:
    raise RuntimeError("GUILD_ID is missing. Add your Discord server ID to .env.")

if not SUPPORT_ROLE_ID:
    raise RuntimeError("SUPPORT_ROLE_ID is missing. Add support role ID to .env.")

bot.run(TOKEN)
