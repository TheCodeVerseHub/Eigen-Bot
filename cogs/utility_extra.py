import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.utils import escape_markdown, escape_mentions
import random
import re
import math
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Union

TIME_REGEX = re.compile(r"(\d+)([smhdw])")
TIME_MULTIPLIERS = {
    's': 1,
    'm': 60,
    'h': 3600,
    'd': 86400,
    'w': 604800
}

class Reminder:
    __slots__ = ("user_id", "channel_id", "end_time", "message")
    def __init__(self, user_id: int, channel_id: int, end_time: datetime, message: str):
        self.user_id = user_id
        self.channel_id = channel_id
        self.end_time = end_time
        self.message = message

class UtilityExtra(commands.Cog):
    """Additional utility commands (emotes, inviteinfo, membercount, randomcolor, remindme, roll)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.reminders: List[Reminder] = []
        self.reminder_checker.start()

    def cog_unload(self):
        self.reminder_checker.cancel()

    # ============ INTERNAL HELPERS ============
    def parse_time(self, time_str: str) -> Optional[int]:
        total = 0
        for amount, unit in TIME_REGEX.findall(time_str.lower()):
            total += int(amount) * TIME_MULTIPLIERS[unit]
        return total if total > 0 else None

    # ============ COMMANDS ============
    @commands.hybrid_command(name="emotes", description="Get a list of server emojis. Optional search.", help="Get a list of server emojis. Optional search.")
    @app_commands.describe(search="Optional search text")
    @commands.guild_only()
    async def emotes(self, ctx: commands.Context, *, search: Optional[str] = None):
        if not ctx.guild or not ctx.guild.emojis:
            return await ctx.reply("No custom emojis in this server.")
        emojis = ctx.guild.emojis
        if search:
            search_lower = search.lower()
            emojis = [e for e in emojis if search_lower in e.name.lower()]
            if not emojis:
                return await ctx.reply("No emojis match that search.")
        display = " ".join(str(e) for e in emojis[:100])  # limit to avoid overflow
        await ctx.reply(f"Emojis ({len(emojis)}):\n{display}")

    @commands.hybrid_command(name="membercount", description="Get the member count of the current server.", help="Get the member count of the current server.")
    @commands.guild_only()
    @app_commands.guild_only()
    async def membercount(self, ctx: commands.Context):
        if ctx.guild is None:
            return await ctx.reply("This command can only be used in a server.")
        await ctx.reply(f"Member Count: {ctx.guild.member_count}")

    @commands.hybrid_command(name="randomcolor", description="Generate a random hex color.", help="Generate a random hex color.")
    async def randomcolor(self, ctx: commands.Context):
        value = random.randint(0, 0xFFFFFF)
        hex_code = f"#{value:06X}"
        embed = discord.Embed(title="Random Color", description=hex_code, color=value)
        embed.set_thumbnail(url=f"https://singlecolorimage.com/get/{hex_code[1:]}/400x100")
        await ctx.reply(embed=embed)

    @commands.command(name="roll", help="Roll dice. Usage: ?roll [size] [count]")
    async def roll(self, ctx: commands.Context, size: int = 6, count: int = 1):
        if size < 2 or size > 1000:
            return await ctx.reply("Size must be between 2 and 1000.")
        if count < 1 or count > 20:
            return await ctx.reply("Count must be between 1 and 20.")
        rolls = [random.randint(1, size) for _ in range(count)]
        total = sum(rolls)
        await ctx.reply(f"Rolled {count}d{size}: {', '.join(map(str, rolls))} (Total: {total})")

    @commands.hybrid_command(name="remindme", description="Set a reminder. Example: /remindme 10m Submit report", help="Set a reminder. Example: /remindme 10m Submit report")
    @app_commands.describe(time="Time span like 10m, 2h, 1d", reminder="Reminder text")
    async def remindme(self, ctx: commands.Context, time: str, *, reminder: str):
        seconds = self.parse_time(time)
        if not seconds or seconds > 60 * 60 * 24 * 30:  # limit 30 days
            return await ctx.reply("Invalid time. Use formats like 10m, 2h, 1d (max 30d).")
        end_time = datetime.now(timezone.utc) + timedelta(seconds=seconds)
        self.reminders.append(Reminder(ctx.author.id, ctx.channel.id, end_time, reminder))
        await ctx.reply(f"Reminder set for <t:{int(end_time.timestamp())}:R>.")

    @tasks.loop(seconds=30)
    async def reminder_checker(self):
        if not self.reminders:
            return
        now = datetime.now(timezone.utc)
        due = [r for r in self.reminders if r.end_time <= now]
        if not due:
            return
        for r in due:
            channel = self.bot.get_channel(r.channel_id)
            # Only attempt to send if the channel is a type that supports sending messages
            if isinstance(channel, (discord.TextChannel, discord.Thread, discord.DMChannel, discord.GroupChannel)):
                try:
                    await channel.send(f"<@{r.user_id}> Reminder: {r.message}")
                except Exception:
                    pass
        self.reminders = [r for r in self.reminders if r.end_time > now]

    @reminder_checker.before_loop
    async def before_reminder_checker(self):
        await self.bot.wait_until_ready()

    @commands.command(name="inviteinfo", help="Get information about a Discord invite.")
    async def inviteinfo(self, ctx: commands.Context, code: str):
        # Extract code if full URL
        if "discord.gg/3xKFvKhuGR" in code:
            code = code.rsplit("/", 1)[-1]
        try:
            invite = await self.bot.fetch_invite(code, with_counts=True)
        except Exception:
            return await ctx.reply("Invalid or expired invite.")
        embed = discord.Embed(title="Invite Info", color=discord.Color.blurple())
        embed.add_field(name="Code", value=invite.code, inline=True)
        if invite.guild:
            # Use getattr to avoid attribute errors when guild is a partial/Object without these attributes
            embed.add_field(name="Server", value=getattr(invite.guild, "name", "Unknown"), inline=True)
            description = getattr(invite.guild, "description", None)
            if description:
                embed.add_field(name="Description", value=description[:200], inline=False)
        if invite.approximate_member_count:
            embed.add_field(name="Members", value=str(invite.approximate_member_count), inline=True)
        if invite.expires_at:
            embed.add_field(name="Expires", value=f"<t:{int(invite.expires_at.timestamp())}:R>", inline=True)
        await ctx.reply(embed=embed)

    @commands.hybrid_command(name="avatar", description="Get a user's avatar.", help="Get a user's avatar.")
    @app_commands.describe(user="The user to get the avatar of")
    async def avatar(self, ctx: commands.Context, user: Optional[Union[discord.Member, discord.User]] = None):
        target = user or ctx.author
        embed = discord.Embed(title=f"{target.display_name}'s Avatar", color=discord.Color.random())
        embed.set_image(url=target.display_avatar.url)
        await ctx.reply(embed=embed)

    @commands.hybrid_command(name="serverinfo", description="Get server info/stats.", help="Get server info/stats.")
    @commands.guild_only()
    async def serverinfo(self, ctx: commands.Context):
        if ctx.guild is None:
            return await ctx.reply("This command can only be used in a server.")
        guild = ctx.guild
        embed = discord.Embed(title=f"Server Info: {guild.name}", color=discord.Color.blue())
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        owner_mention = guild.owner.mention if guild.owner is not None else f"<@{guild.owner_id}>"
        embed.add_field(name="Owner", value=owner_mention, inline=True)
        embed.add_field(name="ID", value=str(guild.id), inline=True)
        embed.add_field(name="Created At", value=discord.utils.format_dt(guild.created_at, 'R'), inline=True)
        embed.add_field(name="Members", value=str(guild.member_count), inline=True)
        embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
        embed.add_field(name="Channels", value=str(len(guild.channels)), inline=True)
        
        await ctx.reply(embed=embed)

    @commands.hybrid_command(name="color", description="Show a color using hex.", help="Show a color using hex.")
    @app_commands.describe(hex_code="Hex color code (e.g., #FF0000)")
    async def color(self, ctx: commands.Context, hex_code: str):
        hex_code = hex_code.strip('#')
        try:
            color_int = int(hex_code, 16)
        except ValueError:
            return await ctx.reply("Invalid hex code.")
            
        if color_int > 0xFFFFFF:
             return await ctx.reply("Invalid hex code range.")

        embed = discord.Embed(title=f"Color #{hex_code.upper()}", color=color_int)
        embed.set_thumbnail(url=f"https://singlecolorimage.com/get/{hex_code}/400x100")
        await ctx.reply(embed=embed)

    @commands.command(name="distance", help="Get the distance between two sets of coordinates (x1,y1 x2,y2).")
    async def distance(self, ctx: commands.Context, coords1: str, coords2: str):
        try:
            x1, y1 = map(float, coords1.split(','))
            x2, y2 = map(float, coords2.split(','))
            dist = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
            await ctx.reply(f"Distance between ({x1},{y1}) and ({x2},{y2}) is **{dist:.2f}**")
        except ValueError:
            await ctx.reply("Invalid format. Use `x,y` for coordinates. Example: `?distance 0,0 3,4`")
            
    @commands.command(name='grep', aliases=['search', 'find'], help='Search for a pattern in the last N messages. Usage: ?grep [-i] <pattern> [limit]')
    @commands.guild_only()
    async def grep(self, ctx: commands.Context, *args):
        # use: ?grep [-i] <pattern> [limit]
        if not ctx.guild:
            return await ctx.reply("This command can only be used in a server.")

        insensitive = False
        clean_args = []

        for arg in args:
            if arg == '-i':
                insensitive = True
            else:
                clean_args.append(arg)

        if not clean_args:
            return await ctx.reply("Please provide a pattern to search for.")

        pattern = clean_args[0]
        # Keep a safe-to-display version of the user pattern.
        safe_pattern = escape_mentions(escape_markdown(pattern))
        limit = 50
        
        if len(clean_args) > 1:
            try:
                parsed_limit = int(clean_args[1])
                limit = max(1, min(parsed_limit, 100))
            except ValueError:
                pass

        flags = re.IGNORECASE if insensitive else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error:
            regex = re.compile(re.escape(pattern), flags)

        matches = []
        async for msg in ctx.channel.history(limit=limit + 10):
            if len(matches) >= limit: 
                break
            if msg.id == ctx.message.id:
                continue
            if msg.author.bot and 'grep result' in msg.content:
                continue

            if regex.search(msg.content):
                matches.append((msg.author.display_name, msg.content, msg.jump_url))

        if not matches:
            return await ctx.reply(
                f"No matches found for `{safe_pattern}` in the recently checked messages.",
                allowed_mentions=discord.AllowedMentions.none(),
            )

        results = []
        # fix: d7a4ff1
        for author_name, content, jump_url in matches:
            safe_author_name = escape_mentions(escape_markdown(author_name))
            clean_content = escape_mentions(escape_markdown(content.replace('\n', ' ')))
            if len(clean_content) > 50:
                clean_content = clean_content[:50] + '...'
                
            line = f"[{safe_author_name}]: {clean_content} ([Jump]({jump_url}))"
            results.append(line)

        header = f"Found {len(matches)} matches for `{safe_pattern}`:\n"
        output_body = "\n".join(results)

        if len(output_body) > 1900:
            output_body = output_body[:1900] + '\n...(truncated)'

        final_output = header + output_body
        await ctx.reply(final_output, allowed_mentions=discord.AllowedMentions.none())

async def setup(bot: commands.Bot):
    await bot.add_cog(UtilityExtra(bot))

