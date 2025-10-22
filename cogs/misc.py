"""
Misc commands cog.
"""

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from models import User
from utils.config import Config
from utils.economy_utils import EconomyUtils
from utils.helpers import EmbedBuilder, format_coins, responsible_gaming_notice
from bot import Fun2OoshBot


class Misc(commands.Cog):
    """Miscellaneous commands."""

    def __init__(self, bot: Fun2OoshBot, config: Config):
        self.bot = bot
        self.config = config

    @commands.command(name='profile')
    async def profile(self, ctx: commands.Context, user: Optional[discord.User] = None):
        """Show user profile."""
        target = user or ctx.author

        async with self.bot.get_session() as session:
            wallet = await EconomyUtils.get_or_create_wallet(session, target.id)
            await session.commit()  # Ensure wallet is saved
            # Get user stats
            stmt = select(User).filter(User.id == target.id)
            result = await session.execute(stmt)
            user_obj = result.scalar_one_or_none()

        embed = EmbedBuilder.info_embed(f"{target.display_name}'s Profile", "")
        embed.add_field(name="Balance", value=format_coins(wallet.balance), inline=True)
        embed.add_field(name="Bank", value=format_coins(wallet.bank), inline=True)
        embed.add_field(name="Total Wagered", value=format_coins(user_obj.total_wagered if user_obj else 0), inline=True)
        embed.set_thumbnail(url=target.avatar.url if target.avatar else target.default_avatar.url)
        await ctx.send(embed=embed)

    @app_commands.command(name='profile', description='Show your profile or another user\'s profile')
    async def profile_slash(self, interaction: discord.Interaction, user: Optional[discord.User] = None):
        """Slash command for profile."""
        target = user or interaction.user

        async with self.bot.get_session() as session:
            wallet = await EconomyUtils.get_or_create_wallet(session, target.id)
            await session.commit()  # Ensure wallet is saved
            # Get user stats
            stmt = select(User).filter(User.id == target.id)
            result = await session.execute(stmt)
            user_obj = result.scalar_one_or_none()

        embed = EmbedBuilder.info_embed(f"{target.display_name}'s Profile", "")
        embed.add_field(name="Balance", value=format_coins(wallet.balance), inline=True)
        embed.add_field(name="Bank", value=format_coins(wallet.bank), inline=True)
        embed.add_field(name="Total Wagered", value=format_coins(user_obj.total_wagered if user_obj else 0), inline=True)
        embed.set_thumbnail(url=target.avatar.url if target.avatar else target.default_avatar.url)
        await interaction.response.send_message(embed=embed)

    @commands.command(name='commands')
    async def help_command(self, ctx: commands.Context):
        """Show help."""
        embed = EmbedBuilder.info_embed("Fun2Oosh Help", "A casino bot for Discord!")
        embed.add_field(name="Economy", value="^balance, ^work, ^daily, ^transfer", inline=False)
        embed.add_field(name="Games", value="^blackjack, ^roulette, ^slots", inline=False)
        embed.add_field(name="Responsible Gaming", value=responsible_gaming_notice(), inline=False)
        await ctx.send(embed=embed)

    @app_commands.command(name='help', description='Show help and available commands')
    async def help_slash(self, interaction: discord.Interaction):
        """Slash command for help."""
        embed = EmbedBuilder.info_embed("Fun2Oosh Help", "A casino bot for Discord!")
        embed.add_field(name="Economy", value="/balance, /leaderboard, /profile", inline=False)
        embed.add_field(name="Games", value="^blackjack, ^roulette, ^slots", inline=False)
        embed.add_field(name="Responsible Gaming", value=responsible_gaming_notice(), inline=False)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    """Setup the misc cog."""
    config = bot.config
    await bot.add_cog(Misc(bot, config))
