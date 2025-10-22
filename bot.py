"""
Main entry point for the fun2oosh Discord bot.

This bot implements a casino-style economy with various games and commands.
It uses discord.py for interactions, SQLAlchemy for async database operations,
and supports both slash commands and message commands.
"""

import asyncio
import logging
import os
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from models import Base
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
    """Main bot class for fun2oosh."""

    def __init__(self, config: Config):
        intents = discord.Intents.default()
        intents.members = True  # For member-related commands
        intents.message_content = True  # For message commands

        # Disable the built-in help_command so a custom help cog can register `f?help` and `/help`
        super().__init__(
            command_prefix='f?',
            intents=intents,
            help_command=None
        )

        self.config = config
        self.engine = create_async_engine(config.database_url, echo=False)
        self.async_session_maker = async_sessionmaker(
            self.engine, expire_on_commit=False
        )
        # Discover available cog modules from the cogs directory
        from pathlib import Path
        cogs_dir = Path(__file__).resolve().parent / 'cogs'
        self.available_cogs = []
        if cogs_dir.exists() and cogs_dir.is_dir():
            for p in sorted(cogs_dir.iterdir()):
                if p.suffix == '.py' and p.stem != '__init__':
                    self.available_cogs.append(p.stem)
        logger.info(f"Available cogs discovered: {self.available_cogs}")

    def get_session(self) -> AsyncSession:
        """Get a database session."""
        return self.async_session_maker()

    async def setup_hook(self) -> None:
        """Setup hook called before the bot starts."""
        # Create database tables
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Load core cogs
        core_cogs = [
            'cogs.economy',
            'cogs.misc',
            'cogs.admin',
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
            'cogs.election',
            'cogs.highlights',
            'cogs.whois_alias',
            'cogs.utility_extra',
        ]

        for ext in feature_cogs:
            try:
                await self.load_extension(ext)
                logger.info(f'Loaded {ext}')
            except Exception as e:
                logger.error(f'Failed to load {ext}: {e}')

        # Clear any existing commands and force fresh sync
        if self.config.guild_id:
            guild = discord.Object(id=self.config.guild_id)
            logger.info("Clearing existing slash commands for guild...")
            self.tree.clear_commands(guild=guild)
            logger.info("Cleared commands, now loading cogs...")
        else:
            self.tree.clear_commands(guild=None)
            logger.info("Cleared global commands, now loading cogs...")
        
        # Sync slash commands
        try:
            if self.config.guild_id:
                guild = discord.Object(id=self.config.guild_id)
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                logger.info(f"Synced slash commands to guild {self.config.guild_id}")
            else:
                await self.tree.sync()
                logger.info("Synced slash commands globally")
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}")

        logger.info(f"Registered slash commands: {[cmd.name for cmd in self.tree.get_commands()]}")

    async def on_ready(self):
        """Called when the bot is ready."""
        if self.user:
            logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        else:
            logger.info('Bot logged in but user is None')
        logger.info(f'Connected to {len(self.guilds)} guilds')

        # Set presence
        await self.change_presence(
            activity=discord.Game(name="Eigen Bot | f?help")
        )

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Handle command errors."""
        # Silence unknown/prefix-not-found commands
        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"This command is on cooldown. Try again in {error.retry_after:.2f} seconds.")
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have permission to use this command.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("Invalid argument provided.")
        else:
            logger.error(f"Command error: {error}")
            await ctx.send("An error occurred while processing your command.")

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle slash command errors."""
        # Silence unknown slash/app commands
        # app_commands doesn't expose a simple CommandNotFound class in some versions, so be conservative
        try:
            from discord import app_commands as _appc
            # In later versions, AppCommandError subclasses may exist; ignore generic NotFound-like errors
        except Exception:
            _appc = None

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
