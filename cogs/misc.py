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

    @commands.hybrid_command(name='about', description='Learn about Eigen Bot')
    async def about(self, ctx: commands.Context):
        """Show information about the bot."""
        embed = discord.Embed(
            title="📚 About Eigen Bot",
            description=(
                "**Eigen Bot** is a feature-rich, production-ready Discord bot that brings together "
                "economy systems, casino games, community engagement, and utility features.\n\n"
                "Built with ❤️ using discord.py and modern async architecture."
            ),
            color=discord.Color.blue()
        )
        
        # Add bot stats
        total_guilds = len(self.bot.guilds)
        total_users = sum(guild.member_count or 0 for guild in self.bot.guilds)
        total_commands = len(self.bot.tree.get_commands())
        
        embed.add_field(
            name="📊 Statistics",
            value=(
                f"🏰 Servers: **{total_guilds}**\n"
                f"👥 Users: **{total_users:,}**\n"
                f"⚡ Commands: **{total_commands}**"
            ),
            inline=True
        )
        
        embed.add_field(
            name="🎯 Features",
            value=(
                "💰 Economy System\n"
                "🎰 Casino Games\n"
                "⭐ Starboard\n"
                "🏷️ Custom Tags\n"
                "🗳️ Elections\n"
                "📊 Invite Tracker\n"
                "🎰 Casino Games\n"
                "🎭 Fun Commands\n"
                "🛠️ Utilities"
            ),
            inline=True
        )
        
        embed.add_field(
            name="🔗 Links",
            value=(
                "[GitHub](https://github.com/TheCodeVerseHub/Eigen-Bot) • "
                "[Invite Bot](https://discord.com/api/oauth2/authorize) • "
                "[Support](https://discord.gg/your-server)"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💡 Getting Started",
            value=(
                "Use `f?help` or `/help` to see all available commands!\n"
                "Most commands work with both `f?` prefix and `/` slash commands."
            ),
            inline=False
        )
        
        # Add version and tech info
        embed.set_footer(
            text=f"Python {discord.__version__} • Made by TheCodeVerseHub",
            icon_url=self.bot.user.avatar.url if self.bot.user and self.bot.user.avatar else None
        )
        
        # Set bot thumbnail
        if self.bot.user and self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)
        
        await ctx.send(embed=embed)


async def setup(bot):
    """Setup the misc cog."""
    config = bot.config
    await bot.add_cog(Misc(bot, config))
