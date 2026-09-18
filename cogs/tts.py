import asyncio
import logging
import os
import sqlite3
from contextlib import suppress
from io import BytesIO

import discord
import edge_tts
from discord.ext import commands
from discord.ext.commands import Context

from utils.database import DATABASE_NAME, ensure_database_directory

logger = logging.getLogger(__name__)


class Say(commands.Cog):
    """Edge TTS with per-guild queues, cooldown, persistent login and auto leave."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.queues: dict[int, asyncio.Queue[str]] = {}
        self.worker_tasks: dict[int, asyncio.Task[None]] = {}

        # Persistent SQLite storage
        ensure_database_directory()
        self.db: sqlite3.Connection = sqlite3.connect(
            DATABASE_NAME, check_same_thread=False
        )

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS tts_logins (
                user_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
            """
        )
        self.db.commit()

    # ----------------------------
    # QUEUE PROCESSOR
    # ----------------------------

    @staticmethod
    def _idle_timeout() -> float:
        try:
            return max(float(os.getenv("TTS_VC_LEAVE_TIMEOUT", "240")), 1.0)
        except ValueError:
            return 240.0

    async def edge_to_bytes(self, text: str) -> BytesIO:
        voice = os.getenv(
            "TTS_VOICE", "en-US-AriaNeural"
        )  # Default voice if env missing
        comm = edge_tts.Communicate(text=text, voice=voice)

        fp = BytesIO()
        async for chunk in comm.stream():
            if chunk["type"] == "audio" and "data" in chunk:
                fp.write(chunk["data"])

        fp.seek(0)
        return fp

    async def process_queue(self, guild_id: int) -> None:
        queue = self.queues[guild_id]
        try:
            while True:
                try:
                    text = await asyncio.wait_for(
                        queue.get(), timeout=self._idle_timeout()
                    )
                except TimeoutError:
                    guild = self.bot.get_guild(guild_id)
                    vc = guild.voice_client if guild else None
                    if isinstance(vc, discord.VoiceClient) and vc.is_connected():
                        await vc.disconnect()
                    return

                guild = self.bot.get_guild(guild_id)
                vc = guild.voice_client if guild else None
                if not isinstance(vc, discord.VoiceClient):
                    queue.task_done()
                    continue
                if not vc.is_connected():
                    queue.task_done()
                    continue

                try:
                    audio = await self.edge_to_bytes(text)
                    source = discord.FFmpegPCMAudio(audio, pipe=True)

                    def after_playing(error):
                        if error:
                            print(f"TTS Error: {error}")
                        # Signal completion here if needed, but simple sleep loop works too for now

                    vc.play(source, after=after_playing)

                    while vc.is_playing():
                        await asyncio.sleep(0.5)
                        if not vc.is_connected():
                            break

                except Exception:
                    logger.exception("Error processing TTS for guild %s", guild_id)
                finally:
                    queue.task_done()
        except asyncio.CancelledError:
            raise
        finally:
            self.worker_tasks.pop(guild_id, None)
            if queue.empty():
                self.queues.pop(guild_id, None)

    async def _stop_guild_worker(self, guild_id: int) -> None:
        worker = self.worker_tasks.pop(guild_id, None)
        if worker and not worker.done():
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker
        self.queues.pop(guild_id, None)

    def cog_unload(self) -> None:
        for worker in self.worker_tasks.values():
            worker.cancel()
        self.worker_tasks.clear()
        self.queues.clear()
        self.db.close()

    # ----------------------------
    # LOGIN TTS NAME
    # ----------------------------

    @commands.hybrid_command(name="logintts")
    async def logintts(self, ctx: Context, name: str):
        if len(name) > 32:
            return await ctx.send("Name too long. Max 32 characters.")

        self.db.execute(
            "INSERT OR REPLACE INTO tts_logins (user_id, name) VALUES (?, ?)",
            (ctx.author.id, name.strip()),
        )
        self.db.commit()

        await ctx.send(f"TTS name set to: {name}\nYou can now use ?tts <message>")

    # ----------------------------
    # FORCE LEAVE VC
    # ----------------------------

    @commands.hybrid_command(name="leavevc")
    async def leavevc(self, ctx: Context):
        if ctx.guild is not None:
            await self._stop_guild_worker(ctx.guild.id)
        vc = ctx.voice_client
        if isinstance(vc, discord.VoiceClient) and vc.is_connected():
            await vc.disconnect(force=True)
            await ctx.send("Left the voice channel.")
        else:
            await ctx.send("I am not in a voice channel.")

    # ----------------------------
    # TTS COMMAND
    # ----------------------------

    @commands.hybrid_command(name="tts")
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def tts(self, ctx: Context, *, text: str):

        if ctx.guild is None:
            return await ctx.send("Server only command.")

        if len(text) > 400:
            return await ctx.send("Maximum 400 characters allowed.")

        author = ctx.author
        if not isinstance(author, discord.Member):
            return await ctx.send("Server member only.")

        # Fetch login from DB
        cursor = self.db.execute(
            "SELECT name FROM tts_logins WHERE user_id = ?", (ctx.author.id,)
        )
        row = cursor.fetchone()

        if row is None:
            return await ctx.send(
                "You must set your TTS name first.\nUse: ?logintts <your_name>"
            )

        tts_name: str = row[0]

        if not author.voice or not author.voice.channel:
            return await ctx.send("Join a voice channel first.")

        channel = author.voice.channel
        vc = ctx.voice_client

        if not isinstance(vc, discord.VoiceClient):
            vc = await channel.connect()
        elif vc.channel != channel:
            await vc.disconnect(force=True)
            vc = await channel.connect()

        content = text

        if ctx.message:
            for member in ctx.message.mentions:
                content = content.replace(f"<@{member.id}>", f"@{member.display_name}")
                content = content.replace(f"<@!{member.id}>", f"@{member.display_name}")

            for channel_ in ctx.message.channel_mentions:
                content = content.replace(f"<#{channel_.id}>", f"#{channel_.name}")

        queue = self.queues.setdefault(ctx.guild.id, asyncio.Queue())
        queue.put_nowait(f"{tts_name} said {content}")

        await ctx.send(f'"{tts_name}" is saying: {text}')

        # Do not block the command, process in background
        worker = self.worker_tasks.get(ctx.guild.id)
        if worker is None or worker.done():
            self.worker_tasks[ctx.guild.id] = asyncio.create_task(
                self.process_queue(ctx.guild.id)
            )

    # ----------------------------
    # COOLDOWN ERROR HANDLER
    # ----------------------------

    @tts.error
    async def tts_error(self, ctx: Context, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send("You are sending TTS too fast. Wait 2 seconds.")
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Say(bot))
