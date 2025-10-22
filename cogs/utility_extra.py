import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict

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
    @commands.hybrid_command(name="emotes", help="Get a list of server emojis. Optional search.")
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

    @commands.hybrid_command(name="membercount", help="Get the member count of the current server.")
    @commands.guild_only()
    async def membercount(self, ctx: commands.Context):
        if ctx.guild is None:
            return await ctx.reply("This command can only be used in a server.")
        await ctx.reply(f"Member Count: {ctx.guild.member_count}")

    @commands.hybrid_command(name="randomcolor", help="Generate a random hex color.")
    async def randomcolor(self, ctx: commands.Context):
        value = random.randint(0, 0xFFFFFF)
        hex_code = f"#{value:06X}"
        embed = discord.Embed(title="Random Color", description=hex_code, color=value)
        embed.set_thumbnail(url=f"https://singlecolorimage.com/get/{hex_code[1:]}/400x100")
        await ctx.reply(embed=embed)

    @commands.hybrid_command(name="roll", help="Roll dice. Usage: /roll size count")
    @app_commands.describe(size="Number of faces per die (e.g., 6)", count="Number of dice (1-20)")
    async def roll(self, ctx: commands.Context, size: int = 6, count: int = 1):
        if size < 2 or size > 1000:
            return await ctx.reply("Size must be between 2 and 1000.")
        if count < 1 or count > 20:
            return await ctx.reply("Count must be between 1 and 20.")
        rolls = [random.randint(1, size) for _ in range(count)]
        total = sum(rolls)
        await ctx.reply(f"Rolled {count}d{size}: {', '.join(map(str, rolls))} (Total: {total})")

    @commands.hybrid_command(name="remindme", help="Set a reminder. Example: /remindme 10m Submit report")
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

    @commands.hybrid_command(name="inviteinfo", help="Get information about a Discord invite.")
    @app_commands.describe(code="Invite code or full URL")
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

async def setup(bot: commands.Bot):
    await bot.add_cog(UtilityExtra(bot))
