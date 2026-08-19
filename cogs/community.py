"""Community engagement commands.

Provides quote, question, and meme commands.

Note: Suggestion submission is handled by the dedicated Suggestions cog
(`cogs/suggestions.py`). This file intentionally does not register a `suggest`
command to avoid command name conflicts.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import discord
from discord.ext import commands

from utils.helpers import (
    create_error_embed,
    create_success_embed,
    fetch_programming_meme,
    get_random_quote,
)


class CommunityCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.load_data()

    def load_data(self):
        base_dir = Path(__file__).resolve().parents[1]
        try:
            # Prefer local repo data folder.
            questions_path = base_dir / "data" / "coding_questions.json"
            with open(questions_path, "r", encoding="utf-8") as f:
                self.questions = json.load(f)
        except FileNotFoundError:
            self.questions = []
        try:
            quotes_path = base_dir / "data" / "quotes.json"
            with open(quotes_path, "r", encoding="utf-8") as f:
                self.quotes = json.load(f)
        except FileNotFoundError:
            # Fallback built-in quotes if file is missing.
            self.quotes = [
                "Talk is cheap. Show me the code. - Linus Torvalds",
                "Programs must be written for people to read. - Harold Abelson",
                "Simplicity is prerequisite for reliability. - Edsger W. Dijkstra",
                "First, solve the problem. Then, write the code. - John Johnson",
                "Before software can be reusable it first has to be usable. - Ralph Johnson",
            ]

    @commands.hybrid_command(
        name="quote", help="Get a random motivational/programming quote"
    )
    async def quote(self, ctx: commands.Context):
        if not self.quotes:
            embed = discord.Embed(
                title="No Quotes Available",
                description="Quote database is currently empty.",
                color=0xE74C3C,
            )
            await ctx.reply(embed=embed, mention_author=False)
            return
        text = get_random_quote(self.quotes)
        embed = discord.Embed(
            title="Programming Inspiration",
            description=f"*{text}*",
            color=0xF39C12,
            timestamp=datetime.now(tz=timezone.utc),
        )
        embed.set_footer(text="CodeVerse Bot | Stay motivated")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="meme", help="Get a random programming meme")
    async def meme(self, ctx: commands.Context):
        async with ctx.typing():
            meme = await fetch_programming_meme()
        if meme.startswith("http"):
            embed = discord.Embed(
                title="Programming Humor",
                color=0xE67E22,
                timestamp=datetime.now(tz=timezone.utc),
            )
            embed.set_image(url=meme)
        else:
            embed = discord.Embed(
                title="Programming Humor",
                description=meme,
                color=0xE67E22,
                timestamp=datetime.now(tz=timezone.utc),
            )
        embed.set_footer(text="CodeVerse Bot | Programming Humor")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.hybrid_command(
        name="reload-data", help="Reload quotes & questions (Admin only)"
    )
    @commands.has_permissions(administrator=True)
    async def reload_data(self, ctx: commands.Context):
        try:
            self.load_data()
            await ctx.send(
                embed=create_success_embed(
                    "🔄 Data Reloaded",
                    f"Loaded {len(self.questions)} questions, {len(self.quotes)} quotes.",
                )
            )
        except Exception as e:
            await ctx.send(embed=create_error_embed("Reload Failed", str(e)))


async def setup(bot: commands.Bot):
    await bot.add_cog(CommunityCommands(bot))
