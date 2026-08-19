"""cogs/bump_leaderboard.py

Bump leaderboard cog.

What this does
-------------
Counts bumps done via a **Bump Reminder** embed in a configured bump channel.

Important technical note
------------------------
Discord does not expose *another bot/app's* slash-command interactions to your bot.
Instead, we listen for a bump confirmation embed ("Bump Reminder") and attribute
the bump to the user name stored in the embed title.

Data is stored in the SQLite database (`botdata.db`).

Note: This implementation intentionally does NOT migrate/import existing JSON data.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

from utils.database import DATABASE_NAME

logger = logging.getLogger(__name__)


DATA_VERSION = 1
DEFAULT_COOLDOWN_SECONDS = 60  # basic anti-spam; adjust as needed

# Minimal signal to identify a "bump" embed.
_BUMP_CMD_RE = re.compile(r"\b/bump\b", re.IGNORECASE)


def _utcnow() -> datetime:
    return discord.utils.utcnow()


def _dt_to_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _iso_to_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


@dataclass(frozen=True)
class BumpEntry:
    user_id: int
    username: str
    total_bumps: int
    last_bump_time: datetime | None


class BumpLeaderboard(commands.Cog):
    """Track bumps in a configured channel and provide leaderboards."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self._db_path = Path(DATABASE_NAME)
        self._db_lock = asyncio.Lock()
        self._db_ready = False

        self._lock = asyncio.Lock()

        # In-memory cache to avoid repeatedly parsing ISO strings for cooldown checks.
        self._last_bump_cache: dict[int, dict[int, datetime]] = {}

        # Prevent double counting when the same bump message is edited/reposted.
        self._processed_message_ids: dict[int, float] = {}

        # Ensure DB tables exist (no JSON migration).
        self.bot.loop.create_task(self.load_data())

    # ----------------------------
    # Bump Reminder embed parsing
    # ----------------------------

    def _looks_like_bump_reminder_embed(self, embed: discord.Embed) -> bool:
        """Return True if an embed looks like a bump confirmation."""
        # The screenshot shows a field like "Command ran: /bump".
        for f in embed.fields or []:
            name = (f.name or "").strip()
            value = (f.value or "").strip()
            if _BUMP_CMD_RE.search(name) or _BUMP_CMD_RE.search(value):
                return True

        # Fallback: search embed text blob.
        parts: list[str] = []
        if embed.title:
            parts.append(str(embed.title))
        if embed.description:
            parts.append(str(embed.description))
        for f in embed.fields or []:
            if f.name:
                parts.append(str(f.name))
            if f.value:
                parts.append(str(f.value))
        return _BUMP_CMD_RE.search("\n".join(parts) or "") is not None

    def _extract_bumper_name_from_embeds(
        self, message: discord.Message
    ) -> str | None:
        """Return bumper username from the bump embed title."""
        for emb in message.embeds or []:
            if not emb or not emb.title:
                continue
            if not self._looks_like_bump_reminder_embed(emb):
                continue
            name = str(emb.title).strip()
            if name:
                return name
        return None

    def _resolve_member_by_name(
        self, guild: discord.Guild, name: str
    ) -> discord.Member | None:
        """Resolve a guild member by display name / username (best-effort)."""
        # discord.py helper: matches nick / name / name#discrim..
        try:
            m = guild.get_member_named(name)
            if m is not None:
                return m
        except Exception:
            pass

        needle = name.casefold()
        for member in guild.members:
            if (
                member.display_name.casefold() == needle
                or member.name.casefold() == needle
            ):
                return member
        return None

    def _cleanup_processed_cache(self) -> None:
        # Keep ~10 minutes of ids; enough to cover edits/reposts.
        cutoff = time.monotonic() - 600
        stale = [mid for mid, ts in self._processed_message_ids.items() if ts < cutoff]
        for mid in stale:
            self._processed_message_ids.pop(mid, None)

    async def _handle_possible_bump_reminder_bump(
        self, message: discord.Message
    ) -> None:
        if message.guild is None:
            return

        await self.load_data()
        bump_channel_id = await self._get_bump_channel_id(message.guild.id)

        if not bump_channel_id:
            return

        if message.channel.id != int(bump_channel_id):
            return

        bumper_name = self._extract_bumper_name_from_embeds(message)
        if not bumper_name:
            return

        bumper_member = self._resolve_member_by_name(message.guild, bumper_name)
        if bumper_member is None:
            # If we can't resolve the member, do not guess.
            return

        # Deduplicate message id (Disboard often edits the same message).
        self._cleanup_processed_cache()
        if message.id in self._processed_message_ids:
            return
        self._processed_message_ids[message.id] = time.monotonic()

        # Count the bump (+1) and thank the user.
        await self.update_bump_count(
            message.guild,
            bumper_member,
            now=message.created_at or _utcnow(),
            amount=1,
            bypass_cooldown=True,
        )

        try:
            await message.channel.send(f"Thanks {bumper_member.mention} for bump")
        except Exception:
            pass

    # ----------------------------
    # Event listeners
    # ----------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        # Do not react to our own bot.
        if message.author and message.author.id == getattr(self.bot.user, "id", None):
            return
        try:
            await self._handle_possible_bump_reminder_bump(message)
        except Exception:
            logger.exception("Failed handling possible bump reminder message")

    @commands.Cog.listener()
    async def on_message_edit(
        self, before: discord.Message, after: discord.Message
    ) -> None:
        # Some apps may edit the confirmation message; handle edits too.
        if after.author and after.author.id == getattr(self.bot.user, "id", None):
            return
        try:
            await self._handle_possible_bump_reminder_bump(after)
        except Exception:
            logger.exception("Failed handling edited bump reminder message")

    # ----------------------------
    # Persistence helpers
    # ----------------------------

    async def load_data(self) -> None:
        """Ensure the bump leaderboard tables exist."""
        if self._db_ready:
            return

        async with self._db_lock:
            if self._db_ready:
                return

            async with aiosqlite.connect(self._db_path) as db:
                await db.execute("PRAGMA journal_mode=WAL")

                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS bump_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                    """
                )
                await db.execute(
                    "INSERT OR IGNORE INTO bump_settings (key, value) VALUES (?, ?)",
                    ("cooldown_seconds", str(DEFAULT_COOLDOWN_SECONDS)),
                )

                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS bump_guild_config (
                        guild_id INTEGER PRIMARY KEY,
                        bump_channel_id INTEGER
                    )
                    """
                )

                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS bump_guild_stats (
                        guild_id INTEGER PRIMARY KEY,
                        total_bumps INTEGER NOT NULL DEFAULT 0,
                        last_bumper_id INTEGER,
                        last_bump_time TEXT
                    )
                    """
                )

                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS bump_user_stats (
                        guild_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        username TEXT,
                        total_bumps INTEGER NOT NULL DEFAULT 0,
                        last_bump_time TEXT,
                        PRIMARY KEY (guild_id, user_id)
                    )
                    """
                )

                await db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_bump_user_stats_total ON bump_user_stats (guild_id, total_bumps DESC)"
                )
                await db.commit()

            self._db_ready = True

    async def _get_cooldown_seconds(self) -> int:
        await self.load_data()
        async with aiosqlite.connect(self._db_path) as db, db.execute(
            "SELECT value FROM bump_settings WHERE key = ?",
            ("cooldown_seconds",),
        ) as cursor:
            row = await cursor.fetchone()

        if not row or row[0] is None:
            return DEFAULT_COOLDOWN_SECONDS
        return _safe_int(row[0], DEFAULT_COOLDOWN_SECONDS)

    async def _get_bump_channel_id(self, guild_id: int) -> int | None:
        await self.load_data()
        async with aiosqlite.connect(self._db_path) as db, db.execute(
            "SELECT bump_channel_id FROM bump_guild_config WHERE guild_id = ?",
            (int(guild_id),),
        ) as cursor:
            row = await cursor.fetchone()
        if not row or row[0] is None:
            return None
        try:
            return int(row[0])
        except (TypeError, ValueError):
            return None

    async def _set_bump_channel_id(self, guild_id: int, channel_id: int) -> None:
        await self.load_data()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO bump_guild_config (guild_id, bump_channel_id) VALUES (?, ?)",
                (int(guild_id), int(channel_id)),
            )
            await db.execute(
                "INSERT OR IGNORE INTO bump_guild_stats (guild_id, total_bumps) VALUES (?, 0)",
                (int(guild_id),),
            )
            await db.commit()

    def _format_relative_time(self, dt: datetime | None) -> str:
        if not dt:
            return "Never"
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        ts = int(dt.timestamp())
        return f"<t:{ts}:R>"

    def _format_full_time(self, dt: datetime | None) -> str:
        if not dt:
            return "Never"
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        ts = int(dt.timestamp())
        return f"<t:{ts}:f>"

    # ----------------------------
    # Core bump logic
    # ----------------------------

    async def update_bump_count(
        self,
        guild: discord.Guild,
        user: discord.abc.User,
        *,
        now: datetime | None = None,
        amount: int = 1,
        bypass_cooldown: bool = False,
    ) -> tuple[bool, float | None]:
        """Update a user's bump count.

        Returns:
            (ok, retry_after_seconds)
        """
        now = now or _utcnow()

        await self.load_data()
        now_iso = _dt_to_iso(now)
        username = getattr(user, "display_name", getattr(user, "name", str(user.id)))

        async with self._lock:
            cooldown = await self._get_cooldown_seconds()

            async with aiosqlite.connect(self._db_path) as db:
                await db.execute("PRAGMA journal_mode=WAL")

                async with db.execute(
                    "SELECT total_bumps, last_bump_time FROM bump_user_stats WHERE guild_id = ? AND user_id = ?",
                    (int(guild.id), int(user.id)),
                ) as cursor:
                    row = await cursor.fetchone()

                current_total = _safe_int(row[0], 0) if row else 0
                last_dt: datetime | None = None

                # Prefer in-memory timestamp cache.
                last_dt = self._last_bump_cache.get(guild.id, {}).get(user.id)
                if last_dt is None and row:
                    last_dt = _iso_to_dt(row[1])

                # Cooldown check (only for positive increments).
                if amount > 0 and not bypass_cooldown and last_dt is not None:
                    elapsed = (now - last_dt).total_seconds()
                    if elapsed < cooldown:
                        return False, float(cooldown - elapsed)

                new_total = max(0, current_total + int(amount))
                new_last_bump_time = (
                    now_iso if amount > 0 else (row[1] if row else None)
                )

                await db.execute(
                    """
                    INSERT INTO bump_user_stats (guild_id, user_id, username, total_bumps, last_bump_time)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(guild_id, user_id) DO UPDATE SET
                        username = excluded.username,
                        total_bumps = excluded.total_bumps,
                        last_bump_time = excluded.last_bump_time
                    """,
                    (
                        int(guild.id),
                        int(user.id),
                        str(username),
                        int(new_total),
                        new_last_bump_time,
                    ),
                )

                await db.execute(
                    "INSERT OR IGNORE INTO bump_guild_stats (guild_id, total_bumps) VALUES (?, 0)",
                    (int(guild.id),),
                )

                async with db.execute(
                    "SELECT COALESCE(SUM(total_bumps), 0) FROM bump_user_stats WHERE guild_id = ?",
                    (int(guild.id),),
                ) as cursor:
                    total_row = await cursor.fetchone()

                total_bumps = _safe_int(total_row[0], 0) if total_row else 0

                if amount > 0:
                    await db.execute(
                        "UPDATE bump_guild_stats SET total_bumps = ?, last_bumper_id = ?, last_bump_time = ? WHERE guild_id = ?",
                        (int(total_bumps), int(user.id), now_iso, int(guild.id)),
                    )
                    self._last_bump_cache.setdefault(guild.id, {})[user.id] = now
                else:
                    await db.execute(
                        "UPDATE bump_guild_stats SET total_bumps = ? WHERE guild_id = ?",
                        (int(total_bumps), int(guild.id)),
                    )

                await db.commit()

        return True, None

    async def get_leaderboard(
        self, guild: discord.Guild, limit: int = 10
    ) -> list[BumpEntry]:
        """Return sorted bump leaderboard for the guild."""
        await self.load_data()
        lim = max(1, int(limit))

        async with aiosqlite.connect(self._db_path) as db, db.execute(
            """
                SELECT user_id, username, total_bumps, last_bump_time
                FROM bump_user_stats
                WHERE guild_id = ?
                ORDER BY total_bumps DESC, COALESCE(last_bump_time, '') DESC
                LIMIT ?
                """,
            (int(guild.id), int(lim)),
        ) as cursor:
            fetched = await cursor.fetchall()

        rows: list[BumpEntry] = []
        for user_id, username, total_bumps, last_bump_time in fetched or []:
            rows.append(
                BumpEntry(
                    user_id=_safe_int(user_id, 0),
                    username=str(username or f"{user_id}"),
                    total_bumps=_safe_int(total_bumps, 0),
                    last_bump_time=_iso_to_dt(last_bump_time),
                )
            )
        return rows

    async def get_my_stats(
        self, guild: discord.Guild, user: discord.abc.User
    ) -> BumpEntry:
        await self.load_data()
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT username, total_bumps, last_bump_time FROM bump_user_stats WHERE guild_id = ? AND user_id = ?",
                (int(guild.id), int(user.id)),
            ) as cursor:
                row = await cursor.fetchone()

        if not row:
            return BumpEntry(
                user_id=int(user.id),
                username=str(
                    getattr(user, "display_name", getattr(user, "name", str(user.id)))
                ),
                total_bumps=0,
                last_bump_time=None,
            )

        username, total_bumps, last_bump_time = row
        return BumpEntry(
            user_id=int(user.id),
            username=str(
                username
                or getattr(user, "display_name", getattr(user, "name", str(user.id)))
            ),
            total_bumps=_safe_int(total_bumps, 0),
            last_bump_time=_iso_to_dt(last_bump_time),
        )

    async def get_bump_stats(
        self, guild: discord.Guild
    ) -> tuple[int, int | None, datetime | None]:
        await self.load_data()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO bump_guild_stats (guild_id, total_bumps) VALUES (?, 0)",
                (int(guild.id),),
            )
            await db.commit()

            async with db.execute(
                "SELECT total_bumps, last_bumper_id, last_bump_time FROM bump_guild_stats WHERE guild_id = ?",
                (int(guild.id),),
            ) as cursor:
                row = await cursor.fetchone()

        if not row:
            return 0, None, None

        total_bumps, last_bumper_id, last_bump_time = row
        last_bumper = _safe_int(last_bumper_id, 0) or None
        return _safe_int(total_bumps, 0), last_bumper, _iso_to_dt(last_bump_time)

    # ----------------------------
    # Permission helpers
    # ----------------------------

    def _is_manage_guild_member(self, member: discord.Member) -> bool:
        return member.guild_permissions.manage_guild

    async def _ensure_manage_guild(self, ctx: commands.Context) -> bool:
        if ctx.guild is None:
            await ctx.send("Server-only command.")
            return False
        if not isinstance(ctx.author, discord.Member):
            await ctx.send("Server member only.")
            return False
        if not self._is_manage_guild_member(ctx.author):
            await ctx.send(
                "You need the **Manage Server** permission to use this command."
            )
            return False
        return True

    async def _ensure_manage_guild_interaction(
        self, interaction: discord.Interaction
    ) -> bool:
        if interaction.guild is None:
            await interaction.response.send_message(
                "Server-only command.", ephemeral=True
            )
            return False
        if isinstance(interaction.user, discord.Member):
            if interaction.user.guild_permissions.manage_guild:
                return True
            await interaction.response.send_message(
                "You need the **Manage Server** permission to use this command.",
                ephemeral=True,
            )
            return False

        try:
            member = await interaction.guild.fetch_member(interaction.user.id)
        except Exception:
            await interaction.response.send_message(
                "Could not verify permissions.", ephemeral=True
            )
            return False

        if member.guild_permissions.manage_guild:
            return True
        await interaction.response.send_message(
            "You need the **Manage Server** permission to use this command.",
            ephemeral=True,
        )
        return False

    # ----------------------------
    # Hybrid commands (slash + prefix)
    # ----------------------------

    @commands.hybrid_command(
        name="bumplb", description="Show the bump leaderboard (top 10)"
    )
    async def bumplb(self, ctx: commands.Context):
        if ctx.guild is None:
            return await ctx.send("Server-only command.")

        await self.load_data()
        rows = await self.get_leaderboard(ctx.guild, limit=10)

        embed = discord.Embed(
            title="🏆 Bump Leaderboard",
            description="Top 10 bumpers in this server",
            color=discord.Color.blurple(),
        )

        if not rows or all(r.total_bumps == 0 for r in rows):
            embed.description = "No bumps recorded yet. Use Disboard's `/bump` in the bump channel to get started."
            return await ctx.send(embed=embed)

        lines: list[str] = []
        medals = ["🥇", "🥈", "🥉"]
        for i, r in enumerate(rows, start=1):
            rank = medals[i - 1] if i <= 3 else f"`#{i}`"
            lines.append(
                f"{rank} <@{r.user_id}> -> **{r.total_bumps}** bumps · last: {self._format_relative_time(r.last_bump_time)}"
            )

        embed.add_field(name="Rankings", value="\n".join(lines), inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="bumpstats", description="Show total bumps and the most recent bumper"
    )
    async def bumpstats(self, ctx: commands.Context):
        if ctx.guild is None:
            return await ctx.send("Server-only command.")

        await self.load_data()
        total, last_bumper_id, last_bump_time = await self.get_bump_stats(ctx.guild)

        embed = discord.Embed(title="📈 Bump Stats", color=discord.Color.gold())
        embed.add_field(name="Total bumps", value=str(total), inline=True)

        if last_bumper_id:
            embed.add_field(
                name="Most recent bumper", value=f"<@{last_bumper_id}>", inline=True
            )
            embed.add_field(
                name="Last bump",
                value=self._format_full_time(last_bump_time),
                inline=False,
            )
        else:
            embed.add_field(name="Most recent bumper", value="None yet", inline=True)

        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="setbumpchannel", description="Set the channel where bumps count"
    )
    @app_commands.describe(channel="Channel where Disboard bumps should be counted")
    async def setbumpchannel(self, ctx: commands.Context, channel: discord.TextChannel):
        if not await self._ensure_manage_guild(ctx):
            return

        await self._set_bump_channel_id(ctx.guild.id, channel.id)  # type: ignore[union-attr]

        embed = discord.Embed(
            title="✅ Bump channel set",
            description=f"Bumps will now count in {channel.mention}.",
            color=discord.Color.green(),
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="addbumps", description="Admin: add bumps to a user")
    @app_commands.describe(user="User to modify", amount="Number of bumps to add")
    async def addbumps(self, ctx: commands.Context, user: discord.Member, amount: int):
        if not await self._ensure_manage_guild(ctx):
            return

        if amount < 1 or amount > 100000:
            return await ctx.send("Amount must be between 1 and 100000.")

        await self.load_data()
        ok, _ = await self.update_bump_count(
            ctx.guild, user, amount=int(amount), bypass_cooldown=True
        )  # type: ignore[arg-type]
        if not ok:
            # bypass_cooldown=True should always be ok
            pass

        entry = await self.get_my_stats(ctx.guild, user)  # type: ignore[arg-type]
        embed = discord.Embed(
            title="✅ Bumps added",
            description=f"Added **{amount}** bumps to {user.mention}.\nTotal: **{entry.total_bumps}**",
            color=discord.Color.green(),
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="removebumps", description="Admin: remove bumps from a user"
    )
    @app_commands.describe(user="User to modify", amount="Number of bumps to remove")
    async def removebumps(
        self, ctx: commands.Context, user: discord.Member, amount: int
    ):
        if not await self._ensure_manage_guild(ctx):
            return

        if amount < 1 or amount > 100000:
            return await ctx.send("Amount must be between 1 and 100000.")

        await self.load_data()
        ok, _ = await self.update_bump_count(
            ctx.guild, user, amount=-int(amount), bypass_cooldown=True
        )  # type: ignore[arg-type]
        if not ok:
            pass

        entry = await self.get_my_stats(ctx.guild, user)  # type: ignore[arg-type]
        embed = discord.Embed(
            title="✅ Bumps removed",
            description=f"Removed **{amount}** bumps from {user.mention}.\nTotal: **{entry.total_bumps}**",
            color=discord.Color.orange(),
        )
        await ctx.send(embed=embed)

    # ----------------------------
    # Prefix-only commands (requested aliases)
    # ----------------------------

    @commands.command(name="mybumps")
    async def mybumps(self, ctx: commands.Context):
        """Prefix-only: show your bump stats."""
        if ctx.guild is None:
            return await ctx.send("Server-only command.")

        await self.load_data()
        entry = await self.get_my_stats(ctx.guild, ctx.author)

        embed = discord.Embed(title="🙋 Your bumps", color=discord.Color.blurple())
        embed.add_field(name="Total bumps", value=str(entry.total_bumps), inline=True)
        embed.add_field(
            name="Last bump",
            value=self._format_full_time(entry.last_bump_time),
            inline=False,
        )
        await ctx.send(embed=embed)

    @commands.command(name="blb")
    async def blb(self, ctx: commands.Context):
        """Prefix-only alias for bump leaderboard."""
        await self.bumplb(ctx)  # reuse hybrid handler

    @commands.command(name="bst")
    async def bst(self, ctx: commands.Context):
        """Prefix-only alias for bump stats."""
        await self.bumpstats(ctx)

    @commands.command(name="topbump")
    async def topbump(self, ctx: commands.Context):
        """Prefix-only: show top 3 bumpers."""
        if ctx.guild is None:
            return await ctx.send("Server-only command.")

        await self.load_data()
        rows = await self.get_leaderboard(ctx.guild, limit=3)

        embed = discord.Embed(title="🥇 Top bumpers", color=discord.Color.blurple())
        if not rows or all(r.total_bumps == 0 for r in rows):
            embed.description = "No bumps recorded yet."
            return await ctx.send(embed=embed)

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, r in enumerate(rows, start=1):
            lines.append(f"{medals[i - 1]} <@{r.user_id}> -> **{r.total_bumps}**")
        embed.add_field(name="Top 3", value="\n".join(lines), inline=False)
        await ctx.send(embed=embed)

    # ----------------------------
    # Error handling for prefix commands
    # ----------------------------

    @addbumps.error
    @removebumps.error
    @setbumpchannel.error
    async def _admin_prefix_error(
        self, ctx: commands.Context, error: commands.CommandError
    ):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have permission to use this command.")
            return
        if isinstance(error, commands.BadArgument):
            await ctx.send(
                "Invalid argument. Please mention a valid user/channel and amount."
            )
            return
        await ctx.send("An error occurred while processing your command.")


async def setup(bot: commands.Bot):
    """Load the bump leaderboard cog."""
    await bot.add_cog(BumpLeaderboard(bot))
