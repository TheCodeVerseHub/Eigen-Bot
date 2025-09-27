"""
Professional Fun Commands - Programming-themed entertainment
Clean, emoji-free implementation optimized for bot-hosting.net
"""

import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
from datetime import datetime, timezone
from typing import Optional

# Professional data sets without emojis
COMPLIMENTS = [
    "Your programming skills are excellent.",
    "You demonstrate impressive problem-solving abilities.",
    "Your code quality is consistently high.",
    "You handle debugging challenges efficiently.",
    "Your code architecture is well-structured.",
    "You write maintainable and readable code.",
    "Your attention to detail is commendable."
]

PROGRAMMING_JOKES = [
    "Why don't programmers like nature? It has too many bugs!",
    "What do you call a programmer from Finland? Nerdic!",
    "Why do Java developers wear glasses? Because they don't C!",
    "How many programmers does it take to change a light bulb? None, that's a hardware problem.",
    "Why did the programmer quit his job? He didn't get arrays!",
    "What's a programmer's favorite hangout place? Foo Bar!",
    "Why do programmers prefer dark mode? Because light attracts bugs!"
]

FORTUNE_MESSAGES = [
    "Your next commit will be bug-free.",
    "A well-documented solution awaits your discovery.",
    "Your code review will receive unanimous approval.",
    "An elegant algorithm will present itself today.",
    "Your debugging session will be shorter than expected.",
    "Your code will compile successfully on the first attempt.",
    "A mentor will share valuable programming wisdom with you."
]

TRIVIA_QUESTIONS = [
    {
        "question": "What does CPU stand for?",
        "answer": "Central Processing Unit",
        "category": "Hardware"
    },
    {
        "question": "Which programming language is known for its snake logo?",
        "answer": "Python",
        "category": "Programming"
    },
    {
        "question": "What does HTML stand for?",
        "answer": "HyperText Markup Language",
        "category": "Web Development"
    },
    {
        "question": "Who created the Linux operating system?",
        "answer": "Linus Torvalds",
        "category": "Operating Systems"
    }
]

class Fun(commands.Cog):
    """Professional fun commands for programming communities."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    @commands.hybrid_command(name="compliment", help="Receive a professional programming compliment")
    async def compliment(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Give a professional compliment to yourself or another member."""
        """Give a professional compliment to yourself or another member."""
        target = member or ctx.author
        compliment = random.choice(COMPLIMENTS)
        
        embed = discord.Embed(
            title="Professional Recognition",
            description=f"{target.mention}, {compliment}",
            color=0x2ECC71,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text="CodeVerse Bot | Professional Development")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.hybrid_command(name="joke", help="Get a programming-related joke")
    async def joke(self, ctx: commands.Context):
        """Share a clean programming joke."""
        joke = random.choice(PROGRAMMING_JOKES)
        
        embed = discord.Embed(
            title="Programming Humor",
            description=joke,
            color=0xF39C12,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text="CodeVerse Bot | Community Fun")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.hybrid_command(name="fortune", help="Get a programming fortune")
    async def fortune(self, ctx: commands.Context):
        """Receive a programming-themed fortune message."""
        fortune = random.choice(FORTUNE_MESSAGES)
        
        embed = discord.Embed(
            title="Programming Fortune",
            description=fortune,
            color=0x9B59B6,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text="CodeVerse Bot | Daily Inspiration")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.hybrid_command(name="trivia", help="Answer a programming trivia question")
    async def trivia(self, ctx: commands.Context):
        """Start a programming trivia question."""
        question_data = random.choice(TRIVIA_QUESTIONS)
        
        embed = discord.Embed(
            title="Programming Trivia",
            description=f"**Category:** {question_data['category']}\n\n**Question:** {question_data['question']}",
            color=0x3498DB,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text="Answer will be revealed in 30 seconds")
        
        message = await ctx.reply(embed=embed, mention_author=False)
        
        # Wait 30 seconds, then reveal answer
        await asyncio.sleep(30)
        
        answer_embed = discord.Embed(
            title="Trivia Answer",
            description=f"**Question:** {question_data['question']}\n**Answer:** {question_data['answer']}",
            color=0x2ECC71,
            timestamp=datetime.now(timezone.utc)
        )
        answer_embed.set_footer(text="CodeVerse Bot | Programming Knowledge")
        
        try:
            await message.edit(embed=answer_embed)
        except:
            await ctx.send(embed=answer_embed)

    @commands.hybrid_command(name="flip", help="Flip a coin")
    async def flip(self, ctx: commands.Context):
        """Flip a virtual coin."""
        result = random.choice(["Heads", "Tails"])
        
        embed = discord.Embed(
            title="Coin Flip",
            description=f"Result: **{result}**",
            color=0x95A5A6,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text="CodeVerse Bot | Random Utilities")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.hybrid_command(name="singledice", help="Roll a single die (basic). For multi-dice use /roll")
    @app_commands.describe(sides="Number of sides on the die (default: 6)")
    async def single_dice(self, ctx: commands.Context, sides: int = 6):
        """Roll a single die (basic variant). Advanced multi-dice available via /roll."""
        if sides < 2 or sides > 100:
            embed = discord.Embed(
                title="Invalid Dice",
                description="Dice must have between 2 and 100 sides.",
                color=0xE74C3C
            )
            await ctx.reply(embed=embed, mention_author=False)
            return
        
        result = random.randint(1, sides)
        
        embed = discord.Embed(
            title=f"Dice Roll (d{sides})",
            description=f"Result: **{result}**",
            color=0x3498DB,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text="CodeVerse Bot | Random Utilities")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.hybrid_command(name="choose", help="Choose randomly from a list of options")
    @app_commands.describe(choices="Comma-separated list of choices")
    async def choose(self, ctx: commands.Context, *, choices: str):
        """Randomly choose from a list of options."""
        options = [choice.strip() for choice in choices.split(',') if choice.strip()]
        
        if len(options) < 2:
            embed = discord.Embed(
                title="Insufficient Options",
                description="Please provide at least 2 comma-separated choices.",
                color=0xE74C3C
            )
            await ctx.reply(embed=embed, mention_author=False)
            return
        
        if len(options) > 20:
            embed = discord.Embed(
                title="Too Many Options",
                description="Please provide no more than 20 choices.",
                color=0xE74C3C
            )
            await ctx.reply(embed=embed, mention_author=False)
            return
        
        choice = random.choice(options)
        
        embed = discord.Embed(
            title="Random Choice",
            description=f"**Options:** {', '.join(options)}\n\n**Selected:** {choice}",
            color=0x9B59B6,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text="CodeVerse Bot | Decision Helper")
        await ctx.reply(embed=embed, mention_author=False)

async def setup(bot: commands.Bot):
    await bot.add_cog(Fun(bot))
