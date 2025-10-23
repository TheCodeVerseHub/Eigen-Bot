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
                "[Support Server](https://discord.gg/3xKFvKhuGR)"
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
