"""
Modmail cog: Users DM the bot, messages are forwarded to a modmail channel. Mods can reply from the channel.
"""
import discord
from discord.ext import commands
from discord import app_commands
from utils.config import Config
from typing import Optional, Dict, Any
import asyncio
import json
from pathlib import Path
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class ModMail(commands.Cog):
    # Session format per user_id:
    # { 'state': 'open'|'locked'|'resolved', 'reset_at': ISO8601 timestamp or None }
    modmail_sessions: Dict[int, Dict[str, Any]] = {}
    _session_locks: Dict[int, asyncio.Lock] = {}
    SESSIONS_FILE = Path("data/modmail_sessions.json")

    def __init__(self, bot: commands.Bot, config: Config):
        self.bot = bot
        self.config = config
        self.modmail_channel_id: Optional[int] = getattr(config, 'modmail_channel_id', None)
        # Configurable reset delay (seconds)
        self.RESET_DELAY_SECONDS: int = getattr(config, 'MODMAIL_RESET_SECONDS', 600)
        # Load persisted sessions if present
        try:
            self._load_sessions_from_file()
        except Exception:
            logger.exception("modmail: failed to load persisted sessions")

    # Persistence helpers
    def _load_sessions_from_file(self):
        if not self.SESSIONS_FILE.exists():
            return
        try:
            with self.SESSIONS_FILE.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            # Convert keys back to int
            for k, v in data.items():
                try:
                    self.modmail_sessions[int(k)] = v
                except Exception:
                    logger.exception(f"modmail: failed to load session for key {k}")
        except Exception:
            logger.exception("modmail: error reading sessions file")

    def _persist_sessions_to_file(self):
        # Ensure directory exists
        try:
            self.SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
            # Convert keys to strings for JSON
            dumpable = {str(k): v for k, v in self.modmail_sessions.items()}
            with self.SESSIONS_FILE.open("w", encoding="utf-8") as fh:
                json.dump(dumpable, fh)
        except Exception:
            logger.exception("modmail: failed to persist sessions to file")

    class ConfirmView(discord.ui.View):
        def __init__(self, cog, user, message_content):
            super().__init__(timeout=600)  # 10 minutes
            self.cog = cog
            self.user = user
            self.message_content = message_content

        async def on_timeout(self):
            # Reset session if no action in 10 minutes
            self.cog.modmail_sessions.pop(self.user.id, None)
            try:
                self.cog._persist_sessions_to_file()
            except Exception:
                logger.exception(f"modmail: failed to persist session on timeout for {self.user.id}")

        @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
        async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user != self.user:
                return
            channel = self.cog.bot.get_channel(self.cog.modmail_channel_id)
            if channel and isinstance(channel, discord.TextChannel):
                embed = discord.Embed(
                    title="ModMail Message",
                    description=self.message_content,
                    color=discord.Color.blue()
                )
                embed.set_author(name=f"{self.user} ({self.user.id})", icon_url=self.user.display_avatar.url)
                await channel.send(embed=embed)
                await channel.send(f"User ID: `{self.user.id}`")
            sent_embed = discord.Embed(
                title="Message Sent",
                description="Your message was delivered to the moderators. They will respond as soon as possible. Your session is locked for security. Please wait for a moderator to respond before sending more messages.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=sent_embed, ephemeral=False)
            # Lock the session until a moderator replies
            self.cog.modmail_sessions[self.user.id] = {'state': 'locked', 'reset_at': None}
            try:
                self.cog._persist_sessions_to_file()
            except Exception:
                logger.exception(f"modmail: failed to persist session lock for {self.user.id}")
            self.stop()

        @discord.ui.button(label="No", style=discord.ButtonStyle.red)
        async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user != self.user:
                return
            cancel_embed = discord.Embed(
                title="ModMail Cancelled",
                description="Your message was not sent and cancelled by you. You may compose a different message and try again. Your session remains open. It may reset after a period of inactivity.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=cancel_embed, ephemeral=False)
            # Keep session 'open'
            self.stop()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is not None or message.author.bot:
            return
        if not self.modmail_channel_id:
            return
        user_id = message.author.id

        # Ensure single-threaded handling per user to avoid duplicate guideline sends
        lock = self._session_locks.setdefault(user_id, asyncio.Lock())
        async with lock:
            session = self.modmail_sessions.get(user_id)

            # If there is a resolved session with reset_at, check expiry
            if isinstance(session, dict) and session.get('state') == 'resolved' and session.get('reset_at'):
                try:
                    reset_at = datetime.fromisoformat(session['reset_at'])
                except Exception:
                    reset_at = None
                now = datetime.utcnow()
                if reset_at and now >= reset_at:
                    # expired - treat as brand new (clear session)
                    self.modmail_sessions.pop(user_id, None)
                    try:
                        self._persist_sessions_to_file()
                    except Exception:
                        logger.exception(f"modmail: failed to persist session clear for {user_id}")
                    session = None

            session_state = session.get('state') if isinstance(session, dict) else None

            if session is None:
                guideline = (
                    "**ModMail System**\n"
                    "Send your message to the moderators below.\n"
                    "You have only **one message**. After you send it, Modmail will be locked until a moderator replies.\n"
                    "Please include all your questions and details in this one message.\n"
                    "Wait for a moderator to respond before sending anything else."
                )
                embed = discord.Embed(
                    title="ModMail System",
                    description=(
                        "__How to use ModMail__\n"
                        "Send your message to the moderators below. You have only **one message**. "
                        "After you send it, modmail will be locked until a moderator replies.\n\n"
                        "__Tips__\n"
                        "• Include all relevant details, links, and timestamps in this message.\n"
                        "• Do not send multiple follow-ups — wait for a moderator to reply.\n\n"
                        "__Privacy__\n"
                        "Moderators will see your username and ID only; do not share sensitive credentials."
                    ),
                    color=discord.Color.blue()
                )
                embed.set_footer(text="Please follow these guidelines to help moderators assist you faster")
                await message.author.send(embed=embed)
                self.modmail_sessions[user_id] = {'state': 'open', 'reset_at': None}
                logger.info(f"modmail: guidelines sent to user {user_id}")
                try:
                    self._persist_sessions_to_file()
                except Exception:
                    logger.exception(f"modmail: failed to persist session after guidelines for {user_id}")
                return

            # If session is resolved and not expired, behave like 'open' (ask confirmation to continue existing thread)
            if session_state == 'resolved':
                embed = discord.Embed(
                    title="Confirm ModMail Message",
                    description=f"Do you want to send this message to the moderators?\n\n**Message:** {message.content}",
                    color=discord.Color.orange()
                )
                view = self.ConfirmView(self, message.author, message.content)
                await message.author.send(embed=embed, view=view)
                logger.info(f"modmail: confirmation requested for user {user_id} (within reset window)")
                return

            if session_state == 'open':
                embed = discord.Embed(
                    title="Confirm ModMail Message",
                    description=f"Do you want to send this message to the moderators?\n\n**Message:** {message.content}",
                    color=discord.Color.orange()
                )
                view = self.ConfirmView(self, message.author, message.content)
                await message.author.send(embed=embed, view=view)
                logger.info(f"modmail: confirmation requested for user {user_id}")
                return

            if session_state == 'locked':
                try:
                    locked_embed = discord.Embed(
                        title="ModMail Locked",
                        description="Your modmail is currently locked. Please wait for a moderator to reply before sending more messages.",
                        color=discord.Color.orange()
                    )
                    await message.author.send(embed=locked_embed)
                except Exception:
                    pass
                return

    @commands.command(name="reply_modmail")
    @commands.has_permissions(manage_messages=True)
    async def reply_modmail(self, ctx: commands.Context, user_id: int, *, response: str):
        try:
            user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
        except Exception:
            await ctx.send("User not found or not cached.")
            return
        try:
            reply_embed = discord.Embed(
                title="Moderator Reply",
                description=response + "Your session is now resolved and open if you have any further queries. This session will reset after a short period of inactivity.",
                color=discord.Color.green()
            )
            # include moderator identity
            try:
                avatar_url = None
                if hasattr(ctx.author, 'display_avatar') and getattr(ctx.author, 'display_avatar'):
                    avatar_url = ctx.author.display_avatar.url
                reply_embed.set_author(name=ctx.author.display_name, icon_url=avatar_url)
            except Exception:
                pass
            await user.send(embed=reply_embed)
            await ctx.send("Reply sent.")
            # Schedule reset in the future instead of immediately opening the session
            reset_at = (datetime.utcnow() + timedelta(seconds=self.RESET_DELAY_SECONDS)).isoformat()
            self.modmail_sessions[user_id] = {'state': 'resolved', 'reset_at': reset_at}
            logger.info(f"modmail: scheduled reset for user {user_id} at {reset_at}")
            info_embed = discord.Embed(
                title="You may send another message only if needed",
                description="A Moderator has responded. If you need to send another message your session is open. This session will reset after a short period of inactivity.",
                color=discord.Color.blue()
            )
            await user.send(embed=info_embed)
            try:
                self._persist_sessions_to_file()
            except Exception:
                logger.exception(f"modmail: failed to persist scheduled reset for {user_id}")
            # Notify modmail channel
            if self.modmail_channel_id:
                channel = self.bot.get_channel(self.modmail_channel_id)
                if channel and isinstance(channel, discord.TextChannel):
                    embed = discord.Embed(
                        title="ModMail Resolved",
                        description=f"Moderator {ctx.author.mention} has replied to {user.mention}'s modmail.\n\n**Reply:** {response}",
                        color=discord.Color.green()
                    )
                    await channel.send(embed=embed)
        except Exception:
            await ctx.send("Failed to send DM. User may have DMs closed.")

    @commands.command(name="set_modmail_channel")
    @commands.has_permissions(administrator=True)
    async def set_modmail_channel(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        if not channel:
            channel = ctx.channel if isinstance(ctx.channel, discord.TextChannel) else None
        if not channel:
            await ctx.send("Please mention a text channel or use this command in a text channel.")
            return
        self.modmail_channel_id = channel.id
        await ctx.send(f"Modmail channel set to {channel.mention}.")

    @app_commands.command(name="reply_modmail", description="Reply to a user's modmail (mod only)")
    @app_commands.describe(user="User to reply to", response="Message to send")
    async def reply_modmail_slash(self, interaction: discord.Interaction, user: discord.User, response: str):
        member = None
        if interaction.guild:
            member = interaction.guild.get_member(interaction.user.id)
        if not (member and member.guild_permissions.manage_messages):
            await interaction.response.send_message("Bruhhh!!! You don't have permission to use this command.", ephemeral=True)
            return
        try:
            # Send moderator reply as an embed to the user
            reply_embed = discord.Embed(
                title="Moderator Reply",
                description=response,
                color=discord.Color.green()
            )
            try:
                avatar_url = None
                if hasattr(interaction.user, 'display_avatar') and getattr(interaction.user, 'display_avatar'):
                    avatar_url = interaction.user.display_avatar.url
                reply_embed.set_author(name=interaction.user.display_name, icon_url=avatar_url)
            except Exception:
                pass
            await user.send(embed=reply_embed)
            await interaction.response.send_message("Reply sent.", ephemeral=True)
            reset_at = (datetime.utcnow() + timedelta(seconds=self.RESET_DELAY_SECONDS)).isoformat()
            self.modmail_sessions[user.id] = {'state': 'resolved', 'reset_at': reset_at}
            logger.info(f"modmail: scheduled reset for user {user.id} at {reset_at}")
            info_embed = discord.Embed(
                title="You may send another message soon",
                description="A moderator has responded. If you need to send another message, your session is open. This session will reset after a short period of inactivity.",
                color=discord.Color.blue()
            )
            await user.send(embed=info_embed)
            try:
                self._persist_sessions_to_file()
            except Exception:
                logger.exception(f"modmail: failed to persist scheduled reset for {user.id}")
            # Notify modmail channel
            if self.modmail_channel_id:
                channel = self.bot.get_channel(self.modmail_channel_id)
                if channel and isinstance(channel, discord.TextChannel):
                    embed = discord.Embed(
                        title="ModMail Resolved",
                        description=f"Moderator {interaction.user.mention} has replied to {user.mention}'s modmail.\n\n**Reply:** {response}",
                        color=discord.Color.green()
                    )
                    await channel.send(embed=embed)
        except Exception:
            await interaction.response.send_message("Failed to send DM. User may have DMs closed.", ephemeral=True)

    @app_commands.command(name="set_modmail_channel", description="Set the modmail channel (admin only)")
    @app_commands.describe(channel="Channel to set as modmail")
    async def set_modmail_channel_slash(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        member = None
        if interaction.guild:
            member = interaction.guild.get_member(interaction.user.id)
        if not (member and member.guild_permissions.administrator):
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return
        if not channel:
            if isinstance(interaction.channel, discord.TextChannel):
                channel = interaction.channel
            else:
                await interaction.response.send_message("Please specify a text channel or use this in a text channel.", ephemeral=True)
                return
        self.modmail_channel_id = channel.id
        await interaction.response.send_message(f"Modmail channel set to {channel.mention}.", ephemeral=True)

async def setup(bot):
    config = getattr(bot, 'config', None)
    if config is None:
        raise RuntimeError("Bot config is missing. Cannot load ModMail cog.")
    await bot.add_cog(ModMail(bot, config))
