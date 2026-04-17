import asyncio
import os
import sqlite3
from queue import Queue
from io import BytesIO

import discord
from discord.ext import commands
from discord.ext.commands import Context
import edge_tts


class Say(commands.Cog):
    """Edge TTS with queue, cooldown, persistent login and auto leave."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.queue: Queue[str] = Queue()
        self.playing: bool = False
        self.leave_task: asyncio.Task | None = None

        # Persistent SQLite storage
        self.db: sqlite3.Connection = sqlite3.connect(
            "botdata.db",
            check_same_thread=False
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
    # AUTO LEAVE
    # ----------------------------

    async def schedule_leave(self, vc: discord.VoiceClient) -> None:
        if self.leave_task and not self.leave_task.done():
            self.leave_task.cancel()

        async def leave_later():
            try:
                timeout = float(os.getenv("TTS_VC_LEAVE_TIMEOUT", "240"))
                await asyncio.sleep(timeout)

                if vc.is_connected() and not vc.is_playing():
                    await vc.disconnect()
            except asyncio.CancelledError:
                pass

        self.leave_task = asyncio.create_task(leave_later())

    # ----------------------------
    # QUEUE PROCESSOR
    # ----------------------------

    async def edge_to_bytes(self, text: str) -> BytesIO:
        voice = os.getenv("TTS_VOICE", "en-US-AriaNeural") # Default voice if env missing
        comm = edge_tts.Communicate(text=text, voice=voice)

        fp = BytesIO()
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                if "data" in chunk:
                    fp.write(chunk["data"])

        fp.seek(0)
        return fp

    async def process_queue(self, vc: discord.VoiceClient) -> None:
        if self.playing:
            return

        self.playing = True

        try:
            while not self.queue.empty():
                if not vc.is_connected():
                    break

                text = self.queue.get()

                if self.leave_task:
                    self.leave_task.cancel()

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

                except Exception as e:
                    print(f"Error processing TTS: {e}")
                finally:
                    self.queue.task_done()
        finally:
            self.playing = False
            await self.schedule_leave(vc)

    # ----------------------------
        await self.schedule_leave(vc)

    # ----------------------------
    # LOGIN TTS NAME
    # ----------------------------

    @commands.hybrid_command(name="logintts", description="Set your TTS display name for voice chat", help="Set your TTS display name for voice chat")
    async def logintts(self, ctx: Context, name: str):
        if len(name) > 32:
            return await ctx.send("Name too long. Max 32 characters.")

        self.db.execute(
            "INSERT OR REPLACE INTO tts_logins (user_id, name) VALUES (?, ?)",
            (ctx.author.id, name.strip())
        )
        self.db.commit()

        await ctx.send(
            f'TTS name set to: {name}\n'
            "You can now use ?tts <message>"
        )

    # ----------------------------
    # FORCE LEAVE VC
    # ----------------------------

    @commands.hybrid_command(name="leavevc", description="Make the bot leave its current voice channel", help="Make the bot leave its current voice channel")
    async def leavevc(self, ctx: Context):
        vc = ctx.voice_client
        if isinstance(vc, discord.VoiceClient) and vc.is_connected():
            await vc.disconnect(force=True)
            await ctx.send("Left the voice channel.")
        else:
            await ctx.send("I am not in a voice channel.")

    # ----------------------------
    # TTS COMMAND
    # ----------------------------

    @commands.hybrid_command(name="tts", description="Send a text-to-speech message in your voice channel", help="Send a text-to-speech message in your voice channel")
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
            "SELECT name FROM tts_logins WHERE user_id = ?",
            (ctx.author.id,)
        )
        row = cursor.fetchone()

        if row is None:
            return await ctx.send(
                "You must set your TTS name first.\n"
                "Use: ?logintts <your_name>"
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
                content = content.replace(
                    f"<@{member.id}>", f"@{member.display_name}"
                )
                content = content.replace(
                    f"<@!{member.id}>", f"@{member.display_name}"
                )

            for channel_ in ctx.message.channel_mentions:
                content = content.replace(
                    f"<#{channel_.id}>", f"#{channel_.name}"
                )

        self.queue.put(f"{tts_name} said {content}")

        await ctx.send(f'"{tts_name}" is saying: {text}')

        # Do not block the command, process in background
        if not self.playing:
            self.bot.loop.create_task(self.process_queue(vc))

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
