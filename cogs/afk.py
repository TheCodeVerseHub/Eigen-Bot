"""
AFK (Away From Keyboard) System
Allows users to set AFK status with custom reasons and auto-responds to mentions
"""

import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict
from pathlib import Path


class AFKSystem(commands.Cog):
    """AFK System for automatic away message responses"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.database_path = Path("data/afk.db")
        self.afk_cache: Dict[int, Dict] = {}  # Cache for quick lookups
        self.ready = asyncio.Event()
        
    async def cog_load(self):
        """Initialize the AFK system when the cog loads"""
        await self.init_database()
        await self.load_afk_cache()
        self.ready.set()
        
    async def init_database(self):
        """Initialize the AFK database"""
        # Ensure data directory exists
        self.database_path.parent.mkdir(exist_ok=True)
        
        async with aiosqlite.connect(self.database_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS afk_users (
                    user_id INTEGER PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    reason TEXT,
                    set_time TEXT NOT NULL,
                    mention_count INTEGER DEFAULT 0
                )
            """)
            await db.commit()
            
    async def load_afk_cache(self):
        """Load all AFK users into cache for quick access"""
        async with aiosqlite.connect(self.database_path) as db:
            cursor = await db.execute("SELECT user_id, guild_id, reason, set_time, mention_count FROM afk_users")
            rows = await cursor.fetchall()
            
            for row in rows:
                user_id, guild_id, reason, set_time, mention_count = row
                self.afk_cache[user_id] = {
                    'guild_id': guild_id,
                    'reason': reason,
                    'set_time': set_time,
                    'mention_count': mention_count
                }
                
    async def set_afk(self, user_id: int, guild_id: int, reason: Optional[str] = None):
        """Set a user as AFK"""
        current_time = datetime.now(timezone.utc).isoformat()
        afk_reason = reason or "No reason provided"
        
        async with aiosqlite.connect(self.database_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO afk_users (user_id, guild_id, reason, set_time, mention_count)
                VALUES (?, ?, ?, ?, 0)
            """, (user_id, guild_id, afk_reason, current_time))
            await db.commit()
            
        # Update cache
        self.afk_cache[user_id] = {
            'guild_id': guild_id,
            'reason': afk_reason,
            'set_time': current_time,
            'mention_count': 0
        }
        
    async def remove_afk(self, user_id: int):
        """Remove a user from AFK status"""
        async with aiosqlite.connect(self.database_path) as db:
            await db.execute("DELETE FROM afk_users WHERE user_id = ?", (user_id,))
            await db.commit()
            
        # Remove from cache
        if user_id in self.afk_cache:
            del self.afk_cache[user_id]
            
    async def increment_mention_count(self, user_id: int):
        """Increment the mention count for an AFK user"""
        if user_id in self.afk_cache:
            self.afk_cache[user_id]['mention_count'] += 1
            
            async with aiosqlite.connect(self.database_path) as db:
                await db.execute("""
                    UPDATE afk_users SET mention_count = mention_count + 1 
                    WHERE user_id = ?
                """, (user_id,))
                await db.commit()
                
    def is_afk(self, user_id: int) -> bool:
        """Check if a user is currently AFK"""
        return user_id in self.afk_cache
        
    def get_afk_info(self, user_id: int) -> Optional[Dict]:
        """Get AFK information for a user"""
        return self.afk_cache.get(user_id)
        
    def format_afk_duration(self, set_time_str: str) -> str:
        """Format the AFK duration into a human-readable string"""
        try:
            set_time = datetime.fromisoformat(set_time_str)
            current_time = datetime.now(timezone.utc)
            duration = current_time - set_time
            
            days = duration.days
            hours, remainder = divmod(duration.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            
            if days > 0:
                return f"{days}d {hours}h {minutes}m"
            elif hours > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{minutes}m"
        except:
            return "unknown time"

    @commands.hybrid_command(
        name="afk",
        help="Set yourself as AFK with an optional reason",
        usage="afk [reason]"
    )
    @app_commands.describe(reason="The reason you're going AFK (optional)")
    @commands.guild_only()
    async def set_afk_command(self, ctx: commands.Context, *, reason: Optional[str] = None):
        """Set yourself as AFK"""
        await self.ready.wait()
        
        if not ctx.guild:
            embed = discord.Embed(
                title=" Server Only",
                description="This command can only be used in a server.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, ephemeral=True)
            return
            
        # Check if user is already AFK
        was_afk = self.is_afk(ctx.author.id)
        if was_afk:
            old_info = self.get_afk_info(ctx.author.id)
            action_text = "updated"
        else:
            action_text = "set"
        
        # Set user as AFK
        await self.set_afk(ctx.author.id, ctx.guild.id, reason)
        
        # Create response embed
        embed = discord.Embed(
            title=f" AFK Status {action_text.title()}",
            color=discord.Color.orange()
        )
        
        if reason:
            # Truncate reason if too long
            display_reason = reason[:200] + "..." if len(reason) > 200 else reason
            embed.description = f"**{ctx.author.display_name}** is now AFK: {display_reason}"
        else:
            embed.description = f"**{ctx.author.display_name}** is now AFK"
            
        embed.add_field(
            name=" Auto-Return",
            value="You'll automatically return when you send any message!",
            inline=True
        )
        embed.add_field(
            name=" Mentions",
            value="I'll respond to mentions while you're away",
            inline=True
        )
        
        if was_afk and old_info:
            old_reason = old_info['reason']
            if old_reason != reason:
                embed.add_field(
                    name=" Previous Reason",
                    value=old_reason[:100] + "..." if len(old_reason) > 100 else old_reason,
                    inline=False
                )
        
        embed.set_footer(text=f"Use /unafk to manually return • Set at")
        embed.timestamp = datetime.now(timezone.utc)
        
        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="unafk",
        help="Remove your AFK status manually",
        aliases=["back", "return"]
    )
    @app_commands.describe()
    @commands.guild_only()
    async def remove_afk_command(self, ctx: commands.Context):
        """Manually remove AFK status"""
        await self.ready.wait()
        
        if not self.is_afk(ctx.author.id):
            embed = discord.Embed(
                title=" Not AFK",
                description="You're not currently set as AFK.",
                color=discord.Color.blue()
            )
            embed.add_field(
                name=" Tip",
                value="Use `/afk [reason]` to set yourself as AFK",
                inline=False
            )
            await ctx.send(embed=embed, ephemeral=True)
            return
            
        # Get AFK info before removing
        afk_info = self.get_afk_info(ctx.author.id)
        await self.remove_afk(ctx.author.id)
        
        # Create welcome back embed
        embed = discord.Embed(
            title=" Welcome Back!",
            description=f"**{ctx.author.display_name}** is no longer AFK",
            color=discord.Color.green()
        )
        
        if afk_info:
            duration = self.format_afk_duration(afk_info['set_time'])
            mention_count = afk_info['mention_count']
            reason = afk_info['reason']
            
            embed.add_field(
                name=" AFK Duration",
                value=duration,
                inline=True
            )
            embed.add_field(
                name=" Mentions Received",
                value=str(mention_count),
                inline=True
            )
            
            if reason and reason != "No reason provided":
                embed.add_field(
                    name=" Previous Reason",
                    value=reason[:200] + "..." if len(reason) > 200 else reason,
                    inline=False
                )
            
        embed.set_footer(text="Manually returned from AFK")
        embed.timestamp = datetime.now(timezone.utc)
        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="afklist",
        help="List all currently AFK users in the server",
        aliases=["afkstatus", "whoafk"]
    )
    @app_commands.describe()
    @commands.guild_only()
    async def afk_list_command(self, ctx: commands.Context):
        """Show all currently AFK users in the server"""
        await self.ready.wait()
        
        if not ctx.guild:
            embed = discord.Embed(
                title=" Server Only",
                description="This command can only be used in a server.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, ephemeral=True)
            return
            
        # Get AFK users in this guild
        guild_afk_users = []
        for user_id, afk_data in self.afk_cache.items():
            if afk_data['guild_id'] == ctx.guild.id:
                member = ctx.guild.get_member(user_id)
                if member:  # Only include users still in the server
                    duration = self.format_afk_duration(afk_data['set_time'])
                    guild_afk_users.append({
                        'member': member,
                        'reason': afk_data['reason'],
                        'duration': duration,
                        'mentions': afk_data['mention_count']
                    })
                    
        if not guild_afk_users:
            embed = discord.Embed(
                title=" AFK Users",
                description="No users are currently AFK in this server.",
                color=discord.Color.blue()
            )
            embed.add_field(
                name=" Tip",
                value="Use `/afk [reason]` to set yourself as AFK",
                inline=False
            )
            await ctx.send(embed=embed)
            return
            
        # Sort by AFK duration (longest first)
        guild_afk_users.sort(key=lambda x: x['duration'], reverse=True)
        
        # Create embed with AFK users
        embed = discord.Embed(
            title=" Currently AFK Users",
            description=f"Found **{len(guild_afk_users)}** AFK user(s) in **{ctx.guild.name}**",
            color=discord.Color.orange()
        )
        
        # Show up to 10 users
        display_count = min(len(guild_afk_users), 10)
        for i in range(display_count):
            afk_user = guild_afk_users[i]
            member = afk_user['member']
            reason = afk_user['reason']
            
            # Truncate long reasons
            if len(reason) > 150:
                reason = reason[:150] + "..."
            
            field_value = f"**Reason:** {reason}\n"
            field_value += f"**Duration:** {afk_user['duration']}\n"
            field_value += f"**Mentions:** {afk_user['mentions']}"
            
            embed.add_field(
                name=f" {member.display_name}",
                value=field_value,
                inline=True
            )
            
        if len(guild_afk_users) > 10:
            embed.add_field(
                name=" Note",
                value=f"Showing first 10 of {len(guild_afk_users)} AFK users.\nUse this command again to refresh the list.",
                inline=False
            )
            
        embed.set_footer(text=f"Total: {len(guild_afk_users)} AFK users • Auto-updates every message")
        embed.timestamp = datetime.now(timezone.utc)
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle messages to check for AFK users and auto-return"""
        # Ignore bot messages
        if message.author.bot:
            return
            
        # Ignore DMs
        if not message.guild:
            return
            
        await self.ready.wait()
        
        # Check if the message author is AFK and should be returned
        if self.is_afk(message.author.id):
            afk_info = self.get_afk_info(message.author.id)
            if afk_info:
                duration = self.format_afk_duration(afk_info['set_time'])
                mention_count = afk_info['mention_count']
                
                # Remove from AFK
                await self.remove_afk(message.author.id)
                
                # Send welcome back message
                embed = discord.Embed(
                    title="Welcome Back!",
                    description=f"**{message.author.display_name}** is no longer AFK",
                    color=discord.Color.green()
                )
                embed.add_field(name="Was AFK for", value=duration, inline=True)
                if mention_count > 0:
                    embed.add_field(name="Mentions received", value=str(mention_count), inline=True)
                
                try:
                    await message.channel.send(embed=embed, delete_after=10)
                except:
                    pass  # Ignore if we can't send messages
                    
        # Check for mentions of AFK users
        if message.mentions:
            for mentioned_user in message.mentions:
                # Skip if mentioning themselves
                if mentioned_user.id == message.author.id:
                    continue
                    
                if self.is_afk(mentioned_user.id):
                    afk_info = self.get_afk_info(mentioned_user.id)
                    if afk_info and afk_info['guild_id'] == message.guild.id:
                        # Increment mention count
                        await self.increment_mention_count(mentioned_user.id)
                        
                        # Create AFK response
                        duration = self.format_afk_duration(afk_info['set_time'])
                        reason = afk_info['reason']
                        
                        embed = discord.Embed(
                            title="User is AFK",
                            color=discord.Color.orange()
                        )
                        
                        if reason and reason != "No reason provided":
                            embed.description = f"**{mentioned_user.display_name}** is currently AFK: {reason}"
                        else:
                            embed.description = f"**{mentioned_user.display_name}** is currently AFK"
                            
                        embed.add_field(
                            name="AFK Duration",
                            value=duration,
                            inline=True
                        )
                        embed.add_field(
                            name="Mentions",
                            value=str(afk_info['mention_count'] + 1),  # +1 for current mention
                            inline=True
                        )
                        embed.set_footer(text="They'll see your message when they return!")
                        
                        try:
                            await message.channel.send(embed=embed, delete_after=15)
                        except:
                            pass  # Ignore if we can't send messages
                        
                        # Only respond once per message, even if multiple AFK users are mentioned
                        break


async def setup(bot: commands.Bot):
    await bot.add_cog(AFKSystem(bot))