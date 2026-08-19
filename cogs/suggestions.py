"""cogs/suggestions.py

Suggestion system for Eigen Bot.

Behavior:
- Users run `/suggest <message>` (hybrid command).
- Bot posts an embed to a configured suggestions channel.
- Bot adds reaction voting (approve / reject / neutral).
- Bot creates a discussion thread from that suggestion message.

Configuration:
- Admins set the suggestions channel with `/setsuggestchannel #channel`.
- Settings are persisted in the SQLite database (`botdata.db`).

This keeps the main suggestions channel clean while enabling organized discussion.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

from utils.database import DATABASE_NAME

logger = logging.getLogger(__name__)


DATA_VERSION = 1

VOTE_APPROVE = "✅"
VOTE_REJECT = "❌"
VOTE_NEUTRAL = "😐"


class Suggestions(commands.Cog):
    """Suggestion submission + voting + threads."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self._db_path = Path(DATABASE_NAME)
        self._db_lock = asyncio.Lock()
        self._db_ready = False

    async def _ensure_db(self) -> None:
        """Ensure the suggestions config table exists.

        Note: This intentionally does NOT import/migrate existing JSON config.
        """
        if self._db_ready:
            return

        async with self._db_lock:
            if self._db_ready:
                return

            async with aiosqlite.connect(self._db_path) as db:
                await db.execute("PRAGMA journal_mode=WAL")
                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS suggestions_config (
                        guild_id INTEGER PRIMARY KEY,
                        suggestions_channel_id INTEGER
                    )
                    """
                )
                await db.commit()

            self._db_ready = True

    async def _get_suggestions_channel_id(self, guild_id: int) -> int | None:
        await self._ensure_db()

        async with aiosqlite.connect(self._db_path) as db, db.execute(
            "SELECT suggestions_channel_id FROM suggestions_config WHERE guild_id = ?",
            (int(guild_id),),
        ) as cursor:
            row = await cursor.fetchone()

        if not row or row[0] is None:
            return None
        try:
            return int(row[0])
        except (TypeError, ValueError):
            return None

    # ----------------------------
    # Permission helpers
    # ----------------------------

    async def _ensure_manage_guild(self, ctx: commands.Context) -> bool:
        if ctx.guild is None:
            await ctx.send("Server-only command.")
            return False
        if not isinstance(ctx.author, discord.Member):
            await ctx.send("Server member only.")
            return False
        if not ctx.author.guild_permissions.manage_guild:
            await ctx.send("You need the **Manage Server** permission to use this command.")
            return False
        return True

    # ----------------------------
    # Commands
    # ----------------------------

    async def _safe_respond(
        self,
        ctx: commands.Context,
        content: str | None = None,
        *,
        embed: discord.Embed | None = None,
        ephemeral: bool = False,
    ) -> None:
        """Respond without crashing on expired slash interactions.

        For hybrid commands invoked as slash commands, Discord requires a response within
        a short window. If the interaction expires, fallback to channel send.
        """
        interaction = getattr(ctx, "interaction", None)
        payload: dict[str, Any] = {}
        if content is not None:
            payload["content"] = content
        if embed is not None:
            payload["embed"] = embed

        if interaction is not None:
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(**payload, ephemeral=ephemeral)
                    return
                await interaction.followup.send(**payload, ephemeral=ephemeral)
                return
            except (discord.NotFound, discord.HTTPException, discord.Forbidden):
                pass
            except Exception:
                pass

        try:
            if ctx.channel is not None:
                await ctx.channel.send(**payload)
        except Exception:
            return

    @commands.hybrid_command(name="setsuggestchannel", description="Set the channel where suggestions are posted")
    @app_commands.describe(channel="Channel where suggestions should be posted")
    async def setsuggestchannel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Admin: configure suggestions channel."""
        # If invoked as a slash command, defer quickly to avoid interaction expiry.
        if ctx.interaction is not None:
            try:
                await ctx.defer(ephemeral=True)
            except Exception:
                pass

        if not await self._ensure_manage_guild(ctx):
            return

        await self._ensure_db()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO suggestions_config (guild_id, suggestions_channel_id) VALUES (?, ?)",
                (int(ctx.guild.id), int(channel.id)),  # type: ignore[union-attr]
            )
            await db.commit()

        embed = discord.Embed(
            title="Suggestions channel set",
            description=f"Suggestions will now be posted in {channel.mention}.",
            color=discord.Color.green(),
        )
        await self._safe_respond(ctx, embed=embed, ephemeral=True)

    @commands.hybrid_command(name="suggest", description="Submit a suggestion to the server")
    @app_commands.describe(message="Your suggestion")
    async def suggest(self, ctx: commands.Context, *, message: str):
        """Submit a suggestion and create a discussion thread."""
        if ctx.guild is None:
            await self._safe_respond(ctx, "Server-only command.", ephemeral=True)
            return

        # If invoked as a slash command, defer quickly to avoid interaction expiry.
        if ctx.interaction is not None:
            try:
                await ctx.defer(ephemeral=True)
            except Exception:
                pass

        # Basic validation
        content = message.strip()
        if not content:
            await self._safe_respond(ctx, "Please provide a suggestion message.", ephemeral=True)
            return
        if len(content) > 1800:
            await self._safe_respond(ctx, "Suggestion is too long. Please keep it under 1800 characters.", ephemeral=True)
            return

        channel_id = await self._get_suggestions_channel_id(ctx.guild.id)
        if not channel_id:
            await self._safe_respond(
                ctx,
                "Suggestions channel is not configured. An admin can set it with `/setsuggestchannel`.",
                ephemeral=True,
            )
            return

        target_channel = ctx.guild.get_channel(channel_id)
        if target_channel is None:
            try:
                target_channel = await ctx.guild.fetch_channel(channel_id)
            except Exception:
                target_channel = None

        if not isinstance(target_channel, discord.TextChannel):
            await self._safe_respond(ctx, "Configured suggestions channel is invalid or not a text channel.", ephemeral=True)
            return

        embed = discord.Embed(
            title="New Suggestion",
            description=content,
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_author(name=str(ctx.author), icon_url=getattr(ctx.author.display_avatar, "url", None))
        embed.add_field(name="Author", value=ctx.author.mention, inline=True)

        try:
            suggestion_msg = await target_channel.send(embed=embed)
        except discord.Forbidden:
            await self._safe_respond(ctx, "I don't have permission to post in the suggestions channel.", ephemeral=True)
            return
        except Exception:
            logger.exception("Failed to post suggestion")
            await self._safe_respond(ctx, "An error occurred while posting your suggestion.", ephemeral=True)
            return

        # Add voting reactions
        try:
            await suggestion_msg.add_reaction(VOTE_APPROVE)
            await suggestion_msg.add_reaction(VOTE_REJECT)
            await suggestion_msg.add_reaction(VOTE_NEUTRAL)
        except discord.Forbidden:
            # Not critical; continue
            pass
        except Exception:
            pass

        # Create discussion thread
        try:
            await suggestion_msg.create_thread(
                name="Suggestion Discussion",
                auto_archive_duration=1440,
                reason="Suggestion discussion thread",
            )
        except discord.Forbidden:
            # Inform the user but don't fail the suggestion itself.
            await self._safe_respond(
                ctx,
                "Suggestion posted, but I couldn't create a thread (missing permissions).",
                ephemeral=True,
            )
        except Exception:
            logger.exception("Failed to create suggestion thread")

        # Acknowledge to the user
        ack = discord.Embed(
            title="Suggestion submitted",
            description=f"Posted in {target_channel.mention}.",
            color=discord.Color.green(),
        )
        await self._safe_respond(ctx, embed=ack, ephemeral=True)

    # ----------------------------
    # Errors
    # ----------------------------

    @setsuggestchannel.error
    async def _setsuggestchannel_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            return await ctx.send("You don't have permission to use this command.")
        if isinstance(error, commands.BadArgument):
            return await ctx.send("Invalid channel.")
        logger.exception("setsuggestchannel error: %s", error)
        await ctx.send("An error occurred.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Suggestions(bot))
