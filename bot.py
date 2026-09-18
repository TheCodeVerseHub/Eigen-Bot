"""
Main entry point for the Eigen Discord bot.

This bot provides various utilities and features for Discord servers.
It uses discord.py for interactions and supports both slash commands and message commands.
"""

import asyncio
import logging
import os

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from utils.config import Config

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class Fun2OoshBot(commands.Bot):
    """Main bot class for Eigen Bot."""

    def __init__(self, config: Config):
        intents = discord.Intents.default()
        intents.members = True  # For member-related commands
        intents.message_content = True  # For message commands
        intents.presences = True  # For seeing user activities (Spotify, games, etc.)
        intents.voice_states = True  # For join/leave voice channel features

        # Disable the built-in help_command so a custom help cog can register `?helpmenu` and `/help`
        super().__init__(
            command_prefix="?",
            intents=intents,
            help_command=None,
            # SECURITY: Prevent mass-mention exploits caused by echoing user content.
            # Even if the bot has Administrator / Mention Everyone, this blocks @everyone/@here and role pings.
            allowed_mentions=discord.AllowedMentions(
                everyone=False, roles=False, users=True, replied_user=False
            ),
        )

        self.start_time = discord.utils.utcnow()
        self.config = config
        self.loaded_cogs: list[str] = []
        self.failed_cogs: list[tuple[str, str]] = []  # (cog_name, error_message)
        # Discover available cog modules from the cogs directory
        from pathlib import Path

        cogs_dir = Path(__file__).resolve().parent / "cogs"
        self.available_cogs = []
        if cogs_dir.exists() and cogs_dir.is_dir():
            for p in sorted(cogs_dir.iterdir()):
                if p.suffix == ".py" and p.stem != "__init__":
                    self.available_cogs.append(p.stem)
        logger.info(f"Available cogs discovered: {self.available_cogs}")

    async def setup_hook(self) -> None:
        """Setup hook called before the bot starts."""
        # Initialize CodeBuddy database
        try:
            from utils.codebuddy_database import init_db

            await init_db()
            logger.info("Initialized CodeBuddy database")
        except Exception as e:
            logger.error(f"Failed to initialize CodeBuddy database: {e}")

        # Load core cogs (required — abort startup if any fail)
        required_cogs = [
            "cogs.misc",
            "cogs.admin",
            "cogs.tickets",
        ]

        for ext in required_cogs:
            try:
                await self.load_extension(ext)
                logger.info(f"Loaded {ext}")
                self.loaded_cogs.append(ext)
            except Exception as e:
                logger.critical(f"Required cog {ext} failed to load: {e}")
                self.failed_cogs.append((ext, str(e)))
                raise RuntimeError(f"Required cog {ext} failed to load: {e}") from e

        # Load feature cogs (new/renamed)
        feature_cogs = [
            "cogs.tags",
            "cogs.fun",
            "cogs.starboard",
            "cogs.help",
            "cogs.community",
            "cogs.utility_extra",
            "cogs.afk",
            "cogs.birthday",
            "cogs.bump_leaderboard",
            "cogs.suggestions",
            "cogs.codebuddy_quiz",
            "cogs.codebuddy_leaderboard",
            "cogs.codebuddy_help",
            "cogs.counting",
            "cogs.tod",
            "cogs.daily_quests",
            "cogs.staff_applications",
            "cogs.tts",
            "cogs.chowkidar",
            "cogs.staff_guide",
        ]

        for ext in feature_cogs:
            try:
                await self.load_extension(ext)
                logger.info(f"Loaded {ext}")
                self.loaded_cogs.append(ext)
            except Exception as e:
                logger.error(f"Failed to load {ext}: {e}")
                self.failed_cogs.append((ext, str(e)))

        # Load modmail cog
        # try:
        #     await self.load_extension('cogs.modmail')
        #     logger.info('Loaded cogs.modmail')
        # except Exception as e:
        #     logger.error(f'Failed to load cogs.modmail: {e}')

        # Sync slash commands
        try:
            if self.config.guild_ids:
                for guild_id in self.config.guild_ids:
                    guild = discord.Object(id=guild_id)
                    # Ensure guild command set reflects the current global command set
                    self.tree.clear_commands(guild=guild)
                    self.tree.copy_global_to(guild=guild)
                    synced = await self.tree.sync(guild=guild)

                    logger.info(
                        f"✅ Synced {len(synced)} slash commands to guild {guild_id}"
                    )
                    logger.info(
                        f"📊 Guild Command Slots: {len(synced)}/100 used ({100 - len(synced)} remaining)"
                    )

                    command_names = [cmd.name for cmd in synced]
                    logger.info(
                        f"📝 Synced commands for {guild_id}: {', '.join(command_names)}"
                    )
            else:
                synced = await self.tree.sync()
                logger.info(f"✅ Synced {len(synced)} slash commands globally")
                logger.info(
                    f"📊 Global Command Slots: {len(synced)}/100 used ({100 - len(synced)} remaining)"
                )

                command_names = [cmd.name for cmd in synced]
                logger.info(f"📝 Synced commands: {', '.join(command_names)}")

        except Exception as e:
            logger.error(f"❌ Failed to sync slash commands: {e}")

        # Also log commands from the tree
        tree_commands = self.tree.get_commands()
        logger.info(f"🌲 Command tree contains {len(tree_commands)} commands")

    async def on_ready(self):
        """Called when the bot is ready."""
        if self.user:
            logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        else:
            logger.info("Bot logged in but user is None")
        logger.info(f"Connected to {len(self.guilds)} guilds")

        # Set presence
        await self.change_presence(
            activity=discord.Game(name="?helpmenu /help | Made by YC45")
        )

    async def on_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ):
        """Handle command errors."""
        # Silence unknown/prefix-not-found commands
        if isinstance(error, commands.CommandNotFound):
            return

        # If a command/cog-level error handler (e.g. `cog_command_error`)
        # already handled the error, don't send a generic message on top.
        command = ctx.command
        if command is not None:
            if command.has_error_handler():
                return
            cog = command.cog
            if cog is not None and cog.has_error_handler():
                return

        async def _safe_ctx_send(message: str) -> None:
            """Send a message without crashing on expired slash interactions.

            Hybrid commands may have `ctx.interaction` set. If the interaction has expired,
            discord will raise `Unknown interaction (10062)` when trying to respond.
            """
            interaction = getattr(ctx, "interaction", None)
            if interaction is not None:
                try:
                    is_expired = getattr(interaction, "is_expired", None)
                    if callable(is_expired) and interaction.is_expired():
                        raise RuntimeError("interaction expired")

                    if not interaction.response.is_done():
                        await interaction.response.send_message(message, ephemeral=True)
                        return
                    await interaction.followup.send(message, ephemeral=True)
                    return
                except (
                    discord.NotFound,
                    discord.HTTPException,
                    discord.Forbidden,
                    RuntimeError,
                ):
                    # Fall back to a normal channel send.
                    pass
                except Exception:
                    pass

            try:
                if ctx.channel is not None:
                    await ctx.channel.send(message)
            except Exception:
                return

        if isinstance(error, commands.CommandOnCooldown):
            await _safe_ctx_send(
                f"This command is on cooldown. Try again in {error.retry_after:.2f} seconds."
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            command = getattr(ctx, "command", None)
            cog = getattr(command, "cog", None)
            if command and command.qualified_name == "resources" and cog is not None:
                send_usage = getattr(cog, "_send_resource_usage", None)
                if callable(send_usage):
                    await send_usage(ctx)
                    return
            usage = f"?{command.qualified_name} {command.signature}".strip()
            await _safe_ctx_send(f"Missing required input. Usage: `{usage}`")
        elif isinstance(error, commands.MissingPermissions):
            permissions = ", ".join(permission.replace("_", " ") for permission in error.missing_permissions)
            await _safe_ctx_send(f"You need the following permission(s): {permissions}.")
        elif isinstance(error, commands.BotMissingPermissions):
            permissions = ", ".join(permission.replace("_", " ") for permission in error.missing_permissions)
            await _safe_ctx_send(f"I need the following permission(s): {permissions}.")
        elif isinstance(error, commands.NoPrivateMessage):
            await _safe_ctx_send("This command can only be used in a server.")
        elif isinstance(error, commands.DisabledCommand):
            await _safe_ctx_send("This command is currently disabled.")
        elif isinstance(error, commands.MaxConcurrencyReached):
            await _safe_ctx_send("This command is already running. Please wait for it to finish.")
        elif isinstance(error, commands.CheckFailure):
            await _safe_ctx_send("You cannot use this command here or do not meet its requirements.")
        elif isinstance(error, commands.BadArgument):
            usage = f"?{command.qualified_name} {command.signature}".strip()
            await _safe_ctx_send(f"Invalid input. Usage: `{usage}`")
        elif isinstance(error, commands.CommandInvokeError):
            if isinstance(error.original, discord.Forbidden):
                await _safe_ctx_send(
                    "I don't have permission to complete that action in this channel."
                )
            elif isinstance(error.original, discord.HTTPException):
                await _safe_ctx_send(
                    "Discord could not process that request. Please try again shortly."
                )
            else:
                logger.exception("Command failed", exc_info=error.original)
                await _safe_ctx_send(
                    "Something went wrong while running that command. Please try again later."
                )
        else:
            logger.exception("Unhandled command error", exc_info=error)
            await _safe_ctx_send(
                "Something went wrong while running that command. Please try again later."
            )

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """Handle slash command errors."""
        # Silence unknown slash/app commands.
        # `app_commands` doesn't expose a stable CommandNotFound across versions, so be conservative.

        async def _safe_interaction_send(message: str) -> None:
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(message, ephemeral=True)
                else:
                    await interaction.response.send_message(message, ephemeral=True)
            except (discord.Forbidden, discord.HTTPException):
                return

        # If it's a cooldown, inform user
        if isinstance(error, app_commands.CommandOnCooldown):
            await _safe_interaction_send(
                f"This command is on cooldown. Try again in {error.retry_after:.2f} seconds.",
            )
        elif isinstance(error, app_commands.MissingPermissions):
            permissions = ", ".join(permission.replace("_", " ") for permission in error.missing_permissions)
            await _safe_interaction_send(
                f"You need the following permission(s): {permissions}."
            )
        elif isinstance(error, app_commands.BotMissingPermissions):
            permissions = ", ".join(permission.replace("_", " ") for permission in error.missing_permissions)
            await _safe_interaction_send(
                f"I need the following permission(s): {permissions}."
            )
        elif isinstance(error, app_commands.TransformerError):
            await _safe_interaction_send("Invalid input. Please check the command options and try again.")
        elif isinstance(error, app_commands.CheckFailure):
            await _safe_interaction_send(
                "You cannot use this command here or do not meet its requirements."
            )
        elif isinstance(error, app_commands.CommandInvokeError):
            if isinstance(error.original, discord.Forbidden):
                await _safe_interaction_send(
                    "I don't have permission to complete that action in this channel."
                )
            elif isinstance(error.original, discord.HTTPException):
                await _safe_interaction_send(
                    "Discord could not process that request. Please try again shortly."
                )
            else:
                logger.exception("Slash command failed", exc_info=error.original)
                await _safe_interaction_send(
                    "Something went wrong while running that command. Please try again later."
                )
        else:
            logger.exception("Unhandled slash command error", exc_info=error)
            await _safe_interaction_send(
                "Something went wrong while running that command. Please try again later."
            )


    # ── Owner-only health command ──────────────────────────────────────
    @commands.command(name="health", hidden=True)  # type: ignore[type-var]
    async def health_command(self, ctx: commands.Context):
        """Show bot health summary (bot owner only)."""
        if self.config.owner_id is not None and ctx.author.id != self.config.owner_id:
            return

        total = len(self.loaded_cogs) + len(self.failed_cogs)
        loaded = len(self.loaded_cogs)
        failed = len(self.failed_cogs)

        embed = discord.Embed(
            title="Bot Health",
            color=discord.Color.green() if failed == 0 else discord.Color.orange(),
        )
        embed.add_field(name="Cogs Loaded", value=str(loaded), inline=True)
        embed.add_field(name="Cogs Failed", value=str(failed), inline=True)
        embed.add_field(name="Total Discovered", value=str(total), inline=True)

        latency_ms = round(self.latency * 1000)
        embed.add_field(name="Latency", value=f"{latency_ms}ms", inline=True)
        embed.add_field(name="Guilds", value=str(len(self.guilds)), inline=True)
        embed.add_field(
            name="Uptime",
            value=discord.utils.format_dt(self.start_time, "R"),
            inline=True,
        )

        if self.failed_cogs:
            lines = [f"• `{name}` — {err[:80]}" for name, err in self.failed_cogs]
            embed.add_field(
                name="Failed Cogs",
                value="\n".join(lines),
                inline=False,
            )

        await ctx.send(embed=embed)


async def main():
    """Main function to run the bot."""
    config = Config()

    if not config.discord_token:
        logger.error("DISCORD_TOKEN not found in environment variables.")
        return

    bot = Fun2OoshBot(config)

    try:
        await bot.start(config.discord_token)
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested (KeyboardInterrupt).")
    except asyncio.CancelledError:
        # Occurs during event loop cancellation / shutdown sequences (e.g. Ctrl-C)
        logger.info(
            "Bot start cancelled (asyncio.CancelledError). Shutting down gracefully."
        )
    except Exception as e:
        logger.error(f"Bot encountered an error: {e}")
    finally:
        await bot.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, asyncio.CancelledError):
        # Graceful shutdown requested (Ctrl-C or event loop cancellation).
        logger.info("Shutdown requested; exiting.")
