"""Logging setup and command usage/error logging helpers.

Configures a shared root logger (console + rotating file under `logs/`) and
provides small helpers/listeners to log every command invocation and error
with a consistent format: timestamp, user id, command name.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

command_logger = logging.getLogger("eigen.commands")


def setup_logging(log_level: str = "INFO") -> None:
    """Configure the root logger with console + rotating file output."""
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    file_handler = RotatingFileHandler(
        logs_dir / "bot.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    stream_handler = logging.StreamHandler()

    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[file_handler, stream_handler],
    )


def log_command_usage(user_id: int, command_name: str, guild_id: int | None) -> None:
    command_logger.info(
        f"command='{command_name}' user_id={user_id} guild_id={guild_id}"
    )


def log_command_error(
    user_id: int, command_name: str, guild_id: int | None, error: BaseException
) -> None:
    command_logger.error(
        f"command='{command_name}' user_id={user_id} guild_id={guild_id} error={error}"
    )


def register_command_logging(bot: commands.Bot) -> None:
    """Attach listeners that log every prefix/hybrid and slash command invocation."""

    @bot.listen("on_command_completion")
    async def _log_prefix_command(ctx: commands.Context) -> None:
        guild_id = ctx.guild.id if ctx.guild else None
        log_command_usage(ctx.author.id, ctx.command.qualified_name, guild_id)

    @bot.listen("on_app_command_completion")
    async def _log_app_command(
        interaction: discord.Interaction, command: app_commands.Command
    ) -> None:
        log_command_usage(
            interaction.user.id, command.qualified_name, interaction.guild_id
        )
