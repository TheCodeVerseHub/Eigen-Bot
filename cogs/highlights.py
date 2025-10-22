import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime, timezone
import re

DB_PATH = Path("data/highlights.db")

class Highlights(commands.Cog):
    """Get notified when specific phrases are said in the server."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cache: Dict[int, Dict[int, List[str]]] = {}  # guild_id -> {user_id: [phrases]}

    async def cog_load(self):
        await self.init_db()
        await self.load_cache()

    async def init_db(self):
        DB_PATH.parent.mkdir(exist_ok=True)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS highlights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    phrase TEXT NOT NULL,
                    added_at TEXT NOT NULL,
                    UNIQUE(guild_id, user_id, phrase)
                )
            """)
            await db.commit()

    async def load_cache(self):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT guild_id, user_id, phrase FROM highlights")
            rows = await cursor.fetchall()
            loaded = 0
            for guild_id, user_id, phrase in rows:
                self.cache.setdefault(guild_id, {}).setdefault(user_id, []).append(phrase)
                loaded += 1
            print(f"[Highlights] Loaded {loaded} phrases into cache.")

    # ================= COMMAND GROUP =================
    @commands.hybrid_group(name="highlights", description="Manage your highlight phrases.")
    @commands.guild_only()
    async def highlights_group(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            return await ctx.send("Use /highlights add <phrase> or /highlights list")

    @highlights_group.command(name="add", description="Add a phrase to your highlights.")
    @app_commands.describe(phrase="Phrase to highlight on. 3-100 chars.")
    async def highlights_add(self, ctx: commands.Context, *, phrase: str):
        if not ctx.guild:
            return
        phrase_clean = phrase.strip()
        if len(phrase_clean) < 3 or len(phrase_clean) > 100:
            return await ctx.reply("Phrase length must be between 3 and 100 characters.")
        if "@" in phrase_clean:
            return await ctx.reply("Mentions are not allowed in highlight phrases.")
        # Save
        async with aiosqlite.connect(DB_PATH) as db:
            try:
                await db.execute(
                    "INSERT INTO highlights (guild_id, user_id, phrase, added_at) VALUES (?, ?, ?, ?)",
                    (ctx.guild.id, ctx.author.id, phrase_clean.lower(), datetime.now(timezone.utc).isoformat())
                )
                await db.commit()
            except aiosqlite.IntegrityError:
                return await ctx.reply("You already have that phrase.")
        self.cache.setdefault(ctx.guild.id, {}).setdefault(ctx.author.id, []).append(phrase_clean.lower())
        await ctx.reply(f"Added highlight phrase: '{phrase_clean}'.")

    @highlights_group.command(name="remove", description="Remove one of your highlight phrases.")
    @app_commands.describe(phrase="Exact phrase to remove.")
    async def highlights_remove(self, ctx: commands.Context, *, phrase: str):
        if not ctx.guild:
            return
        phrase_clean = phrase.strip().lower()
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "DELETE FROM highlights WHERE guild_id = ? AND user_id = ? AND phrase = ?",
                (ctx.guild.id, ctx.author.id, phrase_clean)
            )
            await db.commit()
        if ctx.guild.id in self.cache and ctx.author.id in self.cache[ctx.guild.id]:
            try:
                self.cache[ctx.guild.id][ctx.author.id].remove(phrase_clean)
            except ValueError:
                pass
        await ctx.reply(f"Removed highlight phrase: '{phrase_clean}'.")

    @highlights_group.command(name="list", description="List your highlight phrases.")
    async def highlights_list(self, ctx: commands.Context):
        if not ctx.guild:
            return
        phrases = self.cache.get(ctx.guild.id, {}).get(ctx.author.id, [])
        if not phrases:
            return await ctx.reply("You have no highlight phrases set.")
        display = "\n".join(f"• {p}" for p in phrases[:30])
        await ctx.reply(f"Your highlight phrases ({len(phrases)}):\n{display}")

    # ================= LISTENER =================
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild or not message.content:
            return
        guild_cache = self.cache.get(message.guild.id)
        if not guild_cache:
            return
        content_lower = message.content.lower()
        for user_id, phrases in guild_cache.items():
            if user_id == message.author.id:
                continue  # don't notify on own messages
            for phrase in phrases:
                if phrase in content_lower:
                    user = message.guild.get_member(user_id)
                    if user:
                        try:
                            await user.send(
                                f"Highlight: '{phrase}' mentioned in #{message.channel} in {message.guild.name}. \n"
                                f"Message: {message.content[:1800]}\nLink: {message.jump_url}"
                            )
                        except Exception:
                            pass
                    break

async def setup(bot: commands.Bot):
    await bot.add_cog(Highlights(bot))
