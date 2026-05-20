"""
Professional Fun Commands - Programming-themed entertainment
Clean, emoji-free implementation optimized for bot-hosting.net
"""

import asyncio
import io
import logging
import random
import time
import urllib.request
from datetime import datetime, timezone
from typing import Optional, Union

import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont, ImageSequence

# Professional data sets without emojis
COMPLIMENTS = [
    "Your programming skills are excellent.",
    "You demonstrate impressive problem-solving abilities.",
    "Your code quality is consistently high.",
    "You handle debugging challenges efficiently.",
    "Your code architecture is well-structured.",
    "You write maintainable and readable code.",
    "Your attention to detail is commendable.",
]

PROGRAMMING_JOKES = [
    "Why don't programmers like nature? It has too many bugs!",
    "What do you call a programmer from Finland? Nerdic!",
    "Why do Java developers wear glasses? Because they don't C!",
    "How many programmers does it take to change a light bulb? None, that's a hardware problem.",
    "Why did the programmer quit his job? He didn't get arrays!",
    "What's a programmer's favorite hangout place? Foo Bar!",
    "Why do programmers prefer dark mode? Because light attracts bugs!",
]

FORTUNE_MESSAGES = [
    "Your next commit will be bug-free.",
    "A well-documented solution awaits your discovery.",
    "Your code review will receive unanimous approval.",
    "An elegant algorithm will present itself today.",
    "Your debugging session will be shorter than expected.",
    "Your code will compile successfully on the first attempt.",
    "A mentor will share valuable programming wisdom with you.",
]


ABSOLUTE_TEMPLATE_GIF_URL = (
    "https://media1.tenor.com/m/9zeYdsiRscoAAAAd/absolute-cinema.gif"
)
max_absol_text_len = 24
ABSOLUTE_TEMPLATE_CACHE_TTL_SECONDS = 1800

logger = logging.getLogger(__name__)


class Fun(commands.Cog):
    """Professional fun commands for programming communities."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._absolute_template_cache_bytes: Optional[bytes] = None
        self._absolute_template_cache_expires_at = 0.0
        self._absolute_template_cache_lock = asyncio.Lock()

    @staticmethod
    def _download_bytes(url: str) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.read()

    @staticmethod
    def _load_font(size: int) -> Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]:
        for font_name in ("arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"):
            try:
                return ImageFont.truetype(font_name, size=size)
            except OSError:
                continue
        return ImageFont.load_default()

    @classmethod
    def _build_absolute_gif(
        cls, template_bytes: bytes, avatar_bytes: bytes, text: str
    ) -> io.BytesIO:
        template = Image.open(io.BytesIO(template_bytes))
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")

        output_frames = []
        frame_durations = []
        caption = f"ABSOLUTE {text.upper()}"
        width, height = template.size

        avatar_size = max(56, int(min(width, height) * 0.22))
        resized_avatar = avatar.resize(
            (avatar_size, avatar_size), Image.Resampling.LANCZOS
        )
        avatar_mask = Image.new("L", (avatar_size, avatar_size), 0)
        ImageDraw.Draw(avatar_mask).ellipse((0, 0, avatar_size, avatar_size), fill=255)
        circular_avatar = Image.new("RGBA", (avatar_size, avatar_size), (0, 0, 0, 0))
        circular_avatar.paste(resized_avatar, (0, 0), avatar_mask)
        avatar_x = (width - avatar_size) // 2
        avatar_y = int(height * 0.28)

        font_size = max(14, width // 11)
        font = cls._load_font(font_size)
        stroke_width = max(1, width // 140)

        for frame in ImageSequence.Iterator(template):
            base = frame.convert("RGBA")
            base.paste(circular_avatar, (avatar_x, avatar_y), circular_avatar)

            draw = ImageDraw.Draw(base)

            text_bbox = draw.textbbox(
                (0, 0), caption, font=font, stroke_width=stroke_width
            )
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            bar_padding = max(6, width // 70)
            bar_height = text_height + (bar_padding * 2)
            bar_top = height - bar_height
            draw.rectangle((0, bar_top, width, height), fill=(0, 0, 0, 210))

            text_x = (width - text_width) // 2
            text_y = bar_top + (bar_height - text_height) // 2
            draw.text(
                (text_x, text_y),
                caption,
                font=font,
                fill=(255, 255, 255, 255),
                stroke_width=stroke_width,
                stroke_fill=(0, 0, 0, 255),
            )

            output_frames.append(base.convert("P", palette=Image.Palette.ADAPTIVE))
            frame_durations.append(frame.info.get("duration", 40))

        result = io.BytesIO()
        output_frames[0].save(
            result,
            format="GIF",
            save_all=True,
            append_images=output_frames[1:],
            duration=frame_durations,
            loop=0,
            disposal=2,
        )
        result.seek(0)
        return result

    async def _get_absolute_template_bytes(self) -> bytes:
        now = time.monotonic()
        if (
            self._absolute_template_cache_bytes
            and now < self._absolute_template_cache_expires_at
        ):
            return self._absolute_template_cache_bytes

        async with self._absolute_template_cache_lock:
            now = time.monotonic()
            if (
                self._absolute_template_cache_bytes
                and now < self._absolute_template_cache_expires_at
            ):
                return self._absolute_template_cache_bytes

            template_bytes = await asyncio.to_thread(
                self._download_bytes, ABSOLUTE_TEMPLATE_GIF_URL
            )
            self._absolute_template_cache_bytes = template_bytes
            self._absolute_template_cache_expires_at = (
                now + ABSOLUTE_TEMPLATE_CACHE_TTL_SECONDS
            )
            return template_bytes

    @commands.hybrid_command(name="fridge", help="Send a fridge image")
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def fridge(self, ctx: commands.Context):
        """Send a fridge image (simple utility)."""
        # Generate an image locally so it always works (no external hotlinking).
        width, height = 512, 512
        img = Image.new("RGB", (width, height), (245, 248, 252))
        draw = ImageDraw.Draw(img)

        # Simple fridge body
        body_left, body_top = 150, 70
        body_right, body_bottom = 362, 440
        draw.rounded_rectangle(
            (body_left, body_top, body_right, body_bottom),
            radius=24,
            fill=(220, 230, 240),
            outline=(120, 140, 160),
            width=6,
        )

        # Door split
        split_y = 250
        draw.line(
            (body_left + 10, split_y, body_right - 10, split_y),
            fill=(120, 140, 160),
            width=6,
        )

        # Handles
        draw.rounded_rectangle((330, 110, 346, 190), radius=8, fill=(120, 140, 160))
        draw.rounded_rectangle((330, 290, 346, 410), radius=8, fill=(120, 140, 160))

        # Feet
        draw.rectangle((190, 440, 220, 460), fill=(90, 100, 110))
        draw.rectangle((292, 440, 322, 460), fill=(90, 100, 110))

        # Export
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        file = discord.File(buf, filename="fridge.png")
        embed = discord.Embed(
            title="Fridge", color=0x3498DB, timestamp=datetime.now(timezone.utc)
        )
        embed.set_image(url="attachment://fridge.png")
        await ctx.reply(embed=embed, file=file, mention_author=False)

    @commands.command(name="pat", help="Send a wholesome pat gif (prefix-only).")
    async def pat(self, ctx: commands.Context):
        """Send a wholesome pat gif (prefix-only)."""
        gif_url = "https://tenor.com/bQSNq.gif"
        # Send as a plain message with the GIF URL (not embedded)
        await ctx.reply(gif_url, mention_author=False)

    @commands.hybrid_command(
        name="compliment", help="Receive a professional programming compliment"
    )
    async def compliment(
        self, ctx: commands.Context, member: Optional[discord.Member] = None
    ):
        """Give a professional compliment to yourself or another member."""
        """Give a professional compliment to yourself or another member."""
        target = member or ctx.author
        compliment = random.choice(COMPLIMENTS)

        embed = discord.Embed(
            title="Professional Recognition",
            description=f"{target.mention}, {compliment}",
            color=0x2ECC71,
            timestamp=datetime.now(timezone.utc),
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
            timestamp=datetime.now(timezone.utc),
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
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text="CodeVerse Bot | Daily Inspiration")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.hybrid_command(name="flip", help="Flip a coin")
    async def flip(self, ctx: commands.Context):
        """Flip a virtual coin."""
        result = random.choice(["Heads", "Tails"])

        embed = discord.Embed(
            title="Coin Flip",
            description=f"Result: **{result}**",
            color=0x95A5A6,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text="CodeVerse Bot | Random Utilities")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="topic", help="Get a random chat topic (prefix-only).")
    async def topic(self, ctx: commands.Context):
        """Send a random discussion topic from a curated list (prefix-only)."""
        topics = [
            "What programming language should everyone try at least once?",
            "Tabs or spaces?",
            "What was your first coding project?",
            "Which tech trend is overrated right now?",
            "Linux or Windows for development?",
            "What game got you addicted instantly?",
            "What is your dream setup?",
            "Which framework do you hate working with?",
            "Frontend or backend?",
            "What coding mistake taught you the most?",
            "What app do you use every single day?",
            "What technology will dominate in 10 years?",
            "Which programming meme is the most accurate?",
            "What is the hardest bug you ever fixed?",
            "What was your first PC or laptop?",
            "Dark mode or light mode?",
            "Which company has the best developer tools?",
            "What coding project are you proud of?",
            "Which OS looks the cleanest?",
            "If you could master one skill instantly what would it be?",
            "What keyboard switch sounds the best?",
            "Which tech YouTuber do you watch most?",
            "What is your favorite open source project?",
            "What coding language feels the most satisfying?",
            "What is your dream job in tech?",
            "What is the worst programming language syntax?",
            "What motivates you to keep learning?",
            "Which anime has the best story?",
            "What game has the best soundtrack?",
            "Which editor or IDE do you use daily?",
            "What was your biggest coding fail?",
            "What technology scared you at first?",
            "What is your favorite Linux distro?",
            "Which browser do you trust most?",
            "AI replacing developers soon or not?",
            "Which social media app is declining fastest?",
            "What coding project idea should beginners make first?",
            "What is your favorite keyboard shortcut?",
            "Which programming language should schools teach first?",
            "What tech purchase was 100 percent worth it?",
            "Which programming language has the best community?",
            "What is your favorite command line tool?",
            "Which startup idea would you build if money was unlimited?",
            "What movie has the best visual effects?",
            "Which coding habit improved your skills most?",
            "What is your favorite API?",
            "Which game has the best graphics?",
            "What website design looks the cleanest?",
            "What skill will be most valuable in future tech?",
            "Which programming language is hardest to learn?",
            "What is your favorite terminal theme?",
            "Which app has the worst UI?",
            "What was your most useful coding resource?",
            "Which fictional technology do you want real?",
            "What coding language would survive longest?",
            "Which company makes the best hardware?",
            "What is your favorite productivity trick?",
            "What project are you currently building?",
            "Which coding project took longest to finish?",
            "What is your favorite game genre?",
            "Which tech myth annoys you most?",
            "What browser extension can you not live without?",
            "Which programming language deserves more attention?",
            "What was your first experience with Linux?",
            "Which coding project idea sounds fun right now?",
            "What feature should Discord add next?",
            "Which device do you use most daily?",
            "What was your first coding language?",
            "Which operating system is most underrated?",
            "What tech opinion would start an argument instantly?",
            "Which programming language has best documentation?",
            "What game world would you live in?",
            "What coding skill is hardest to master?",
            "Which old technology do you still use?",
            "What motivates you during difficult projects?",
            "Which app wastes most of your time?",
            "What is your favorite coding font?",
            "Which console generation was best?",
            "What is your dream programming project?",
            "Which tech company fell off hardest?",
            "What was your biggest learning breakthrough?",
            "Which Linux command feels most powerful?",
            "What coding advice do beginners ignore too much?",
            "Which movie predicted technology best?",
            "What is your favorite coding snack?",
            "Which programming language has coolest logo?",
            "What tech skill should everyone learn?",
            "Which software has the cleanest UI?",
            "What coding project would you restart differently?",
            "Which mobile app deserves a desktop version?",
            "What futuristic gadget do you want most?",
            "Which tech career seems most exciting?",
            "What coding workflow works best for you?",
            "Which app update ruined the app?",
            "What programming concept took longest to understand?",
            "Which game deserves a remake?",
            "What is your favorite open source alternative?",
            "Which website do you visit most often?",
            "What coding language has best naming style?",
            "Which piece of tech do you regret buying?",
            "What project idea sounds impossible but cool?",
            "Which software should become open source?",
            "What was your favorite school subject?",
            "Which programming language feels fastest?",
            "What tech trend are you most excited for?",
            "Which coding project improved your skills most?",
            "What device would you upgrade right now?",
            "Which app icon looks best?",
            "What is the cleanest programming syntax ever?",
            "Which developer tool saved you most time?",
            "What technology from movies became real?",
            "Which coding project idea should become a startup?",
            "What is your favorite Discord server type?",
            "Which website has the worst ads?",
            "What coding topic should more people learn?",
            "Which gadget feels most futuristic?",
            "What is your favorite tech wallpaper style?",
            "Which programming meme is painfully true?",
            "What was your most satisfying coding moment?",
            "Which game had the best multiplayer experience?",
        ]
        topic = random.choice(topics)

        embed = discord.Embed(
            title="Discussion Topic",
            description=topic,
            color=0x3498DB,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text="Use ?topic to get another idea")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="gif", help="Send a gif matching a query (prefix-only).")
    async def gif(self, ctx: commands.Context, *, query: Optional[str] = None):
        """Return a gif URL from a fixed list matching the query or random if none."""
        gifs = [
            "https://tenor.com/view/patrick-spongebob-spongebob-meme-patrick-meme-dumb-patrick-gif-9974665538168463324",
            "https://images-ext-2.discordapp.net/external/CXNcMebjeujg_gGvrp1Ymgjg9ei_fTQRybF8rymUh2s/https/cdn.weeb.sh/images/SyFkekYwW.gif",
            "https://tenor.com/view/i-ain%E2%80%99t-reading-all-that-happy-for-u-tho-happy-for-you-tho-sorry-that-happened-too-long-didn%E2%80%99t-read-gif-9353839682789985827",
            "https://tenor.com/view/tuff-tuff-minion-tuff-minoin-hoverboard-gif-17512699728490497347",
            "https://cdn.discordapp.com/attachments/1203665076997849139/1506339325464285264/ragebait.gif",
            "https://klipy.com/gifs/breaking-bad-126--k01KRGZC3DEFA1MMB9RF30TE2XX",
        ]

        # Simple keyword matching to pick a gif; lower-case query.
        if query:
            q = query.lower()
            # mapping of keywords to gif URLs (first match wins)
            mapping = {
                "patrick": gifs[0],
                "spongebob": gifs[0],
                "weeb": gifs[1],
                "i ain't reading": gifs[2],
                "reading": gifs[2],
                "minion": gifs[3],
                "tuff": gifs[3],
                "rage": gifs[4],
                "breaking": gifs[5],
                "bad": gifs[5],
            }

            for k, url in mapping.items():
                if k in q:
                    await ctx.send(url)
                    return

        # No query or no keyword matched: random gif
        await ctx.send(random.choice(gifs))

    @commands.command(
        name="singledice", help="Roll a single die (basic). For multi-dice use ?roll"
    )
    async def single_dice(self, ctx: commands.Context, sides: int = 6):
        """Roll a single die (basic variant). Advanced multi-dice available via /roll."""
        if sides < 2 or sides > 100:
            embed = discord.Embed(
                title="Invalid Dice",
                description="Dice must have between 2 and 100 sides.",
                color=0xE74C3C,
            )
            await ctx.reply(embed=embed, mention_author=False)
            return

        result = random.randint(1, sides)

        embed = discord.Embed(
            title=f"Dice Roll (d{sides})",
            description=f"Result: **{result}**",
            color=0x3498DB,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text="CodeVerse Bot | Random Utilities")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.hybrid_command(
        name="choose", help="Choose randomly from a list of options"
    )
    @app_commands.describe(choices="Comma-separated list of choices")
    async def choose(self, ctx: commands.Context, *, choices: str):
        """Randomly choose from a list of options."""
        options = [choice.strip() for choice in choices.split(",") if choice.strip()]

        if len(options) < 2:
            embed = discord.Embed(
                title="Insufficient Options",
                description="Please provide at least 2 comma-separated choices.",
                color=0xE74C3C,
            )
            await ctx.reply(embed=embed, mention_author=False)
            return

        if len(options) > 20:
            embed = discord.Embed(
                title="Too Many Options",
                description="Please provide no more than 20 choices.",
                color=0xE74C3C,
            )
            await ctx.reply(embed=embed, mention_author=False)
            return

        choice = random.choice(options)

        embed = discord.Embed(
            title="Random Choice",
            description=f"**Options:** {', '.join(options)}\n\n**Selected:** {choice}",
            color=0x9B59B6,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text="CodeVerse Bot | Decision Helper")
        await ctx.reply(embed=embed, mention_author=False)

    @app_commands.describe(text="Text to replace 'cinema' with")
    async def absolute(self, ctx: commands.Context, *, text: str):

        clean_text = " ".join(text.split())

        if not clean_text:
            await ctx.reply(
                "Please provide text. Example: `/absolute text: coding`",
                mention_author=False,
            )
            return

        if len(clean_text) > max_absol_text_len:
            await ctx.reply(
                f"Text must be {max_absol_text_len} characters or less.",
                mention_author=False,
            )
            return

        try:
            await ctx.defer()
        except Exception:
            pass

        try:
            avatar_asset = ctx.author.display_avatar.with_size(256)
            try:
                avatar_asset = avatar_asset.with_format("png")
            except Exception:
                pass

            avatar_bytes = await avatar_asset.read()
            template_bytes = await self._get_absolute_template_bytes()
            gif_bytes = await asyncio.to_thread(
                self._build_absolute_gif, template_bytes, avatar_bytes, clean_text
            )
        except Exception:
            logger.exception("Failed to generate /absolute GIF")
            await ctx.reply(
                "Couldn't generate the GIF right now. Try again later.",
                mention_author=False,
            )
            return

        await ctx.reply(
            file=discord.File(gif_bytes, filename="absolute.gif"), mention_author=False
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Fun(bot))
