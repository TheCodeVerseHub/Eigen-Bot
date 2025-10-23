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

    @commands.hybrid_command(name='song', aliases=['sp', 'spotify'], description='Show what you are currently listening to on Spotify')
    async def song(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        """Display the current song/music that a user is listening to on Spotify or other music apps."""
        target_user = user or ctx.author
        
        # Ensure target_user is a Member (has activities attribute)
        if not isinstance(target_user, discord.Member):
            embed = discord.Embed(
                title="❌ Error",
                description="This command only works in servers, not in DMs.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Check all activities - be more comprehensive
        spotify_activity = None
        music_activity = None
        
        for activity in target_user.activities:
            # Check for Spotify specifically
            if isinstance(activity, discord.Spotify):
                spotify_activity = activity
                break
            # Check for any listening activity (including other music apps)
            elif activity.type == discord.ActivityType.listening:
                music_activity = activity
        
        if spotify_activity:
            # Create rich embed for Spotify
            embed = discord.Embed(
                title="🎵 Now Playing on Spotify",
                description=f"**{target_user.display_name}** is listening to:",
                color=0x1DB954  # Spotify green
            )
            
            # Song details
            embed.add_field(
                name="🎵 Track",
                value=f"**[{spotify_activity.title}]({spotify_activity.track_url})**",
                inline=False
            )
            
            embed.add_field(
                name="👨‍🎤 Artist(s)",
                value=", ".join(spotify_activity.artists),
                inline=True
            )
            
            embed.add_field(
                name="💿 Album",
                value=spotify_activity.album,
                inline=True
            )
            
            # Duration
            duration = spotify_activity.duration
            current = (discord.utils.utcnow() - spotify_activity.start).total_seconds()
            
            duration_str = f"{int(duration.total_seconds() // 60)}:{int(duration.total_seconds() % 60):02d}"
            current_str = f"{int(current // 60)}:{int(current % 60):02d}"
            
            # Progress bar
            progress = min(current / duration.total_seconds(), 1.0)
            bar_length = 20
            filled = int(bar_length * progress)
            bar = "━" * filled + "○" + "─" * (bar_length - filled - 1)
            
            embed.add_field(
                name="⏱️ Duration",
                value=f"`{current_str}` {bar} `{duration_str}`",
                inline=False
            )
            
            # Add album art if available
            if spotify_activity.album_cover_url:
                embed.set_thumbnail(url=spotify_activity.album_cover_url)
            
            embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
            
        elif music_activity:
            # Found other music activity (not Spotify)
            if True:
                # Generic music activity
                embed = discord.Embed(
                    title="🎵 Now Listening",
                    description=f"**{target_user.display_name}** is listening to:",
                    color=discord.Color.blurple()
                )
                
                embed.add_field(
                    name="Activity",
                    value=f"**{music_activity.name}**",
                    inline=False
                )
                
                # Use getattr to safely access optional attributes
                details = getattr(music_activity, 'details', None)
                if details:
                    embed.add_field(name="Details", value=details, inline=False)
                
                state = getattr(music_activity, 'state', None)
                if state:
                    embed.add_field(name="State", value=state, inline=False)
                
                embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        else:
            # No music activity found - show debug info
            if target_user == ctx.author:
                # Show what activities were detected
                activities_list = []
                for activity in target_user.activities:
                    activities_list.append(f"• **{activity.name}** (Type: {activity.type.name})")
                
                if activities_list:
                    debug_info = "\n".join(activities_list)
                    message = (
                        "❌ **No music activity detected!**\n\n"
                        f"**Your current activities:**\n{debug_info}\n\n"
                        "**Possible solutions:**\n"
                        "• Make sure you're listening to music on Spotify, Apple Music, YouTube Music, etc.\n"
                        "• Enable 'Display current activity' in Discord Settings → Activity Privacy\n"
                        "• Restart your Discord client\n"
                        "• Make sure the music app is connected to Discord (check User Settings → Connections)"
                    )
                else:
                    message = (
                        "❌ **You are not currently listening to any music!**\n\n"
                        "**To use this command:**\n"
                        "• Be listening to Spotify or another music app\n"
                        "• Enable 'Display current activity' in Discord Settings → Activity Privacy\n"
                        "• Have your Discord client open and showing your activity\n"
                        "• Connect your music app in Discord Settings → Connections (for Spotify)"
                    )
            else:
                message = (
                    f"❌ **{target_user.display_name} is not currently listening to any music!**\n\n"
                    "They must be listening to Spotify or another music app with activity status enabled."
                )
            
            embed = discord.Embed(
                title="🎵 No Music Playing",
                description=message,
                color=discord.Color.red()
            )
            embed.set_footer(text="Tip: Check Discord Settings → Activity Privacy → Display current activity")
        
        await ctx.send(embed=embed)


async def setup(bot):
    """Setup the misc cog."""
    config = bot.config
    await bot.add_cog(Misc(bot, config))
