"""
Starboard System - Track and display starred messages
Similar to Dyno bot functionality with self-starring allowed
"""

import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
from datetime import datetime, timezone
from typing import Optional, Dict, Tuple
import os
from pathlib import Path
from utils.helpers import create_success_embed, create_error_embed, create_warning_embed

class StarboardSystem(commands.Cog):
    @commands.hybrid_command(name="starboard_info", description="Show starboard usage tips and quick setup guide")
    async def starboard_info(self, ctx: commands.Context):
        """Show starboard usage tips and quick setup guide"""
        embed = discord.Embed(
            title="⭐ Modern Starboard Guide",
            description=(
                "Highlight popular messages with stars!\n"
                "\n**How it works:**\n"
                "• React to any message with the configured star emoji (default: ⭐)\n"
                "• When a message reaches the threshold, it appears in the starboard channel\n"
                "• Self-starring is allowed\n"
                "• Attachments and images are supported\n"
                "• Footer shows who starred and when\n"
                "\n**Quick Setup:**\n"
                "`/starboard setup #starboard 3 ⭐`\n"
                "• Change channel: `/starboard channel #starboard`\n"
                "• Change threshold: `/starboard threshold 5`\n"
                "• Change emoji: `/starboard emoji 🌟`\n"
                "• View stats: `/starboard stats`\n"
                "• Clean up: `/starboard_cleanup confirm`\n"
            ),
            color=discord.Color.blurple()
        )
        embed.set_footer(text="Starboard by Codeverse Bot • Modern & Professional")
        await ctx.send(embed=embed)
    """Starboard system for highlighting popular messages with star reactions"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.database_path = Path("data/starboard.db")
        self.star_cache: Dict[int, Dict] = {}  # Cache for quick lookups
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
                
    async def get_starboard_settings(self, guild_id: int) -> Optional[Dict]:
        """Get starboard settings for a guild"""
        if guild_id in self.star_cache:
            return self.star_cache[guild_id]
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
                    query = f"UPDATE starboard_settings SET {', '.join(set_clauses)} WHERE guild_id = ?"
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
            "Starboard Setup Complete",
            f"Starboard has been configured successfully!"
        )
        embed.add_field(name="📍 Channel", value=channel.mention, inline=True)
        embed.add_field(name="⭐ Threshold", value=str(threshold), inline=True)
        embed.add_field(name="🌟 Emoji", value=emoji, inline=True)
        embed.add_field(name="✅ Self-starring", value="Allowed", inline=True)
        embed.add_field(name="🎯 Status", value="Enabled", inline=True)
        
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
    @app_commands.describe(emoji="Emoji to use for starring (⭐, 🌟, etc.)")
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
        """Show starboard statistics"""
        if not ctx.guild:
            return
            
        settings = await self.get_starboard_settings(ctx.guild.id)
        if not settings:
            await ctx.send(embed=create_error_embed(
                "Starboard Not Setup",
                "Please run `/starboard setup` first to configure the starboard system."
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
            
            # Get top starred message
            cursor = await db.execute(
                "SELECT star_count, message_id FROM starred_messages WHERE guild_id = ? ORDER BY star_count DESC LIMIT 1",
                (ctx.guild.id,)
            )
            top_message = await cursor.fetchone()
            
        embed = discord.Embed(
            title="⭐ Starboard Statistics",
            color=discord.Color.gold()
        )
        embed.add_field(name="📊 Total Starred Messages", value=str(total_starred), inline=True)
        embed.add_field(name="⭐ Total Stars Given", value=str(total_stars), inline=True)
        embed.add_field(name="🎯 Current Threshold", value=str(settings['threshold']), inline=True)
        
        if top_message:
            embed.add_field(name="🏆 Most Starred", value=f"{top_message[0]} stars", inline=True)
            
        embed.add_field(name="📍 Channel", value=f"<#{settings['channel_id']}>", inline=True)
        embed.add_field(name="🌟 Emoji", value=settings['star_emoji'], inline=True)
        
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
                name="💡 Quick Setup",
                value="`/starboard setup #channel-name 3 ⭐`",
                inline=False
            )
        else:
            status = "🟢 Enabled" if settings['enabled'] else "🔴 Disabled"
            channel = f"<#{settings['channel_id']}>" if settings['channel_id'] else "Not set"
            
            embed = discord.Embed(
                title="⭐ Starboard Configuration",
                color=discord.Color.gold()
            )
            embed.add_field(name="📊 Status", value=status, inline=True)
            embed.add_field(name="📍 Channel", value=channel, inline=True)
            embed.add_field(name="🎯 Threshold", value=str(settings['threshold']), inline=True)
            embed.add_field(name="🌟 Emoji", value=settings['star_emoji'], inline=True)
            embed.add_field(name="✅ Self-starring", value="Allowed", inline=True)
            
        await ctx.send(embed=embed)

    # ==================== REACTION MONITORING ====================
    
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        """Handle star reactions being added"""
        if not self.ready:
            return
            
        await self.handle_star_reaction(reaction, user, added=True)
        
    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction: discord.Reaction, user: discord.User):
        """Handle star reactions being removed"""
        if not self.ready:
            return
            
        await self.handle_star_reaction(reaction, user, added=False)
        
    async def handle_star_reaction(self, reaction: discord.Reaction, user: discord.User, added: bool):
        """Process star reactions (add or remove)"""
        message = reaction.message
        
        # Skip if not in a guild
        if not message.guild:
            return
            
        # Skip bot messages in starboard channel to prevent loops
        settings = await self.get_starboard_settings(message.guild.id)
        if not settings or not settings['enabled']:
            return
            
        if message.channel.id == settings.get('channel_id'):
            return
            
        # Check if this is the star emoji
        star_emoji = settings.get('star_emoji', '⭐')
        if str(reaction.emoji) != star_emoji:
            return
            
        # Skip if reacting user is a bot (unless it's self-starring)
        if user.bot and user.id != message.author.id:
            return
            
        # Handle the star
        current_time = datetime.now(timezone.utc).isoformat()
        
        async with aiosqlite.connect(self.database_path) as db:
            if added:
                # Add star
                try:
                    await db.execute("""
                        INSERT INTO user_stars (message_id, user_id, guild_id, starred_at)
                        VALUES (?, ?, ?, ?)
                    """, (message.id, user.id, message.guild.id, current_time))
                    await db.commit()
                except:
                    # Star already exists, ignore
                    return
            else:
                # Remove star
                await db.execute("""
                    DELETE FROM user_stars 
                    WHERE message_id = ? AND user_id = ?
                """, (message.id, user.id))
                await db.commit()
            
            # Get current star count
            cursor = await db.execute("""
                SELECT COUNT(*) FROM user_stars WHERE message_id = ?
            """, (message.id,))
            result = await cursor.fetchone()
            star_count = result[0] if result else 0
            
            # Check if message exists in starred_messages
            cursor = await db.execute("""
                SELECT starboard_message_id, star_count FROM starred_messages WHERE message_id = ?
            """, (message.id,))
            existing = await cursor.fetchone()
            
            threshold = settings['threshold']
            
            if star_count >= threshold:
                if existing:
                    # Update existing starboard message
                    await self.update_starboard_message(message, star_count, existing[0], settings)
                    await db.execute("""
                        UPDATE starred_messages 
                        SET star_count = ?, last_updated = ?
                        WHERE message_id = ?
                    """, (star_count, current_time, message.id))
                else:
                    # Create new starboard message
                    starboard_msg_id = await self.create_starboard_message(message, star_count, settings)
                    if starboard_msg_id:
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
            else:
                if existing and star_count < threshold:
                    # Remove from starboard if below threshold
                    await self.remove_starboard_message(existing[0], settings)
                    await db.execute("DELETE FROM starred_messages WHERE message_id = ?", (message.id,))
                    
            await db.commit()
            
    async def create_starboard_message(self, message: discord.Message, star_count: int, settings: Dict) -> Optional[int]:
        """Create a new starboard message"""
        if not message.guild:
            return None
            
        starboard_channel = message.guild.get_channel(settings['channel_id'])
        if not starboard_channel or not isinstance(starboard_channel, discord.TextChannel):
            return None
            
        try:
            embed = await self.create_starboard_embed(message, star_count, settings)
            starboard_msg = await starboard_channel.send(embed=embed)
            return starboard_msg.id
        except Exception as e:
            print(f"❌ Error creating starboard message: {e}")
            return None
            
    async def update_starboard_message(self, message: discord.Message, star_count: int, 
                                     starboard_msg_id: int, settings: Dict):
        """Update an existing starboard message"""
        if not message.guild:
            return
            
        starboard_channel = message.guild.get_channel(settings['channel_id'])
        if not starboard_channel or not isinstance(starboard_channel, discord.TextChannel):
            return
            
        try:
            starboard_msg = await starboard_channel.fetch_message(starboard_msg_id)
            embed = await self.create_starboard_embed(message, star_count, settings)
            await starboard_msg.edit(embed=embed)
        except discord.NotFound:
            # Starboard message was deleted, remove from database
            async with aiosqlite.connect(self.database_path) as db:
                await db.execute("DELETE FROM starred_messages WHERE starboard_message_id = ?", (starboard_msg_id,))
                await db.commit()
        except Exception as e:
            print(f"❌ Error updating starboard message: {e}")
            
    async def remove_starboard_message(self, starboard_msg_id: int, settings: Dict):
        """Remove a starboard message"""
        starboard_channel = self.bot.get_channel(settings['channel_id'])
        if not starboard_channel or not isinstance(starboard_channel, discord.TextChannel):
            return
            
        try:
            starboard_msg = await starboard_channel.fetch_message(starboard_msg_id)
            await starboard_msg.delete()
        except discord.NotFound:
            pass  # Already deleted
        except Exception as e:
            print(f"❌ Error removing starboard message: {e}")
            
    async def create_starboard_embed(self, message: discord.Message, star_count: int, settings: Dict) -> discord.Embed:
        """Create embed for starboard message"""
        star_emoji = settings.get('star_emoji', '⭐')
        embed = discord.Embed(
            description=message.content or "*No text content*",
            color=discord.Color.blurple(),
            timestamp=message.created_at
        )
        # Modern author header
        embed.set_author(
            name=f"{message.author.display_name} • {star_emoji} {star_count}",
            icon_url=message.author.display_avatar.url
        )
        # Add jump link as a field
        embed.add_field(
            name="Jump to Message",
            value=f"[Click here]({message.jump_url})",
            inline=True
        )
        # Channel info
        if isinstance(message.channel, (discord.TextChannel, discord.VoiceChannel, discord.StageChannel, discord.Thread)):
            channel_name = message.channel.mention
        elif hasattr(message.channel, 'name'):
            channel_name = f"#{getattr(message.channel, 'name', 'Unknown')}"
        else:
            channel_name = "Unknown Channel"
        embed.add_field(
            name="Channel",
            value=channel_name,
            inline=True
        )
        # Attachments
        if message.attachments:
            attachment = message.attachments[0]
            if attachment.content_type and attachment.content_type.startswith('image'):
                embed.set_image(url=attachment.url)
            else:
                embed.add_field(
                    name="Attachment",
                    value=f"[{attachment.filename}]({attachment.url})",
                    inline=False
                )
        if len(message.attachments) > 1:
            other_attachments = message.attachments[1:]
            attachment_list = [f"[{att.filename}]({att.url})" for att in other_attachments]
            embed.add_field(
                name=f"Additional Attachments ({len(other_attachments)})",
                value="\n".join(attachment_list[:5]),
                inline=False
            )
        # Starred by avatars (footer)
        async with aiosqlite.connect(self.database_path) as db:
            cursor = await db.execute("SELECT user_id, starred_at FROM user_stars WHERE message_id = ? ORDER BY starred_at ASC", (message.id,))
            star_users = list(await cursor.fetchall())
        if star_users:
            user_mentions = []
            guild = message.guild
            for row in star_users[:10]:
                user_id, starred_at = row
                user = guild.get_member(user_id) if guild else None
                if user:
                    user_mentions.append(user.display_name)
            first_star = star_users[0][1]
            last_star = star_users[-1][1]
            embed.set_footer(text=f"Starred by: {', '.join(user_mentions)}\nFirst: {first_star} • Last: {last_star}\nMsg ID: {message.id}")
        else:
            embed.set_footer(text=f"Msg ID: {message.id}")
        return embed

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
            
        await ctx.defer()
        
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
            title="✅ Starboard Cleanup Complete",
            description=f"Cleaned up {cleaned_count} invalid entries",
            color=discord.Color.green()
        )
        
        if cleaned_count > 0:
            embed.add_field(
                name="🗑️ Removed",
                value=f"{cleaned_count} invalid starboard entries",
                inline=False
            )
            
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(StarboardSystem(bot))