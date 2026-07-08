"""
Staff guide cog for Eigen bot.

Automatically sends a staff guide embed via DM when a member receives the Staff role.
Includes admin commands for manual sending, resending, and previewing the guide.
"""

import logging
from typing import Optional, Set

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

from utils.database import DATABASE_NAME
from utils.helpers import EmbedBuilder

logger = logging.getLogger(__name__)

STAFF_ROLE_ID = 1403059755001577543
LOG_CHANNEL_ID = 1482343273459875962


class StaffGuide(commands.Cog):
    """Staff guide and rules delivery system."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._processing: Set[int] = set()

    async def cog_load(self) -> None:
        """Initialize database table on cog load."""
        async with aiosqlite.connect(DATABASE_NAME) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS staff_guide_sent (
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    sent_at INTEGER NOT NULL,
                    PRIMARY KEY (user_id, guild_id)
                )
            """)
            await db.commit()
        logger.info("StaffGuide cog loaded")

    async def _has_received_guide(self, user_id: int, guild_id: int) -> bool:
        """Check if a user has already received the staff guide."""
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute(
                "SELECT 1 FROM staff_guide_sent WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id),
            ) as cursor:
                return await cursor.fetchone() is not None

    async def _mark_guide_sent(self, user_id: int, guild_id: int) -> None:
        """Mark a user as having received the staff guide."""
        async with aiosqlite.connect(DATABASE_NAME) as db:
            await db.execute(
                "INSERT OR IGNORE INTO staff_guide_sent (user_id, guild_id, sent_at) VALUES (?, ?, ?)",
                (user_id, guild_id, int(discord.utils.utcnow().timestamp())),
            )
            await db.commit()

    def _build_staff_guide_embed(self) -> discord.Embed:
        """Build the staff guide embed."""
        embed = discord.Embed(
            title="Welcome to the Staff Team",
            description=(
                "Welcome to the staff team.\n"
                "This guide explains your responsibilities, expectations, "
                "and important rules. Please read everything carefully."
            ),
            color=0x000000,
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(
            name="Responsibilities",
            value=(
                "Staff members are expected to:\n"
                "- Help members respectfully\n"
                "- Enforce server rules fairly\n"
                "- Report serious issues\n"
                "- Be active when possible\n"
                "- Remain professional"
            ),
            inline=False,
        )
        embed.add_field(
            name="Staff Rules",
            value=(
                "- Do not abuse permissions.\n"
                "- Do not leak internal information.\n"
                "- Treat everyone respectfully.\n"
                "- Stay impartial.\n"
                "- Follow management instructions.\n"
                "- Do not argue publicly with members.\n"
                "- Use moderation powers only when necessary."
            ),
            inline=False,
        )
        embed.add_field(
            name="Need Help?",
            value=(
                "If you have any questions about moderation or staff "
                "procedures, contact a senior staff member or administrator."
            ),
            inline=False,
        )
        embed.set_footer(text="Eigen Staff Guide")
        return embed

    async def _send_guide(
        self,
        member: discord.Member,
        triggered_by: str = "Automatic",
        force: bool = False,
    ) -> str:
        """
        Send the staff guide to a member.

        Parameters
        ----------
        member:
            The member to send the guide to.
        triggered_by:
            How the send was triggered (Automatic, Manual, Resend).
        force:
            If True, bypass the already-sent check.

        Returns
        -------
        str
            Status string: SUCCESS, FAILED, or SKIPPED.
        """
        user_id = member.id
        guild_id = member.guild.id

        if member.bot:
            await self._log_action(member, triggered_by, "SKIPPED", "User is a bot")
            return "SKIPPED"

        if not force and user_id in self._processing:
            await self._log_action(
                member, triggered_by, "SKIPPED", "Already being processed"
            )
            return "SKIPPED"

        if not force and await self._has_received_guide(user_id, guild_id):
            await self._log_action(
                member, triggered_by, "SKIPPED", "Already received guide"
            )
            return "SKIPPED"

        self._processing.add(user_id)
        try:
            embed = self._build_staff_guide_embed()
            await member.send(embed=embed)
            await self._mark_guide_sent(user_id, guild_id)
            await self._log_action(member, triggered_by, "SUCCESS")
            return "SUCCESS"
        except discord.Forbidden:
            await self._log_action(
                member, triggered_by, "FAILED", "Forbidden (DMs closed)"
            )
            return "FAILED"
        except discord.HTTPException as e:
            await self._log_action(member, triggered_by, "FAILED", str(e))
            return "FAILED"
        except discord.NotFound:
            await self._log_action(member, triggered_by, "FAILED", "Member not found")
            return "FAILED"
        except Exception as e:
            logger.exception(f"Unexpected error sending guide to {user_id}: {e}")
            await self._log_action(
                member, triggered_by, "FAILED", f"Unknown error: {e}"
            )
            return "FAILED"
        finally:
            self._processing.discard(user_id)

    async def _log_action(
        self,
        member: discord.Member,
        triggered_by: str,
        status: str,
        reason: Optional[str] = None,
    ) -> None:
        """Log a staff guide action to the log channel."""
        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            logger.warning(f"Log channel {LOG_CHANNEL_ID} not found")
            return

        color_map = {
            "SUCCESS": discord.Color.green(),
            "FAILED": discord.Color.red(),
            "SKIPPED": discord.Color.orange(),
        }

        embed = discord.Embed(
            title="Staff Guide Delivery",
            color=color_map.get(status, discord.Color.default()),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Member", value=member.mention, inline=True)
        embed.add_field(name="ID", value=str(member.id), inline=True)
        embed.add_field(name="Guild", value=member.guild.name, inline=True)
        embed.add_field(name="Triggered By", value=triggered_by, inline=True)
        embed.add_field(name="Status", value=status, inline=True)
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text="Staff Guide System")

        try:
            await log_channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to send log embed: {e}")

    @commands.Cog.listener()
    async def on_member_update(
        self, before: discord.Member, after: discord.Member
    ) -> None:
        """Listen for member role updates to detect staff role additions."""
        if after.bot:
            return

        had_staff = any(role.id == STAFF_ROLE_ID for role in before.roles)
        has_staff = any(role.id == STAFF_ROLE_ID for role in after.roles)

        if not had_staff and has_staff:
            await self._send_guide(after, triggered_by="Automatic")

    async def cog_check(self, ctx: commands.Context) -> bool:
        """Allow only server administrators and bot owner."""
        if self.bot.config.owner_id and ctx.author.id == self.bot.config.owner_id:
            return True
        if ctx.guild is not None:
            member = ctx.guild.get_member(ctx.author.id)
            if member and member.guild_permissions.administrator:
                return True
        return False

    @commands.hybrid_group(
        name="staffrules",
        description="Manage the staff guide system",
    )
    async def staffrules(self, ctx: commands.Context) -> None:
        """Staff guide management commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @staffrules.command(
        name="setup",
        description="View current staff guide configuration",
    )
    async def staffrules_setup(self, ctx: commands.Context) -> None:
        """Display the current configuration and verify permissions."""
        embed = discord.Embed(
            title="Staff Guide Configuration",
            color=0x000000,
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(
            name="Staff Role",
            value=f"<@&{STAFF_ROLE_ID}> (`{STAFF_ROLE_ID}`)",
            inline=False,
        )
        embed.add_field(
            name="Log Channel",
            value=f"<#{LOG_CHANNEL_ID}> (`{LOG_CHANNEL_ID}`)",
            inline=False,
        )
        embed.add_field(
            name="Automatic Delivery",
            value=(
                "Enabled - Staff guide is sent via DM when a member "
                "receives the Staff role."
            ),
            inline=False,
        )
        embed.set_footer(text="Eigen Staff Guide System")
        await ctx.send(embed=embed)

    @staffrules.command(
        name="send",
        description="Send the staff guide to a member",
    )
    @app_commands.describe(member="The member to send the staff guide to")
    async def staffrules_send(
        self, ctx: commands.Context, member: discord.Member
    ) -> None:
        """Send the staff guide to the specified member."""
        status = await self._send_guide(member, triggered_by="Manual")
        if status == "SUCCESS":
            embed = EmbedBuilder.success_embed(
                "Staff Guide Sent",
                f"Staff guide has been sent to {member.mention}.",
            )
        elif status == "SKIPPED":
            embed = EmbedBuilder.info_embed(
                "Staff Guide Skipped",
                f"{member.mention} has already received the staff guide. "
                "Use `?staffrules resend` to force resend.",
            )
        else:
            embed = EmbedBuilder.error_embed(
                "Staff Guide Failed",
                f"Failed to send staff guide to {member.mention}.",
            )
        await ctx.send(embed=embed)

    @staffrules.command(
        name="resend",
        description="Resend the staff guide to a member even if already sent",
    )
    @app_commands.describe(member="The member to resend the staff guide to")
    async def staffrules_resend(
        self, ctx: commands.Context, member: discord.Member
    ) -> None:
        """Resend the staff guide to the specified member, even if already received."""
        status = await self._send_guide(member, triggered_by="Resend", force=True)
        if status == "SUCCESS":
            embed = EmbedBuilder.success_embed(
                "Staff Guide Resent",
                f"Staff guide has been resent to {member.mention}.",
            )
        else:
            embed = EmbedBuilder.error_embed(
                "Staff Guide Failed",
                f"Failed to resend staff guide to {member.mention}.",
            )
        await ctx.send(embed=embed)

    @staffrules.command(
        name="preview",
        description="Preview the staff guide embed",
    )
    async def staffrules_preview(self, ctx: commands.Context) -> None:
        """Send the staff guide embed in the current channel for preview."""
        embed = self._build_staff_guide_embed()
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    """Setup the StaffGuide cog."""
    await bot.add_cog(StaffGuide(bot))
