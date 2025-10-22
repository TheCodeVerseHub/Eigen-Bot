"""Community engagement prefix commands (simplified).

Provides quote, question, meme and suggestion commands. Persistence for
suggestions/challenges/QOTD removed per simplification request.
"""

import discord
from discord.ext import commands
from discord import app_commands
import json
from datetime import datetime, timezone
from utils.helpers import (
    create_success_embed,
    create_error_embed,
    get_random_quote,
    get_random_question,
    fetch_programming_meme,
    sanitize_input
)


class CommunityCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.load_data()

    def load_data(self):
        try:
            with open('src/data/questions.json', 'r', encoding='utf-8') as f:
                self.questions = json.load(f)
        except FileNotFoundError:
            self.questions = []
        try:
            with open('src/data/quotes.json', 'r', encoding='utf-8') as f:
                self.quotes = json.load(f)
        except FileNotFoundError:
            self.quotes = []

    @commands.hybrid_command(name='quote', help='Get a random motivational/programming quote')
    async def quote(self, ctx: commands.Context):
        if not self.quotes:
            embed = discord.Embed(
                title='No Quotes Available',
                description='Quote database is currently empty.',
                color=0xE74C3C
            )
            await ctx.reply(embed=embed, mention_author=False)
            return
        text = get_random_quote(self.quotes)
        embed = discord.Embed(
            title='Programming Inspiration',
            description=f"*{text}*",
            color=0xF39C12,
            timestamp=datetime.now(tz=timezone.utc)
        )
        embed.set_footer(text='CodeVerse Bot | Stay motivated')
        await ctx.reply(embed=embed, mention_author=False)

    @commands.hybrid_command(name='question', help='Get a random programming question')
    async def question(self, ctx: commands.Context):
        if not self.questions:
            embed = discord.Embed(
                title='No Questions Available',
                description='Question database is currently empty.',
                color=0xE74C3C
            )
            await ctx.reply(embed=embed, mention_author=False)
            return
        q = get_random_question(self.questions)
        embed = discord.Embed(
            title='Programming Question',
            color=0x3498DB,
            timestamp=datetime.now(tz=timezone.utc)
        )
        if isinstance(q, dict):
            embed.add_field(name='Question', value=q.get('question', 'N/A'), inline=False)
            if 'difficulty' in q:
                embed.add_field(name='Difficulty', value=q['difficulty'], inline=True)
            if 'category' in q:
                embed.add_field(name='Category', value=q['category'], inline=True)
        else:
            embed.add_field(name='Question', value=str(q), inline=False)
        embed.set_footer(text='CodeVerse Bot | Programming Practice')
        await ctx.reply(embed=embed, mention_author=False)

    @commands.hybrid_command(name='meme', help='Get a random programming meme')
    async def meme(self, ctx: commands.Context):
        async with ctx.typing():
            meme = await fetch_programming_meme()
        if meme.startswith('http'):
            embed = discord.Embed(
                title='Programming Humor',
                color=0xE67E22,
                timestamp=datetime.now(tz=timezone.utc)
            )
            embed.set_image(url=meme)
        else:
            embed = discord.Embed(
                title='Programming Humor',
                description=meme,
                color=0xE67E22,
                timestamp=datetime.now(tz=timezone.utc)
            )
        embed.set_footer(text='CodeVerse Bot | Programming Humor')
        await ctx.reply(embed=embed, mention_author=False)

    @commands.hybrid_command(name='suggest', help='Submit a suggestion (ephemeral – not stored)')
    async def suggest(self, ctx: commands.Context, *, suggestion: str):
        suggestion = sanitize_input(suggestion, 1000)
        if len(suggestion.strip()) < 10:
            embed = discord.Embed(
                title='Suggestion Too Short',
                description='Suggestions must be at least 10 characters long.',
                color=0xE74C3C
            )
            await ctx.reply(embed=embed, mention_author=False)
            return
        embed = discord.Embed(
            title='Suggestion Received',
            description=f"Thank you for your feedback.\n\n**Your suggestion:** {suggestion[:200]}{'...' if len(suggestion) > 200 else ''}",
            color=0x2ECC71,
            timestamp=datetime.now(tz=timezone.utc)
        )
        embed.set_footer(text='CodeVerse Bot | Community Feedback')
        await ctx.reply(embed=embed, mention_author=False)

    @commands.hybrid_command(name='reload-data', help='Reload quotes & questions (Admin only)')
    @commands.has_permissions(administrator=True)
    async def reload_data(self, ctx: commands.Context):
        try:
            self.load_data()
            await ctx.send(embed=create_success_embed('🔄 Data Reloaded', f"Loaded {len(self.questions)} questions, {len(self.quotes)} quotes."))
        except Exception as e:
            await ctx.send(embed=create_error_embed('Reload Failed', str(e)))


async def setup(bot: commands.Bot):
    await bot.add_cog(CommunityCommands(bot))