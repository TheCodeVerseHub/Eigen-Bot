"""
Poker game cog (scaffold).
"""

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy.ext.asyncio import AsyncSession

from models import Bet
from utils.config import Config
from utils.economy_utils import EconomyUtils
from utils.helpers import EmbedBuilder, format_coins


class Poker(commands.Cog):
    """Poker game commands (basic scaffold)."""

    def __init__(self, bot: commands.Bot, config: Config):
        self.bot = bot
        self.config = config

    @commands.command(name='poker', aliases=['texas'])
    async def poker(self, ctx: commands.Context, bet: int):
        """Start a simple poker game (scaffold - not fully implemented)."""
        await ctx.send("Poker game is under development. Check back later!")

    @app_commands.command(name='poker', description='Start a poker game (under development)')
    @app_commands.describe(bet='Amount to bet (not used yet)')
    async def poker_slash(self, interaction: discord.Interaction, bet: int):
        """Slash command for poker."""
        await interaction.response.send_message("Poker game is under development. Check back later!")

    @commands.command(name='join_poker')
    async def join_poker(self, ctx: commands.Context):
        """Join a poker game (scaffold)."""
        await ctx.send("Poker joining is under development.")

    @app_commands.command(name='join_poker', description='Join a poker game (under development)')
    async def join_poker_slash(self, interaction: discord.Interaction):
        """Slash command for joining poker."""
        await interaction.response.send_message("Poker joining is under development.")


async def setup(bot):
    """Setup the poker cog."""
    config = bot.config
    await bot.add_cog(Poker(bot, config))
