"""
Starboard System - Track and display starred messages
Similar to Dyno bot functionality with self-starring allowed
"""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

from utils.helpers import create_error_embed, create_success_embed, create_warning_embed


class ReactionProxy:
    """Minimal reaction-like proxy used for raw events when message isn't cached."""
    def __init__(self, emoji: Any, message: discord.Message):
        self.emoji = emoji
        self.message = message

class StarboardSystem(commands.Cog):
    logger = logging.getLogger(__name__)
    @commands.hybrid_command(name="starboard_info", description="Show starboard usage tips and quick setup guide")
    async def starboard_info(self, ctx: commands.Context):
        """Show starboard usage tips and quick setup guide"""
        embed = discord.Embed(
            title="⭐ Modern Starboard System",
            description=(
                "**Transform popular messages into highlighted showcases!**\n\n"
                " **Visual Features:**\n"
                "• Dynamic colors based on star count (gold for 20+, red for 10+, teal for 5+)\n"
                "• Author thumbnails and clean message formatting\n"
                "• Smart attachment handling (images, videos, files)\n"
                "• Relative timestamps and jump links\n"
                "• Shows who starred and when\n\n"
                " **How it works:**\n"
                "• React with the star emoji (default: ⭐) on any message\n"
                "• When threshold is reached, message appears in starboard\n"
                "• Self-starring allowed by default\n"
                "• Real-time updates as more stars are added\n\n"
                " **Quick Setup:**\n"
                "`?starboard setup #starboard 3 ⭐`\n\n"
                " **Management Commands:**\n"
                "• `?starboard channel #channel` - Change starboard channel\n"
                "• `?starboard threshold 5` - Change star requirement\n"
                "• `?starboard emoji ` - Change star emoji\n"
                "• `?starboard stats` - View server statistics\n"
                "• `?starboard toggle` - Enable/disable system\n"
            ),
            color=0xFFD700  # Gold color
        )
        embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user and self.bot.user.avatar else None)
        embed.add_field(
            name=" Pro Tips",
            value=(
                "• Higher star counts get more vibrant colors\n"
                "• Images are displayed inline for better engagement\n"
                "• Message authors get visual recognition\n"
                "• Clean, mobile-friendly design"
            ),
            inline=False
        )
        embed.set_footer(text="Eigen Bot • Modern Discord Experience", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)
    """Starboard system for highlighting popular messages with star reactions"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.database_path = Path("data/starboard.db")
        self.star_cache: dict[int, dict] = {}  # Cache for quick lookups
        # Locks to prevent race conditions creating duplicate starboard posts
        self._locks: dict[int, asyncio.Lock] = {}
        self.ready = False
        
    async def cog_load(self):
        """Initialize the starboard system when the cog loads"""
        await self.init_database()
        await self.load_starboard_cache()
        self.ready = True
        
    async def init_database(self):
        """Initialize the starboard database"""
        # Ensure data directory exists
        self.database_path.parent.mkdir(exist_ok=True)
        
        async with aiosqlite.connect(self.database_path) as db:
            # Starboard settings table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS starboard_settings (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER,
                    threshold INTEGER DEFAULT 3,
                    star_emoji TEXT DEFAULT '⭐',
                    enabled BOOLEAN DEFAULT 1,
                    self_star BOOLEAN DEFAULT 1,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Starred messages table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS starred_messages (
                    message_id INTEGER PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    author_id INTEGER NOT NULL,
                    starboard_message_id INTEGER,
                    star_count INTEGER DEFAULT 0,
                    content TEXT,
                    attachments TEXT,
                    created_at TEXT NOT NULL,
                    last_updated TEXT NOT NULL
                )
            """)
            
            # Individual stars table (to track who starred what)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_stars (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    starred_at TEXT NOT NULL,
                    UNIQUE(message_id, user_id)
                )
            """)
            
            await db.commit()
            
    async def load_starboard_cache(self):
        """Load starboard settings into cache for quick access"""
        async with aiosqlite.connect(self.database_path) as db:
            cursor = await db.execute("SELECT guild_id, channel_id, threshold, star_emoji, enabled, self_star FROM starboard_settings")
            rows = await cursor.fetchall()
            
            for row in rows:
                guild_id, channel_id, threshold, star_emoji, enabled, self_star = row
                self.star_cache[guild_id] = {
                    'channel_id': channel_id,
                    'threshold': threshold,
                    'star_emoji': star_emoji,
                    'enabled': bool(enabled),
                    'self_star': bool(self_star)
                }
                
    async def get_starboard_settings(self, guild_id: int) -> dict | None:
        """Get starboard settings for a guild"""
        # Check cache first
        if guild_id in self.star_cache:
            return self.star_cache[guild_id]
        
        # If not in cache, load from database
        async with aiosqlite.connect(self.database_path) as db:
            cursor = await db.execute(
                "SELECT channel_id, threshold, star_emoji, enabled, self_star FROM starboard_settings WHERE guild_id = ?",
                (guild_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                settings = {
                    'channel_id': row[0],
                    'threshold': row[1],
                    'star_emoji': row[2],
                    'enabled': bool(row[3]),
                    'self_star': bool(row[4])
                }
                # Update cache
                self.star_cache[guild_id] = settings
                return settings
        
        return None
        
    async def update_starboard_settings(self, guild_id: int, **kwargs):
        """Update starboard settings for a guild"""
        current_time = datetime.now(timezone.utc).isoformat()
        
        async with aiosqlite.connect(self.database_path) as db:
            # Check if settings exist
            cursor = await db.execute("SELECT guild_id FROM starboard_settings WHERE guild_id = ?", (guild_id,))
            exists = await cursor.fetchone()
            
            if exists:
                # Update existing settings
                set_clauses = []
                values = []
                for key, value in kwargs.items():
                    if key in ['channel_id', 'threshold', 'star_emoji', 'enabled', 'self_star']:
                        set_clauses.append(f"{key} = ?")
                        values.append(value)
                
                if set_clauses:
                    allowed_keys = {
                        "channel_id",
                        "threshold",
                        "star_emoji",
                        "enabled",
                        "self_star",
                    }
                    if all(clause.split(" = ?", 1)[0] in allowed_keys for clause in set_clauses):
                        query = "UPDATE starboard_settings SET " + ", ".join(set_clauses)
                        query += " WHERE guild_id = ?"
                        values.append(guild_id)
                        await db.execute(query, values)
            else:
                # Create new settings
                await db.execute("""
                    INSERT INTO starboard_settings (guild_id, channel_id, threshold, star_emoji, enabled, self_star, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    guild_id,
                    kwargs.get('channel_id'),
                    kwargs.get('threshold', 3),
                    kwargs.get('star_emoji', '⭐'),
                    kwargs.get('enabled', True),
                    kwargs.get('self_star', True),
                    current_time
                ))
            
            await db.commit()
            
        # Update cache
        if guild_id not in self.star_cache:
            self.star_cache[guild_id] = {}
        self.star_cache[guild_id].update(kwargs)

    @commands.hybrid_group(name="starboard", description="Starboard system management")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def starboard(self, ctx: commands.Context):
        """Starboard system management commands"""
        if ctx.invoked_subcommand is None:
            await self.show_starboard_status(ctx)
    
    @starboard.command(name="setup", description="Setup starboard for the server")
    @app_commands.describe(
        channel="Channel where starred messages will be posted",
        threshold="Number of stars required (default: 3)",
        emoji="Star emoji to use (default: ⭐)"
    )
    @commands.has_permissions(manage_guild=True)
    async def starboard_setup(self, ctx: commands.Context, channel: discord.TextChannel, 
                            threshold: int = 3, emoji: str = "⭐"):
        """Setup starboard system for the server"""
        if not ctx.guild:
            await ctx.send(embed=create_error_embed("Error", "This command can only be used in a server."))
            return
            
        # Validate threshold
        if threshold < 1 or threshold > 50:
            await ctx.send(embed=create_error_embed("Invalid Threshold", "Threshold must be between 1 and 50."))
            return
            
        # Validate emoji
        if len(emoji) > 10:
            await ctx.send(embed=create_error_embed("Invalid Emoji", "Emoji must be 10 characters or less."))
            return
            
        # Check bot permissions in starboard channel
        if self.bot.user is None:
            await ctx.send(embed=create_error_embed("Error", "Bot is not fully initialized yet."))
            return
            
        bot_member = ctx.guild.get_member(self.bot.user.id)
        if not bot_member:
            await ctx.send(embed=create_error_embed("Error", "Could not find bot member in guild."))
            return
            
        permissions = channel.permissions_for(bot_member)
        if not (permissions.send_messages and permissions.embed_links):
            await ctx.send(embed=create_error_embed(
                "Insufficient Permissions",
                f"I need **Send Messages** and **Embed Links** permissions in {channel.mention}"
            ))
            return
            
        # Update settings
        await self.update_starboard_settings(
            ctx.guild.id,
            channel_id=channel.id,
            threshold=threshold,
            star_emoji=emoji,
            enabled=True,
            self_star=True
        )
        
        embed = create_success_embed(
            " Starboard Setup Complete!",
            "Your modern starboard system is now active and ready to showcase your community's best messages!"
        )
        embed.color = 0x00FF7F  # Spring green
        embed.add_field(name=" Channel", value=channel.mention, inline=True)
        embed.add_field(name=" Threshold", value=f"{threshold} {emoji}", inline=True)
        embed.add_field(name=" Star Emoji", value=emoji, inline=True)
        embed.add_field(name=" Self-starring", value="Allowed", inline=True)
        embed.add_field(name=" Status", value="🟢 Active", inline=True)
        embed.add_field(name=" Features", value="Dynamic colors, thumbnails, smart formatting", inline=True)
        embed.add_field(
            name=" Next Steps",
            value=f"Start starring messages with {emoji} reactions!\nUse `?starboard stats` to track activity.",
            inline=False
        )
        embed.set_footer(text=" Your starboard will get more beautiful as messages get more stars!")
        
        await ctx.send(embed=embed)
        
    @starboard.command(name="channel", description="Set the starboard channel")
    @app_commands.describe(channel="Channel where starred messages will be posted")
    @commands.has_permissions(manage_guild=True)
    async def starboard_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set the starboard channel"""
        if not ctx.guild:
            return
            
        settings = await self.get_starboard_settings(ctx.guild.id)
        if not settings:
            await ctx.send(embed=create_error_embed(
                "Starboard Not Setup",
                "Please run `/starboard setup` first to configure the starboard system."
            ))
            return
            
        await self.update_starboard_settings(ctx.guild.id, channel_id=channel.id)
        
        embed = create_success_embed("Channel Updated", f"Starboard channel set to {channel.mention}")
        await ctx.send(embed=embed)
        
    @starboard.command(name="threshold", description="Set the star threshold")
    @app_commands.describe(threshold="Number of stars required (1-50)")
    @commands.has_permissions(manage_guild=True)
    async def starboard_threshold(self, ctx: commands.Context, threshold: int):
        """Set the star threshold"""
        if not ctx.guild:
            return
            
        if threshold < 1 or threshold > 50:
            await ctx.send(embed=create_error_embed("Invalid Threshold", "Threshold must be between 1 and 50."))
            return
            
        settings = await self.get_starboard_settings(ctx.guild.id)
        if not settings:
            await ctx.send(embed=create_error_embed(
                "Starboard Not Setup",
                "Please run `/starboard setup` first to configure the starboard system."
            ))
            return
            
        await self.update_starboard_settings(ctx.guild.id, threshold=threshold)
        
        embed = create_success_embed("Threshold Updated", f"Star threshold set to **{threshold}** stars")
        await ctx.send(embed=embed)
        
    @starboard.command(name="emoji", description="Set the star emoji")
    @app_commands.describe(emoji="Emoji to use for starring (⭐, , etc.)")
    @commands.has_permissions(manage_guild=True)
    async def starboard_emoji(self, ctx: commands.Context, emoji: str):
        """Set the star emoji"""
        if not ctx.guild:
            return
            
        if len(emoji) > 10:
            await ctx.send(embed=create_error_embed("Invalid Emoji", "Emoji must be 10 characters or less."))
            return
            
        settings = await self.get_starboard_settings(ctx.guild.id)
        if not settings:
            await ctx.send(embed=create_error_embed(
                "Starboard Not Setup",
                "Please run `/starboard setup` first to configure the starboard system."
            ))
            return
            
        await self.update_starboard_settings(ctx.guild.id, star_emoji=emoji)
        
        embed = create_success_embed("Emoji Updated", f"Star emoji set to {emoji}")
        await ctx.send(embed=embed)
        
    @starboard.command(name="toggle", description="Enable or disable the starboard")
    @commands.has_permissions(manage_guild=True)
    async def starboard_toggle(self, ctx: commands.Context):
        """Toggle starboard on/off"""
        if not ctx.guild:
            return
            
        settings = await self.get_starboard_settings(ctx.guild.id)
        if not settings:
            await ctx.send(embed=create_error_embed(
                "Starboard Not Setup",
                "Please run `/starboard setup` first to configure the starboard system."
            ))
            return
            
        new_status = not settings.get('enabled', True)
        await self.update_starboard_settings(ctx.guild.id, enabled=new_status)
        
        status_text = "Enabled" if new_status else "Disabled"
        color = discord.Color.green() if new_status else discord.Color.red()
        
        embed = discord.Embed(
            title="Starboard Toggled",
            description=f"Starboard is now **{status_text}**",
            color=color
        )
        await ctx.send(embed=embed)
        
    @starboard.command(name="stats", description="Show starboard statistics")
    async def starboard_stats(self, ctx: commands.Context):
        """Show enhanced starboard statistics"""
        if not ctx.guild:
            return
            
        settings = await self.get_starboard_settings(ctx.guild.id)
        if not settings:
            await ctx.send(embed=create_error_embed(
                "Starboard Not Setup",
                "Please run `?starboard setup` first to configure the starboard system."
            ))
            return
            
        async with aiosqlite.connect(self.database_path) as db:
            # Get total starred messages
            cursor = await db.execute(
                "SELECT COUNT(*) FROM starred_messages WHERE guild_id = ?",
                (ctx.guild.id,)
            )
            result = await cursor.fetchone()
            total_starred = result[0] if result else 0
            
            # Get total stars given
            cursor = await db.execute(
                "SELECT COUNT(*) FROM user_stars WHERE guild_id = ?",
                (ctx.guild.id,)
            )
            result = await cursor.fetchone()
            total_stars = result[0] if result else 0
            
            # Get top starred message with more details
            cursor = await db.execute("""
                SELECT star_count, message_id, author_id, content 
                FROM starred_messages 
                WHERE guild_id = ? 
                ORDER BY star_count DESC 
                LIMIT 1
            """, (ctx.guild.id,))
            top_message = await cursor.fetchone()
            
            # Get top 3 most active users (who give the most stars)
            cursor = await db.execute("""
                SELECT user_id, COUNT(*) as stars_given 
                FROM user_stars 
                WHERE guild_id = ? 
                GROUP BY user_id 
                ORDER BY stars_given DESC 
                LIMIT 3
            """, (ctx.guild.id,))
            top_starers = await cursor.fetchall()
            
        # Dynamic color based on activity level
        if total_stars >= 100:
            color = 0xFFD700  # Gold
        elif total_stars >= 50:
            color = 0xFF6B6B  # Red
        elif total_stars >= 20:
            color = 0x4ECDC4  # Teal
        else:
            color = 0xF7DC6F  # Yellow
            
        embed = discord.Embed(
            title="⭐ Starboard Statistics",
            description="Here's how your server is shining!",
            color=color
        )
        
        # Main stats in a clean grid
        embed.add_field(
            name=" Messages Starred", 
            value=f"**{total_starred:,}**", 
            inline=True
        )
        embed.add_field(
            name="⭐ Total Stars", 
            value=f"**{total_stars:,}**", 
            inline=True
        )
        embed.add_field(
            name=" Threshold", 
            value=f"**{settings['threshold']}** {settings['star_emoji']}", 
            inline=True
        )
        
        # Configuration info
        embed.add_field(
            name=" Channel", 
            value=f"<#{settings['channel_id']}>", 
            inline=True
        )
        embed.add_field(
            name=" Star Emoji", 
            value=settings['star_emoji'], 
            inline=True
        )
        status_emoji = "🟢" if settings.get('enabled', True) else ""
        embed.add_field(
            name=" Status", 
            value=f"{status_emoji} {'Active' if settings.get('enabled', True) else 'Disabled'}", 
            inline=True
        )
        
        # Top starred message info
        if top_message:
            star_count, _msg_id, author_id, content = top_message
            author = ctx.guild.get_member(author_id)
            author_name = author.display_name if author else "Unknown User"
            
            # Truncate content for display
            display_content = content[:100] + "..." if content and len(content) > 100 else content or "*No text*"
            
            embed.add_field(
                name=f" Most Starred ({star_count} {settings['star_emoji']})",
                value=f"By **{author_name}**\n*{display_content}*",
                inline=False
            )
            
        # Top starers
        if top_starers:
            starer_list = []
            for user_id, count in top_starers:
                user = ctx.guild.get_member(user_id)
                if user:
                    starer_list.append(f"**{user.display_name}** - {count} stars")
                    
            if starer_list:
                embed.add_field(
                    name=" Top Star Givers",
                    value="\n".join(starer_list),
                    inline=False
                )
        
        # Add some flavor text based on activity
        if total_stars == 0:
            embed.set_footer(text=" Ready to start starring messages! React with ⭐ to get started.")
        elif total_stars < 10:
            embed.set_footer(text=" Your starboard is just getting started! Keep starring great messages.")
        elif total_stars < 50:
            embed.set_footer(text=" Great activity! Your community is engaged with the starboard.")
        else:
            embed.set_footer(text=" Amazing! Your starboard is thriving with community engagement.")
            
        await ctx.send(embed=embed)
        
    async def show_starboard_status(self, ctx: commands.Context):
        """Show current starboard configuration"""
        if not ctx.guild:
            return
            
        settings = await self.get_starboard_settings(ctx.guild.id)
        
        if not settings:
            embed = create_warning_embed(
                "Starboard Not Setup",
                "Starboard is not configured for this server.\nUse `/starboard setup` to get started!"
            )
            embed.add_field(
                name=" Quick Setup",
                value="`/starboard setup #channel-name 3 ⭐`",
                inline=False
            )
        else:
            status = "🟢 Enabled" if settings['enabled'] else " Disabled"
            channel = f"<#{settings['channel_id']}>" if settings['channel_id'] else "Not set"
            
            embed = discord.Embed(
                title="⭐ Starboard Configuration",
                color=discord.Color.gold()
            )
            embed.add_field(name=" Status", value=status, inline=True)
            embed.add_field(name=" Channel", value=channel, inline=True)
            embed.add_field(name=" Threshold", value=str(settings['threshold']), inline=True)
            embed.add_field(name=" Emoji", value=settings['star_emoji'], inline=True)
            embed.add_field(name=" Self-starring", value="Allowed", inline=True)
            
        await ctx.send(embed=embed)

    # ==================== REACTION MONITORING ====================
    
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        """Handle star reactions being added"""
        if not self.ready:
            return
        
        # Only process if in a guild and not from bot
        if not reaction.message.guild or user.bot:
            return
        
        # Quick check if it might be a star emoji before doing heavy processing
        settings = await self.get_starboard_settings(reaction.message.guild.id)
        if settings and str(reaction.emoji) == settings.get('star_emoji', '⭐'):
            self.logger.debug(f"⭐ Starboard: Star reaction added by {user.name} on message {reaction.message.id}")
            await self.handle_star_reaction(reaction, user, added=True)
        
    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction: discord.Reaction, user: discord.User):
        """Handle star reactions being removed"""
        if not self.ready:
            return
        
        # Only process if in a guild and not from bot
        if not reaction.message.guild or user.bot:
            return
        
        # Quick check if it might be a star emoji before doing heavy processing
        settings = await self.get_starboard_settings(reaction.message.guild.id)
        if settings and str(reaction.emoji) == settings.get('star_emoji', '⭐'):
            self.logger.debug(f"⭐ Starboard: Star reaction removed by {user.name} on message {reaction.message.id}")
            await self.handle_star_reaction(reaction, user, added=False)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handle reactions added for uncached messages by fetching the message and delegating."""
        if not self.ready:
            return

        # Only handle guild reactions
        if payload.guild_id is None:
            return

        settings = await self.get_starboard_settings(payload.guild_id)
        if not settings or not settings.get('enabled', True):
            return

        # Quick emoji check to avoid extra fetches
        try:
            if str(payload.emoji) != settings.get('star_emoji', '⭐'):
                return
        except Exception:
            return

        # Fetch channel and message (ensure channel supports fetch_message)
        try:
            channel = self.bot.get_channel(payload.channel_id) or await self.bot.fetch_channel(payload.channel_id)
            if not hasattr(channel, 'fetch_message'):
                return
            # Cast to Messageable for type checkers
            from typing import cast

            from discord.abc import Messageable
            mchannel = cast(Messageable, channel)
            message = await mchannel.fetch_message(payload.message_id)
        except Exception:
            return

        # Try to find an existing Reaction object on the message; otherwise create a lightweight proxy
        reaction_obj = None
        for r in getattr(message, 'reactions', []):
            if str(r.emoji) == str(payload.emoji):
                reaction_obj = r
                break

        if reaction_obj is None:
            reaction_obj = ReactionProxy(payload.emoji, message)

        # Resolve user object
        user = None
        guild = self.bot.get_guild(payload.guild_id)
        if guild:
            user = guild.get_member(payload.user_id)

        if user is None:
            try:
                user = await self.bot.fetch_user(payload.user_id)
            except Exception:
                return

        # Ensure user is a discord.User (convert Member if necessary)
        if hasattr(user, 'user'):
            user_obj = user.user
        else:
            user_obj = user

        await self.handle_star_reaction(reaction_obj, user_obj, added=True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Handle reaction removals for uncached messages."""
        if not self.ready:
            return

        if payload.guild_id is None:
            return

        settings = await self.get_starboard_settings(payload.guild_id)
        if not settings or not settings.get('enabled', True):
            return

        try:
            if str(payload.emoji) != settings.get('star_emoji', '⭐'):
                return
        except Exception:
            return

        try:
            channel = self.bot.get_channel(payload.channel_id) or await self.bot.fetch_channel(payload.channel_id)
            if not hasattr(channel, 'fetch_message'):
                return
            # Cast to Messageable for type checkers
            from typing import cast

            from discord.abc import Messageable
            mchannel = cast(Messageable, channel)
            message = await mchannel.fetch_message(payload.message_id)
        except Exception:
            return

        reaction_obj = None
        for r in getattr(message, 'reactions', []):
            if str(r.emoji) == str(payload.emoji):
                reaction_obj = r
                break

        if reaction_obj is None:
            reaction_obj = ReactionProxy(payload.emoji, message)

        user = None
        guild = self.bot.get_guild(payload.guild_id)
        if guild:
            user = guild.get_member(payload.user_id)

        if user is None:
            try:
                user = await self.bot.fetch_user(payload.user_id)
            except Exception:
                return

        if hasattr(user, 'user'):
            user_obj = user.user
        else:
            user_obj = user

        await self.handle_star_reaction(reaction_obj, user_obj, added=False)
        
    async def handle_star_reaction(self, reaction: Any, user: Any, added: bool):
        """Process star reactions (add or remove) - assumes pre-validated emoji"""
        message = reaction.message
        # Ignore bot accounts (including our own) to avoid counting bot reactions
        try:
            if getattr(user, 'bot', False):
                return
        except Exception:
            pass
        
        # Get starboard settings (should exist from pre-check)
        settings = await self.get_starboard_settings(message.guild.id)
        if not settings or not settings.get('enabled', True):
            return
            
        # Skip bot messages in starboard channel to prevent loops
        if message.channel.id == settings.get('channel_id'):
            return

        # Enforce self-starring setting: if disabled, ignore reactions by the message author
        if not settings.get('self_star', True) and user.id == message.author.id:
            return
            
        # Handle the star with a per-message lock to avoid duplicate postings when reactions come in quick succession
        current_time = datetime.now(timezone.utc).isoformat()

        # Acquire/create lock for this message id
        lock = self._locks.get(message.id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[message.id] = lock

        async with lock:
            async with aiosqlite.connect(self.database_path) as db:
                if added:
                    # Add star
                    try:
                        await db.execute("""
                            INSERT INTO user_stars (message_id, user_id, guild_id, starred_at)
                            VALUES (?, ?, ?, ?)
                        """, (message.id, user.id, message.guild.id, current_time))
                        await db.commit()
                        self.logger.debug(f"💫 Starboard: Star added to DB for message {message.id} by user {user.id}")
                    except Exception as e:
                        # Star already exists, ignore (common duplicate insert)
                        self.logger.debug(f"ℹ️ Starboard: Star already exists or error: {e}")
                else:
                    # Remove star
                    await db.execute("""
                        DELETE FROM user_stars 
                        WHERE message_id = ? AND user_id = ?
                    """, (message.id, user.id))
                    await db.commit()
                    self.logger.debug(f"💫 Starboard: Star removed from DB for message {message.id} by user {user.id}")

                # Get current star count
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM user_stars WHERE message_id = ?
                """, (message.id,))
                result = await cursor.fetchone()
                star_count = result[0] if result else 0
                self.logger.debug(f"📊 Starboard: Message {message.id} now has {star_count} stars (threshold: {settings['threshold']})")

                # Check if message exists in starred_messages
                cursor = await db.execute("""
                    SELECT starboard_message_id, star_count FROM starred_messages WHERE message_id = ?
                """, (message.id,))
                existing = await cursor.fetchone()

                threshold = settings['threshold']

                if star_count >= threshold:
                    if existing:
                        # Update existing starboard message
                        self.logger.debug(f"📝 Starboard: Updating message {message.id} with {star_count} stars")
                        await self.update_starboard_message(message, star_count, existing[0], settings)
                        await db.execute("""
                            UPDATE starred_messages 
                            SET star_count = ?, last_updated = ?
                            WHERE message_id = ?
                        """, (star_count, current_time, message.id))
                    else:
                        # Create new starboard message
                        self.logger.debug(f"⭐ Starboard: Creating new starboard message for {message.id} with {star_count} stars (threshold: {threshold})")
                        starboard_msg = await self.create_starboard_message(message, star_count, settings)
                        if starboard_msg:
                            starboard_msg_id = starboard_msg.id
                            self.logger.debug(f"✅ Starboard: Created message {starboard_msg_id} in starboard channel")
                            try:
                                await db.execute("""
                                    INSERT INTO starred_messages 
                                    (message_id, guild_id, channel_id, author_id, starboard_message_id, 
                                     star_count, content, attachments, created_at, last_updated)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    message.id, message.guild.id, message.channel.id, message.author.id,
                                    starboard_msg_id, star_count, message.content or "", 
                                    str([att.url for att in message.attachments]), current_time, current_time
                                ))
                                await db.commit()
                            except Exception as e:
                                self.logger.exception(f"Error inserting starred_messages for {message.id}: {e}")
                        else:
                            self.logger.error(f"❌ Starboard: Failed to create starboard message for {message.id}")
                else:
                    if existing and star_count < threshold:
                        # Remove from starboard if below threshold
                        await self.remove_starboard_message(existing[0], settings)
                        await db.execute("DELETE FROM starred_messages WHERE message_id = ?", (message.id,))
                        await db.commit()
            
    async def create_starboard_message(self, message: discord.Message, star_count: int, settings: dict) -> discord.Message | None:
        """Create a new starboard message"""
        if not message.guild:
            self.logger.error(f"❌ Starboard: Message {message.id} is not in a guild")
            return None

        starboard_channel = message.guild.get_channel(settings['channel_id'])
        if not starboard_channel:
            self.logger.error(f"❌ Starboard: Channel {settings['channel_id']} not found in guild {message.guild.id}")
            return None
        if not isinstance(starboard_channel, discord.TextChannel):
            self.logger.error(f"❌ Starboard: Channel {settings['channel_id']} is not a text channel")
            return None

        try:
            self.logger.debug(f"📤 Starboard: Sending starboard embed to {starboard_channel.name}")
            embed = await self.create_starboard_embed(message, star_count, settings)
            extra_content = self._build_starboard_extra_content(message)
            starboard_msg = await starboard_channel.send(content=extra_content, embed=embed)

            # Try to add the star emoji reaction to both starboard msg and original message so it's obvious
            try:
                star_emoji = settings.get('star_emoji', '⭐')
                await starboard_msg.add_reaction(star_emoji)
            except Exception:
                pass

            try:
                # Add reaction to original message as well (if permissions allow)
                star_emoji = settings.get('star_emoji', '⭐')
                await message.add_reaction(star_emoji)
            except Exception:
                pass

            self.logger.debug(f"✅ Starboard: Successfully posted message {starboard_msg.id} to starboard")
            return starboard_msg
        except Exception:
            self.logger.exception(f"❌ Starboard: Error creating starboard message for {message.id}")
            return None
            
    async def update_starboard_message(self, message: discord.Message, star_count: int, 
                                     starboard_msg_id: int, settings: dict):
        """Update an existing starboard message"""
        if not message.guild:
            return
            
        starboard_channel = message.guild.get_channel(settings['channel_id'])
        if not starboard_channel or not isinstance(starboard_channel, discord.TextChannel):
            return
            
        try:
            starboard_msg = await starboard_channel.fetch_message(starboard_msg_id)
            embed = await self.create_starboard_embed(message, star_count, settings)
            extra_content = self._build_starboard_extra_content(message)
            await starboard_msg.edit(content=extra_content, embed=embed)
            # Ensure the bot reacts to both starboard and original messages
            try:
                await starboard_msg.add_reaction(settings.get('star_emoji', '⭐'))
            except Exception:
                pass

            try:
                await message.add_reaction(settings.get('star_emoji', '⭐'))
            except Exception:
                pass
        except discord.NotFound:
            # Starboard message was deleted, remove from database
            async with aiosqlite.connect(self.database_path) as db:
                await db.execute("DELETE FROM starred_messages WHERE starboard_message_id = ?", (starboard_msg_id,))
                await db.commit()
        except Exception:
            self.logger.exception(f"Error updating starboard message {starboard_msg_id} for original {message.id}")
            
    async def remove_starboard_message(self, starboard_msg_id: int, settings: dict):
        """Remove a starboard message"""
        starboard_channel = self.bot.get_channel(settings['channel_id'])
        if not starboard_channel or not isinstance(starboard_channel, discord.TextChannel):
            return
            
        try:
            starboard_msg = await starboard_channel.fetch_message(starboard_msg_id)
            await starboard_msg.delete()
        except discord.NotFound:
            pass  # Already deleted
        except Exception:
            self.logger.exception(f"Error removing starboard message {starboard_msg_id}")
            
    async def create_starboard_embed(self, message: discord.Message, star_count: int, settings: dict) -> discord.Embed:
        """Create a beautiful, modern embed for starboard message"""
        star_emoji = settings.get('star_emoji', '⭐')
        # Keep the starboard embed compact: author, avatar, highlighted message, and jump link
        # Dynamic color retained for slight visual cue
        if star_count >= 20:
            color = 0xFFD700
        elif star_count >= 10:
            color = 0xFF6B6B
        elif star_count >= 5:
            color = 0x4ECDC4
        else:
            color = 0xF7DC6F

        content = message.content or "*No text content*"
        if len(content) > 1500:
            content = content[:1500] + "..."

        # Highlight the message by using a block quote style in the description
        quoted_content = content.replace("\n", "\n> ")
        description = f"> {quoted_content}"

        embed = discord.Embed(
            description=description,
            color=color
        )

        # Author with avatar only
        embed.set_author(name=f"{message.author.display_name}", icon_url=message.author.display_avatar.url)

        # Add star count field (single, non-duplicated display)
        embed.add_field(name="Stars", value=f"{star_emoji} {star_count}", inline=True)

        # Attachment handling:
        # - First image (if any) is displayed inline via embed.set_image.
        # - Video(s) are included as raw URLs in the starboard message content so Discord shows a player.
        # - Non-image attachments are listed as links.
        image_url = None
        video_links: list[str] = []
        other_links: list[str] = []
        try:
            for att in getattr(message, 'attachments', []):
                fname = getattr(att, 'filename', '') or ''
                content_type = getattr(att, 'content_type', None)
                if content_type and str(content_type).startswith('image'):
                    image_url = att.url
                    break
                # Fallback to extension check
                if any(fname.lower().endswith(ext) for ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                    image_url = att.url
                    break

            # Collect video + other attachment links (do not stop at first image)
            for att in getattr(message, 'attachments', []):
                fname = getattr(att, 'filename', '') or ''
                ctype = getattr(att, 'content_type', None)
                lower = fname.lower()
                is_image = (ctype and str(ctype).startswith('image')) or any(lower.endswith(ext) for ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp'))
                is_video = (ctype and str(ctype).startswith('video')) or any(lower.endswith(ext) for ext in ('.mp4', '.webm', '.mov'))

                if is_video:
                    video_links.append(att.url)
                elif not is_image:
                    other_links.append(att.url)

            # Check embeds for an image if no attachment image
            if not image_url:
                for emb in getattr(message, 'embeds', []) or []:
                    if getattr(emb, 'image', None) and getattr(emb.image, 'url', None):
                        image_url = emb.image.url
                        break
        except Exception:
            image_url = None

        # Add attachment link fields
        try:
            if video_links:
                # Keep within embed field limits
                shown = video_links[:3]
                embed.add_field(name="Video", value="\n".join(shown), inline=False)
            if other_links:
                shown = other_links[:5]
                embed.add_field(name="Attachments", value="\n".join(shown), inline=False)
        except Exception:
            pass

        if image_url:
            try:
                embed.set_image(url=image_url)
            except Exception:
                pass

        # Minimal jump link field
        embed.add_field(name="Jump", value=f"[Jump to message]({message.jump_url})", inline=False)

        # (Removed display of individual starrers to keep starboard compact)

        # No extra footer or timestamp to keep it compact
        return embed

    def _build_starboard_extra_content(self, message: discord.Message) -> str | None:
        """Build additional message content for starboard posts.

        Discord renders a playable video preview when the CDN URL is in the message content.
        Embeds alone often won't show video attachments.
        """
        urls: list[str] = []

        # Prefer actual attachment URLs for uploaded videos.
        for att in getattr(message, 'attachments', []):
            fname = (getattr(att, 'filename', '') or '').lower()
            ctype = getattr(att, 'content_type', None)
            is_video = (ctype and str(ctype).startswith('video')) or any(fname.endswith(ext) for ext in ('.mp4', '.webm', '.mov'))
            if is_video and getattr(att, 'url', None):
                urls.append(att.url)

        # Also handle embed video links (e.g., link previews) when present.
        for emb in getattr(message, 'embeds', []) or []:
            try:
                # Some embeds carry a video.url
                v = getattr(emb, 'video', None)
                vurl = getattr(v, 'url', None) if v else None
                if vurl:
                    urls.append(str(vurl))
                    continue
                # Fallback to emb.url when it's a video-type embed
                if getattr(emb, 'type', None) in ("video", "gifv") and getattr(emb, 'url', None):
                    urls.append(str(emb.url))
            except Exception:
                continue

        # De-dup while keeping order
        deduped: list[str] = []
        seen: set[str] = set()
        for u in urls:
            if not u or u in seen:
                continue
            seen.add(u)
            deduped.append(u)

        if not deduped:
            return None

        # Cap to avoid hitting 2000 char limit.
        return "\n".join(deduped[:3])

    # ==================== ADMIN UTILITIES ====================
    
    @commands.hybrid_command(name='starboard_cleanup', description='Clean up invalid starboard entries')
    @app_commands.describe(
        confirm='Type "confirm" to proceed with cleanup'
    )
    @app_commands.default_permissions(administrator=True)
    async def cleanup_starboard(self, ctx: commands.Context, confirm: str = ""):
        """Clean up invalid starboard entries (Admin only)"""
        if confirm.lower() != "confirm":
            embed = create_warning_embed(
                "Cleanup Confirmation Required",
                "This will remove starboard entries for:\n"
                "• Deleted messages\n"
                "• Messages from deleted channels\n"
                "• Invalid starboard messages\n\n"
                "Use: `/starboard cleanup confirm`"
            )
            await ctx.send(embed=embed)
            return
            
        if not ctx.guild:
            return
            
        settings = await self.get_starboard_settings(ctx.guild.id)
        if not settings:
            embed = create_error_embed("Starboard not configured for this server")
            await ctx.send(embed=embed)
            return
            
        try:
            await ctx.defer()
        except Exception:
            # If we can't defer (older discord.py or missing interaction), continue silently
            pass
        
        cleaned_count = 0
        
        async with aiosqlite.connect(self.database_path) as db:
            # Get all starred messages for this guild
            cursor = await db.execute("""
                SELECT message_id, channel_id, starboard_message_id 
                FROM starred_messages 
                WHERE guild_id = ?
            """, (ctx.guild.id,))
            
            entries = await cursor.fetchall()
            
            for message_id, channel_id, starboard_msg_id in entries:
                should_clean = False
                
                # Check if original message exists
                try:
                    channel = ctx.guild.get_channel(channel_id)
                    if not channel or not isinstance(channel, discord.TextChannel):
                        should_clean = True
                    else:
                        await channel.fetch_message(message_id)
                except discord.NotFound:
                    should_clean = True
                except:
                    pass
                    
                # Check if starboard message exists
                if not should_clean and starboard_msg_id:
                    try:
                        starboard_channel = ctx.guild.get_channel(settings['channel_id'])
                        if starboard_channel and isinstance(starboard_channel, discord.TextChannel):
                            await starboard_channel.fetch_message(starboard_msg_id)
                    except discord.NotFound:
                        should_clean = True
                    except:
                        pass
                        
                if should_clean:
                    # Remove from database
                    await db.execute("DELETE FROM starred_messages WHERE message_id = ?", (message_id,))
                    await db.execute("DELETE FROM user_stars WHERE message_id = ?", (message_id,))
                    cleaned_count += 1
                    
            await db.commit()
            
        embed = discord.Embed(
            title=" Starboard Cleanup Complete",
            description=f"Cleaned up {cleaned_count} invalid entries",
            color=discord.Color.green()
        )
        
        if cleaned_count > 0:
            embed.add_field(
                name=" Removed",
                value=f"{cleaned_count} invalid starboard entries",
                inline=False
            )
            
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(StarboardSystem(bot))
