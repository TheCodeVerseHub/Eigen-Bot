import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

DB_PATH = Path("data/tags.db")

class Tags(commands.Cog):
    """Create, retrieve, edit, and delete short text tags."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        await self.init_db()

    async def init_db(self):
        DB_PATH.parent.mkdir(exist_ok=True)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    content TEXT NOT NULL,
                    author_id INTEGER NOT NULL,
                    uses INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(guild_id, name)
                )
            """)
            await db.commit()

    @commands.hybrid_group(name="tags", description="List or manage tags.")
    @commands.guild_only()
    async def tags_group(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send("Use /tags list or /tag <name>")

    @commands.hybrid_command(name="tag", help="Get a tag by name.")
    @app_commands.describe(name="Tag name to fetch")
    @commands.guild_only()
    async def tag(self, ctx: commands.Context, name: str):
        if ctx.guild is None:
            return await ctx.reply("This command can only be used in a server.")
        guild_id = ctx.guild.id
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT content, uses FROM tags WHERE guild_id = ? AND name = ?",
                (guild_id, name.lower())
            )
            row = await cursor.fetchone()
            if not row:
                return await ctx.reply("Tag not found.")
            content, uses = row
            await db.execute(
                "UPDATE tags SET uses = ? WHERE guild_id = ? AND name = ?",
                (uses + 1, guild_id, name.lower())
            )
            await db.commit()
        await ctx.reply(content[:2000])

    @tags_group.command(name="create", description="Create a new tag.")
    @app_commands.describe(name="Tag name", content="Tag content")
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def tags_create(self, ctx: commands.Context, name: str, *, content: str):
        guild = ctx.guild
        if guild is None:
            return await ctx.reply("This command can only be used in a server.")
        if len(name) > 50:
            return await ctx.reply("Tag name too long (max 50).")
        if len(content) > 2000:
            return await ctx.reply("Content too long (max 2000).")
        async with aiosqlite.connect(DB_PATH) as db:
            try:
                await db.execute("INSERT INTO tags (guild_id, name, content, author_id, uses, created_at, updated_at) VALUES (?, ?, ?, ?, 0, ?, ?)",
                                 (guild.id, name.lower(), content, ctx.author.id, datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat()))
                await db.commit()
            except aiosqlite.IntegrityError:
                return await ctx.reply("A tag with that name already exists.")
        await ctx.reply(f"Created tag '{name}'.")
    @tags_group.command(name="edit", description="Edit an existing tag.")
    @app_commands.describe(name="Tag name", content="New content")
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def tags_edit(self, ctx: commands.Context, name: str, *, content: str):
        guild = ctx.guild
        if guild is None:
            return await ctx.reply("This command can only be used in a server.")
        if len(content) > 2000:
            return await ctx.reply("Content too long (max 2000).")
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT 1 FROM tags WHERE guild_id = ? AND name = ?", (guild.id, name.lower()))
            if not await cursor.fetchone():
                return await ctx.reply("Tag not found.")
            await db.execute(
                "UPDATE tags SET content = ?, updated_at = ? WHERE guild_id = ? AND name = ?",
                (content, datetime.now(timezone.utc).isoformat(), guild.id, name.lower())
            )
            await db.commit()
        await ctx.reply(f"Updated tag '{name}'.")
    
    @tags_group.command(name="delete", description="Delete a tag.")
    @app_commands.describe(name="Tag name")
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def tags_delete(self, ctx: commands.Context, name: str):
        guild = ctx.guild
        if guild is None:
            return await ctx.reply("This command can only be used in a server.")
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("DELETE FROM tags WHERE guild_id = ? AND name = ?", (guild.id, name.lower()))
            await db.commit()
            if cursor.rowcount == 0:
                return await ctx.reply("Tag not found.")
        await ctx.reply(f"Deleted tag '{name}'.")

    @tags_group.command(name="list", description="List tags (optional search)")
    @app_commands.describe(search="Optional search text")
    @commands.guild_only()
    async def tags_list(self, ctx: commands.Context, search: Optional[str] = None):
        if ctx.guild is None:
            return await ctx.reply("This command can only be used in a server.")
        
        async with aiosqlite.connect(DB_PATH) as db:
            if search:
                like = f"%{search.lower()}%"
                cursor = await db.execute("SELECT name, uses FROM tags WHERE guild_id = ? AND name LIKE ? ORDER BY uses DESC LIMIT 50", (ctx.guild.id, like))
            else:
                cursor = await db.execute("SELECT name, uses FROM tags WHERE guild_id = ? ORDER BY uses DESC LIMIT 50", (ctx.guild.id,))
            rows = await cursor.fetchall()
        if not rows:
            return await ctx.reply("No tags found.")
        lines = [f"{name} ({uses})" for name, uses in rows]
        await ctx.reply("Tags:\n" + "\n".join(lines))

async def setup(bot: commands.Bot):
    await bot.add_cog(Tags(bot))
