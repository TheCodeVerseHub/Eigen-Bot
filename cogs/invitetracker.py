"""
Invite Tracker Cog - Professional invite tracking system for Discord servers.

Tracks member invites, maintains leaderboards, and provides detailed analytics.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Dict, List
from datetime import datetime
import aiosqlite
from pathlib import Path


class InviteTracker(commands.Cog):
    """Professional invite tracking system with analytics and leaderboards."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_path = Path("data/invites.db")
        self.db_path.parent.mkdir(exist_ok=True)
        self.invite_cache: Dict[int, Dict[str, discord.Invite]] = {}
        
    async def cog_load(self):
        """Initialize database on cog load."""
        await self.setup_database()
        # Cache invites for all guilds
        for guild in self.bot.guilds:
            await self.cache_invites(guild)
    
    async def setup_database(self):
        """Create database tables if they don't exist."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS invites (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    inviter_id INTEGER,
                    invite_code TEXT,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    left_at TIMESTAMP,
                    is_fake INTEGER DEFAULT 0,
                    PRIMARY KEY (guild_id, user_id, joined_at)
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS invite_stats (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    total_invites INTEGER DEFAULT 0,
                    left_invites INTEGER DEFAULT 0,
                    fake_invites INTEGER DEFAULT 0,
                    PRIMARY KEY (guild_id, user_id)
                )
            """)
            
            await db.commit()
    
    async def cache_invites(self, guild: discord.Guild):
        """Cache all invites for a guild."""
        try:
            invites = await guild.invites()
            self.invite_cache[guild.id] = {invite.code: invite for invite in invites}
        except discord.Forbidden:
            pass  # Bot doesn't have permission to view invites
    
    async def get_invite_stats(self, guild_id: int, user_id: int) -> Dict[str, int]:
        """Get invite statistics for a user."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT total_invites, left_invites, fake_invites
                FROM invite_stats
                WHERE guild_id = ? AND user_id = ?
            """, (guild_id, user_id)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "total": row[0],
                        "left": row[1],
                        "fake": row[2],
                        "valid": row[0] - row[1] - row[2]
                    }
                return {"total": 0, "left": 0, "fake": 0, "valid": 0}
    
    async def update_invite_stats(self, guild_id: int, user_id: int, 
                                  total_delta: int = 0, left_delta: int = 0, fake_delta: int = 0):
        """Update invite statistics for a user."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO invite_stats (guild_id, user_id, total_invites, left_invites, fake_invites)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET
                    total_invites = total_invites + ?,
                    left_invites = left_invites + ?,
                    fake_invites = fake_invites + ?
            """, (guild_id, user_id, total_delta, left_delta, fake_delta, 
                  total_delta, left_delta, fake_delta))
            await db.commit()
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Track which invite was used when a member joins."""
        if member.bot:
            return
        
        guild = member.guild
        
        # Get current invites
        try:
            current_invites = await guild.invites()
        except discord.Forbidden:
            return
        
        # Find which invite was used
        cached_invites = self.invite_cache.get(guild.id, {})
        used_invite = None
        
        for invite in current_invites:
            cached = cached_invites.get(invite.code)
            if cached and invite.uses and cached.uses and invite.uses > cached.uses:
                used_invite = invite
                break
        
        # Update cache
        await self.cache_invites(guild)
        
        if used_invite and used_invite.inviter:
            inviter_id = used_invite.inviter.id
            
            # Check for fake invites (account age < 7 days)
            account_age = (datetime.utcnow() - member.created_at).days
            is_fake = 1 if account_age < 7 else 0
            
            # Record the invite
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO invites (guild_id, user_id, inviter_id, invite_code, is_fake)
                    VALUES (?, ?, ?, ?, ?)
                """, (guild.id, member.id, inviter_id, used_invite.code, is_fake))
                await db.commit()
            
            # Update stats
            if is_fake:
                await self.update_invite_stats(guild.id, inviter_id, total_delta=1, fake_delta=1)
            else:
                await self.update_invite_stats(guild.id, inviter_id, total_delta=1)
    
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Track when invited members leave."""
        if member.bot:
            return
        
        guild = member.guild
        
        # Find who invited this member
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT inviter_id, is_fake FROM invites
                WHERE guild_id = ? AND user_id = ? AND left_at IS NULL
                ORDER BY joined_at DESC LIMIT 1
            """, (guild.id, member.id)) as cursor:
                row = await cursor.fetchone()
                
                if row:
                    inviter_id, is_fake = row
                    
                    # Mark as left
                    await db.execute("""
                        UPDATE invites SET left_at = CURRENT_TIMESTAMP
                        WHERE guild_id = ? AND user_id = ? AND left_at IS NULL
                    """, (guild.id, member.id))
                    await db.commit()
                    
                    # Update stats (only count as left if not fake)
                    if not is_fake:
                        await self.update_invite_stats(guild.id, inviter_id, left_delta=1)
    
    @commands.hybrid_command(name="invitecodes", description="View your invite codes and their usage statistics")
    async def invite_codes(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Display all invite codes created by a user with usage statistics."""
        target = member or ctx.author
        
        if not isinstance(ctx.guild, discord.Guild):
            await ctx.send("This command can only be used in a server.")
            return
        
        try:
            invites = await ctx.guild.invites()
        except discord.Forbidden:
            await ctx.send("I don't have permission to view server invites.")
            return
        
        user_invites = [inv for inv in invites if inv.inviter and inv.inviter.id == target.id]
        
        if not user_invites:
            embed = discord.Embed(
                title="Invite Codes",
                description=f"{target.mention} has not created any invite codes.",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title=f"Invite Codes - {target.display_name}",
            description=f"Total Codes: {len(user_invites)}",
            color=discord.Color.blue()
        )
        
        sorted_invites = sorted(user_invites, key=lambda x: x.uses or 0, reverse=True)[:10]
        for invite in sorted_invites:
            max_uses = invite.max_uses if (invite.max_uses and invite.max_uses > 0) else "Unlimited"
            expires = f"<t:{int(invite.expires_at.timestamp())}:R>" if invite.expires_at else "Never"
            
            # Safe channel mention handling
            if invite.channel and hasattr(invite.channel, 'mention'):
                channel_mention = invite.channel.mention  # type: ignore
            else:
                channel_mention = 'Unknown'
            
            value = (
                f"Code: `{invite.code}`\n"
                f"Uses: {invite.uses or 0} / {max_uses}\n"
                f"Channel: {channel_mention}\n"
                f"Expires: {expires}"
            )
            
            embed.add_field(
                name=f"discord.gg/{invite.code}",
                value=value,
                inline=False
            )
        
        if len(user_invites) > 10:
            embed.set_footer(text=f"Showing top 10 of {len(user_invites)} codes")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="invitedlist", description="View list of members you have invited")
    async def invited_list(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Display a list of members invited by a user."""
        target = member or ctx.author
        
        if not isinstance(ctx.guild, discord.Guild):
            await ctx.send("This command can only be used in a server.")
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT user_id, invite_code, joined_at, left_at, is_fake
                FROM invites
                WHERE guild_id = ? AND inviter_id = ?
                ORDER BY joined_at DESC
                LIMIT 25
            """, (ctx.guild.id, target.id)) as cursor:
                rows = await cursor.fetchall()
        
        rows_list = list(rows)
        if not rows_list:
            embed = discord.Embed(
                title="Invited Members",
                description=f"{target.mention} has not invited anyone yet.",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title=f"Invited Members - {target.display_name}",
            description=f"Total Records: {len(rows_list)}",
            color=discord.Color.blue()
        )
        
        active_members = []
        left_members = []
        
        for row in rows_list:
            user_id, code, joined_at, left_at, is_fake = row
            member_obj = ctx.guild.get_member(user_id)
            
            if member_obj:
                status = "Active"
                if is_fake:
                    status += " (Flagged)"
                active_members.append(f"<@{user_id}> - {status}")
            else:
                left_members.append(f"<@{user_id}> - Left")
        
        if active_members:
            embed.add_field(
                name=f"Active Members ({len(active_members)})",
                value="\n".join(active_members[:15]) or "None",
                inline=False
            )
        
        if left_members:
            embed.add_field(
                name=f"Left Members ({len(left_members)})",
                value="\n".join(left_members[:10]) or "None",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="inviter", description="Check who invited a specific member")
    async def inviter(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Display who invited a specific member to the server."""
        target = member or ctx.author
        
        if not isinstance(ctx.guild, discord.Guild):
            await ctx.send("This command can only be used in a server.")
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT inviter_id, invite_code, joined_at, is_fake
                FROM invites
                WHERE guild_id = ? AND user_id = ?
                ORDER BY joined_at DESC LIMIT 1
            """, (ctx.guild.id, target.id)) as cursor:
                row = await cursor.fetchone()
        
        embed = discord.Embed(
            title="Invite Information",
            color=discord.Color.blue()
        )
        
        if row:
            inviter_id, code, joined_at, is_fake = row
            inviter = ctx.guild.get_member(inviter_id) or await self.bot.fetch_user(inviter_id)
            
            embed.description = f"Invitation details for {target.mention}"
            embed.add_field(name="Invited By", value=inviter.mention if inviter else f"User ID: {inviter_id}", inline=True)
            embed.add_field(name="Invite Code", value=f"`{code}`", inline=True)
            embed.add_field(name="Joined At", value=f"<t:{int(datetime.fromisoformat(joined_at).timestamp())}:F>", inline=False)
            
            if is_fake:
                embed.add_field(
                    name="Status",
                    value="Flagged as potential fake invite (account < 7 days old)",
                    inline=False
                )
        else:
            embed.description = f"No invite information found for {target.mention}.\nThey may have joined before invite tracking was enabled."
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="inviteleaderboard", description="View the server's invite leaderboard")
    async def invite_leaderboard(self, ctx: commands.Context):
        """Display the top inviters in the server."""
        if not isinstance(ctx.guild, discord.Guild):
            await ctx.send("This command can only be used in a server.")
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT user_id, total_invites, left_invites, fake_invites
                FROM invite_stats
                WHERE guild_id = ?
                ORDER BY (total_invites - left_invites - fake_invites) DESC
                LIMIT 15
            """, (ctx.guild.id,)) as cursor:
                rows = await cursor.fetchall()
        
        if not rows:
            embed = discord.Embed(
                title="Invite Leaderboard",
                description="No invite data available yet.",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title=f"Invite Leaderboard - {ctx.guild.name}",
            description="Top members by valid invites",
            color=discord.Color.gold()
        )
        
        leaderboard_text = []
        for idx, row in enumerate(rows, 1):
            user_id, total, left, fake = row
            valid = total - left - fake
            
            if valid <= 0:
                continue
            
            member = ctx.guild.get_member(user_id)
            name = member.display_name if member else f"User {user_id}"
            
            medal = ["🥇", "🥈", "🥉"][idx-1] if idx <= 3 else f"`{idx}.`"
            leaderboard_text.append(
                f"{medal} **{name}**\n"
                f"Valid: {valid} | Total: {total} | Left: {left} | Fake: {fake}"
            )
        
        if leaderboard_text:
            current_desc = embed.description or ""
            embed.description = current_desc + "\n\n" + "\n\n".join(leaderboard_text)
        else:
            embed.description = "No valid invites recorded yet."
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="syncinvites", description="Synchronize invite cache with current server invites")
    @commands.has_permissions(manage_guild=True)
    async def sync_invites(self, ctx: commands.Context):
        """Manually sync invite cache (requires Manage Server permission)."""
        if not isinstance(ctx.guild, discord.Guild):
            await ctx.send("This command can only be used in a server.")
            return
        
        await ctx.defer()
        
        try:
            await self.cache_invites(ctx.guild)
            
            invite_count = len(self.invite_cache.get(ctx.guild.id, {}))
            
            embed = discord.Embed(
                title="Invite Synchronization",
                description=f"Successfully synchronized {invite_count} invite codes.",
                color=discord.Color.green()
            )
            
            await ctx.send(embed=embed)
        except discord.Forbidden:
            embed = discord.Embed(
                title="Synchronization Failed",
                description="I don't have permission to view server invites.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="invitedocs", description="View invite tracker documentation and GitHub repository")
    async def documentation(self, ctx: commands.Context):
        """Display documentation and links for the invite tracking system."""
        embed = discord.Embed(
            title="Invite Tracker Documentation",
            description=(
                "Professional invite tracking system for Discord servers.\n\n"
                "Track member invites, maintain leaderboards, and analyze invitation patterns."
            ),
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Available Commands",
            value=(
                "`/invitecodes` - View your invite codes and usage\n"
                "`/invitedlist` - List members you've invited\n"
                "`/inviter` - Check who invited a member\n"
                "`/inviteleaderboard` - Server invite rankings\n"
                "`/syncinvites` - Sync invite cache (Admin)\n"
                "`/invitedocs` - View this documentation"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Features",
            value=(
                "• Real-time invite tracking\n"
                "• Fake invite detection (accounts < 7 days)\n"
                "• Leave tracking and statistics\n"
                "• Detailed analytics and leaderboards\n"
                "• Invite code usage monitoring"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Statistics Explained",
            value=(
                "**Total**: All-time invites by this user\n"
                "**Valid**: Active members still in server\n"
                "**Left**: Invited members who left\n"
                "**Fake**: Flagged suspicious invites"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Links",
            value=(
                "[GitHub Repository](https://github.com/TheCodeVerseHub/Eigen-Bot)\n"
                "[Report Issues](https://github.com/TheCodeVerseHub/Eigen-Bot/issues)\n"
                "[Documentation](https://github.com/TheCodeVerseHub/Eigen-Bot#readme)"
            ),
            inline=False
        )
        
        embed.set_footer(text="Eigen Bot • Invite Tracking System v1.0")
        
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    """Setup the invite tracker cog."""
    await bot.add_cog(InviteTracker(bot))
