import discord
from discord.ext import commands
import aiosqlite
from utils.helpers import EmbedBuilder

def is_staff():
    async def predicate(ctx):
        if ctx.author.id == ctx.bot.config.owner_id:
            return True
        return ctx.author.guild_permissions.view_audit_log
    return commands.check(predicate)

class Chowkidar(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.watched_users = set()
        self.log_channel_id = None

    async def cog_load(self):
        async with aiosqlite.connect("botdata.db") as db:
            await db.execute("CREATE TABLE IF NOT EXISTS chowkidar_config (guild_id INTEGER PRIMARY KEY, channel_id INTEGER)")
            await db.execute("CREATE TABLE IF NOT EXISTS chowkidar_tracked (user_id INTEGER PRIMARY KEY)")
            await db.commit()
            
            async with db.execute("SELECT channel_id FROM chowkidar_config LIMIT 1") as cursor:
                row = await cursor.fetchone()
                if row:
                    self.log_channel_id = row[0]
            
            async with db.execute("SELECT user_id FROM chowkidar_tracked") as cursor:
                rows = await cursor.fetchall()
                self.watched_users = {row[0] for row in rows}

    async def send_log(self, embed: discord.Embed):
        if not self.log_channel_id:
            return
        channel = self.bot.get_channel(self.log_channel_id)
        if channel:
            await channel.send(embed=embed)

    @commands.hybrid_command(name="setwlchannel", description="Set the current channel as the watchlog channel.")
    @is_staff()
    async def setwlchannel(self, ctx):
        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.send(embed=EmbedBuilder.error_embed("Invalid Channel", "This command can only be used in a standard text channel."))
            return
        
        self.log_channel_id = ctx.channel.id
        async with aiosqlite.connect("botdata.db") as db:
            await db.execute("INSERT OR REPLACE INTO chowkidar_config (guild_id, channel_id) VALUES (?, ?)", (ctx.guild.id, ctx.channel.id))
            await db.commit()
        
        await ctx.send(embed=EmbedBuilder.success_embed("Channel Configured", f"Watchlog channel has been set to {ctx.channel.mention}."))

    @commands.hybrid_command(name="chowkidar", description="Start tracking a user.")
    @is_staff()
    async def chowkidar(self, ctx, user: discord.Member):
        if user.id == self.bot.user.id:
            await ctx.send(embed=EmbedBuilder.error_embed("Invalid Target", "The bot cannot be tracked."))
            return
        
        if user.guild_permissions.view_audit_log and ctx.author.id != ctx.guild.owner_id:
            await ctx.send(embed=EmbedBuilder.error_embed("Invalid Target", "You cannot track another staff member."))
            return

        self.watched_users.add(user.id)
        async with aiosqlite.connect("botdata.db") as db:
            await db.execute("INSERT OR IGNORE INTO chowkidar_tracked (user_id) VALUES (?)", (user.id,))
            await db.commit()

        await ctx.send(embed=EmbedBuilder.success_embed("Tracking Initiated", f"Now tracking actions for {user.mention}."))

    @commands.hybrid_command(name="endwl", description="Stop tracking a user.")
    @is_staff()
    async def endwl(self, ctx, user: discord.Member):
        self.watched_users.discard(user.id)
        async with aiosqlite.connect("botdata.db") as db:
            await db.execute("DELETE FROM chowkidar_tracked WHERE user_id = ?", (user.id,))
            await db.commit()
            
        await ctx.send(embed=EmbedBuilder.success_embed("Tracking Terminated", f"Stopped tracking {user.mention}."))

    @commands.hybrid_command(name="purgewl", description="Delete all watchlogs for a specific user.")
    @is_staff()
    async def purgewl(self, ctx, user: discord.Member):
        if not self.log_channel_id:
            await ctx.send(embed=EmbedBuilder.error_embed("Configuration Error", "Watchlog channel is not set."))
            return
        
        log_channel = self.bot.get_channel(self.log_channel_id)
        if not log_channel:
            await ctx.send(embed=EmbedBuilder.error_embed("Configuration Error", "Watchlog channel could not be found."))
            return

        await ctx.defer()
        to_delete = []
        
        async for msg in log_channel.history(limit=1000):
            if msg.author == self.bot.user and msg.embeds:
                embed = msg.embeds[0]
                if embed.footer and embed.footer.text and f"ID: {user.id}" in embed.footer.text:
                    to_delete.append(msg)

        if to_delete:
            for i in range(0, len(to_delete), 100):
                await log_channel.delete_messages(to_delete[i:i+100])
                
        await ctx.send(embed=EmbedBuilder.success_embed("Purge Complete", f"Deleted {len(to_delete)} log entries for {user.mention}."))

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.author.id not in self.watched_users:
            return

        action = "Message Replied" if message.reference else "Message Sent"
        embed = discord.Embed(title=action, description=message.content, color=discord.Color.blue(), timestamp=message.created_at)
        embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
        embed.add_field(name="Channel", value=message.channel.mention)
        embed.add_field(name="Message ID", value=str(message.id))
        embed.add_field(name="Message Link", value=f"[Jump to Message]({message.jump_url})", inline=False)
        embed.set_footer(text=f"User ID: {message.author.id}")
        
        await self.send_log(embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if after.author.bot or after.author.id not in self.watched_users or before.content == after.content:
            return

        embed = discord.Embed(title="Message Edited", color=discord.Color.yellow(), timestamp=discord.utils.utcnow())
        embed.set_author(name=str(after.author), icon_url=after.author.display_avatar.url)
        embed.add_field(name="Before", value=before.content or "None", inline=False)
        embed.add_field(name="After", value=after.content or "None", inline=False)
        embed.add_field(name="Channel", value=after.channel.mention)
        embed.add_field(name="Message ID", value=str(after.id))
        embed.add_field(name="Message Link", value=f"[Jump to Message]({after.jump_url})", inline=False)
        embed.set_footer(text=f"User ID: {after.author.id}")
        
        await self.send_log(embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot or message.author.id not in self.watched_users:
            return

        embed = discord.Embed(title="Message Deleted", description=message.content, color=discord.Color.red(), timestamp=discord.utils.utcnow())
        embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
        embed.add_field(name="Channel", value=message.channel.mention)
        embed.add_field(name="Message ID", value=str(message.id))
        embed.set_footer(text=f"User ID: {message.author.id}")
        
        await self.send_log(embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot or member.id not in self.watched_users:
            return

        embed = discord.Embed(color=discord.Color.purple(), timestamp=discord.utils.utcnow())
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        embed.set_footer(text=f"User ID: {member.id}")

        if before.channel is None and after.channel is not None:
            embed.title = "Joined Voice Channel"
            embed.add_field(name="Channel", value=after.channel.mention)
        elif before.channel is not None and after.channel is None:
            embed.title = "Left Voice Channel"
            embed.add_field(name="Channel", value=before.channel.mention)
        elif before.channel != after.channel:
            embed.title = "Moved Voice Channel"
            embed.add_field(name="From", value=before.channel.mention)
            embed.add_field(name="To", value=after.channel.mention)
        else:
            return

        await self.send_log(embed)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id not in self.watched_users:
            return
            
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
            
        member = guild.get_member(payload.user_id)
        if not member or member.bot:
            return

        channel = guild.get_channel(payload.channel_id)
        message_link = f"https://discord.com/channels/{payload.guild_id}/{payload.channel_id}/{payload.message_id}"

        embed = discord.Embed(title="Reaction Added", color=discord.Color.teal(), timestamp=discord.utils.utcnow())
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        embed.add_field(name="Emoji", value=str(payload.emoji))
        embed.add_field(name="Channel", value=channel.mention if channel else str(payload.channel_id))
        embed.add_field(name="Message ID", value=str(payload.message_id))
        embed.add_field(name="Message Link", value=f"[Jump to Message]({message_link})", inline=False)
        embed.set_footer(text=f"User ID: {member.id}")
        
        await self.send_log(embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if member.id not in self.watched_users:
            return

        embed = discord.Embed(title="Left Server", color=discord.Color.dark_grey(), timestamp=discord.utils.utcnow())
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        embed.set_footer(text=f"User ID: {member.id}")
        
        await self.send_log(embed)
        
        self.watched_users.discard(member.id)
        async with aiosqlite.connect("botdata.db") as db:
            await db.execute("DELETE FROM chowkidar_tracked WHERE user_id = ?", (member.id,))
            await db.commit()

async def setup(bot):
    await bot.add_cog(Chowkidar(bot))

