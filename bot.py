import asyncio
import os
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv


load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
SUPPORT_ROLE_ID = int(os.getenv("SUPPORT_ROLE_ID", "0"))
TICKET_CATEGORY_ID = os.getenv("TICKET_CATEGORY_ID")


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


async def find_existing_ticket(guild: discord.Guild, user: discord.Member) -> Optional[discord.TextChannel]:
    topic_marker = f"ticket_owner:{user.id}"

    for channel in guild.text_channels:
        if channel.topic and topic_marker in channel.topic:
            return channel

    return None


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

        support_role = interaction.guild.get_role(SUPPORT_ROLE_ID)
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            ),
            interaction.guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                read_message_history=True,
            ),
        }

        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
            )

        ticket_name = f"ticket-{interaction.user.name}".lower().replace(" ", "-")[:90]
        category = get_ticket_category(interaction.guild)
        channel = await interaction.guild.create_text_channel(
            name=ticket_name,
            category=category,
            overwrites=overwrites,
            topic=f"ticket_owner:{interaction.user.id}",
            reason=f"Ticket created by {interaction.user}",
        )

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
    bot.add_view(TicketCreateView())
    bot.add_view(TicketCloseView())

    guild = discord.Object(id=GUILD_ID)
    bot.tree.copy_global_to(guild=guild)
    synced_commands = await bot.tree.sync(guild=guild)
    print(f"Synced {len(synced_commands)} slash command(s) for guild {GUILD_ID}")


@bot.event
async def on_ready() -> None:
    print(f"Logged in as {bot.user} ({bot.user.id})")


@bot.tree.command(
    name="ticket-panel",
    description="Отправить панель создания тикетов.",
    guild=discord.Object(id=GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
async def ticket_panel(interaction: discord.Interaction) -> None:
    embed = discord.Embed(
        title="Поддержка",
        description="Нажми кнопку ниже, чтобы создать приватный тикет для связи с поддержкой.",
        color=discord.Color.blurple(),
    )
    await interaction.response.send_message(embed=embed, view=TicketCreateView())


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


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing. Create .env from .env.example first.")

if not GUILD_ID:
    raise RuntimeError("GUILD_ID is missing. Add your Discord server ID to .env.")

if not SUPPORT_ROLE_ID:
    raise RuntimeError("SUPPORT_ROLE_ID is missing. Add support role ID to .env.")

bot.run(TOKEN)
