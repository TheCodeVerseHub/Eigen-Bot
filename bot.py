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
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
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
            command_prefix='?',
            intents=intents,
            help_command=None,
            # SECURITY: Prevent mass-mention exploits caused by echoing user content.
            # Even if the bot has Administrator / Mention Everyone, this blocks @everyone/@here and role pings.
            allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True, replied_user=False),
        )

        self.start_time = discord.utils.utcnow()
        self.config = config
        # Discover available cog modules from the cogs directory
        from pathlib import Path
        cogs_dir = Path(__file__).resolve().parent / 'cogs'
        self.available_cogs = []
        if cogs_dir.exists() and cogs_dir.is_dir():
            for p in sorted(cogs_dir.iterdir()):
                if p.suffix == '.py' and p.stem != '__init__':
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

        # Load core cogs
        core_cogs = [
            'cogs.misc',
            'cogs.admin',
            'cogs.tickets',
        ]

        for ext in core_cogs:
            try:
                await self.load_extension(ext)
                logger.info(f'Loaded {ext}')
            except Exception as e:
                logger.error(f'Failed to load {ext}: {e}')

        # Load feature cogs (new/renamed)
        feature_cogs = [
            'cogs.tags',
            'cogs.fun',
            'cogs.starboard',
            'cogs.help',
            'cogs.community',
            'cogs.utility_extra',
            'cogs.afk',
            'cogs.birthday',
            'cogs.bump_leaderboard',
            'cogs.suggestions',
            'cogs.codebuddy_quiz',
            'cogs.codebuddy_leaderboard',
            'cogs.codebuddy_help',
            'cogs.counting',
            'cogs.tod',
            'cogs.daily_quests',
            'cogs.staff_applications',
            'cogs.tts',
            'cogs.chowkidar'
        ]

        for ext in feature_cogs:
            try:
                await self.load_extension(ext)
                logger.info(f'Loaded {ext}')
            except Exception as e:
                logger.error(f'Failed to load {ext}: {e}')

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

                    logger.info(f"✅ Synced {len(synced)} slash commands to guild {guild_id}")
                    logger.info(f"📊 Guild Command Slots: {len(synced)}/100 used ({100 - len(synced)} remaining)")

                    command_names = [cmd.name for cmd in synced]
                    logger.info(f"📝 Synced commands for {guild_id}: {', '.join(command_names)}")
            else:
                synced = await self.tree.sync()
                logger.info(f"✅ Synced {len(synced)} slash commands globally")
                logger.info(f"📊 Global Command Slots: {len(synced)}/100 used ({100 - len(synced)} remaining)")

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
            logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        else:
            logger.info('Bot logged in but user is None')
        logger.info(f'Connected to {len(self.guilds)} guilds')

        # Set presence
        await self.change_presence(
            activity=discord.Game(name="?helpmenu | Made by YC45")
        )

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Handle command errors."""
        # Silence unknown/prefix-not-found commands
        if isinstance(error, commands.CommandNotFound):
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
                except (discord.NotFound, discord.HTTPException, discord.Forbidden, RuntimeError):
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
            await _safe_ctx_send(f"This command is on cooldown. Try again in {error.retry_after:.2f} seconds.")
        elif isinstance(error, commands.MissingPermissions):
            await _safe_ctx_send("You don't have permission to use this command.")
        elif isinstance(error, commands.BadArgument):
            await _safe_ctx_send("Invalid argument provided.")
        else:
            logger.error(f"Command error: {error}")
            await _safe_ctx_send("An error occurred while processing your command.")

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle slash command errors."""
        # Silence unknown slash/app commands.
        # `app_commands` doesn't expose a stable CommandNotFound across versions, so be conservative.

        # If it's a cooldown, inform user
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"This command is on cooldown. Try again in {error.retry_after:.2f} seconds.",
                ephemeral=True
            )
        else:
            # For other app command errors, log and try to respond once
            logger.error(f"Slash command error: {error}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "An error occurred while processing your command.",
                        ephemeral=True
                    )
            except Exception:
                # If sending fails, silently ignore to avoid noisy errors for unknown commands
                return

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
        logger.info("Bot shutdown requested.")
    except Exception as e:
        logger.error(f"Bot encountered an error: {e}")
    finally:
        await bot.close()

if __name__ == '__main__':
    asyncio.run(main())
