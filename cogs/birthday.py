from datetime import datetime, time, timezone
from pathlib import Path

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands, tasks


class BirthdaySystem(commands.Cog):
    """
    Birthday System
    Allows users to set their birthday and receive wishes in DMs.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_path = Path("data/birthdays.db")
        # Start the task
        self.check_birthdays_task.start()

    async def cog_load(self):
        """Initialize the database when the cog loads"""
        await self.init_db()

    def cog_unload(self):
        """Cancel the task when the cog unloads"""
        self.check_birthdays_task.cancel()

    async def init_db(self):
        """Initialize the birthday database"""
        self.db_path.parent.mkdir(exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS birthdays (
                    user_id INTEGER PRIMARY KEY,
                    day INTEGER,
                    month INTEGER,
                    year INTEGER
                )
            """)
            await db.commit()

    @commands.hybrid_command(
        name="birthday",
        help="Set your birthday to receive a wish!",
        usage="birthday <day> <month> <year>"
    )
    @app_commands.describe(
        day="Day of birth (1-31)",
        month="Month of birth (1-12)",
        year="Year of birth (e.g. 2000)"
    )
    async def set_birthday(self, ctx: commands.Context, day: int, month: int, year: int):
        """Set your birthday"""
        try:
            # Validate date
            datetime(year, month, day)
        except ValueError:
            await ctx.send("❌ Invalid date provided. Please check the day, month, and year.", ephemeral=True)
            return

        current_year = datetime.now().year
        if year > current_year or year < 1900:
             await ctx.send("❌ Invalid year provided.", ephemeral=True)
             return

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO birthdays (user_id, day, month, year)
                VALUES (?, ?, ?, ?)
            """, (ctx.author.id, day, month, year))
            await db.commit()

        embed = discord.Embed(
            title="🎂 Birthday Set!",
            description=f"I've saved your birthday as **{day}/{month}/{year}**.\nI'll send you a wish in your DMs on your special day!",
            color=discord.Color.purple()
        )
        await ctx.send(embed=embed, ephemeral=True)

    @tasks.loop(time=time(hour=0, minute=0, tzinfo=timezone.utc))
    async def check_birthdays_task(self):
        """Check for birthdays daily"""
        now = datetime.now(timezone.utc)
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT user_id, year FROM birthdays WHERE day = ? AND month = ?", (now.day, now.month))
            rows = await cursor.fetchall()

            for user_id, year in rows:
                try:
                    # Try to get user from cache first, then fetch
                    user = self.bot.get_user(user_id)
                    if not user:
                        user = await self.bot.fetch_user(user_id)
                    
                    if user:
                        age = now.year - year
                        
                        embed = discord.Embed(
                            title="🎉 Happy Birthday! 🎂",
                            description=f"Wishing you a fantastic day as you turn **{age}**!",
                            color=discord.Color.gold()
                        )
                        embed.set_footer(text="From your friendly bot")
                        
                        try:
                            await user.send(embed=embed)
                        except discord.Forbidden:
                            print(f"Could not DM birthday wish to user {user_id}")
                except Exception as e:
                    print(f"Failed to process birthday for {user_id}: {e}")

    @check_birthdays_task.before_loop
    async def before_check_birthdays(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(BirthdaySystem(bot))
