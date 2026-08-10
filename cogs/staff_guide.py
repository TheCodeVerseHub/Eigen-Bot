"""
Staff guide cog for Eigen bot.

Automatically sends a staff guide via DM when a member receives the Staff role.
Uses Discord's Components V2 for a clean, modern onboarding UI.
Includes admin commands for manual sending, resending, and previewing the guide.
"""

import logging
from typing import Optional, Set

import aiosqlite
import discord
from discord import ButtonStyle, app_commands
from discord.ext import commands
from discord.ui import Button, Container, LayoutView, Section, Separator, TextDisplay

from utils.database import DATABASE_NAME
from utils.helpers import EmbedBuilder

logger = logging.getLogger(__name__)

STAFF_ROLE_ID = 1403059755001577543
LOG_CHANNEL_ID = 1482343273459875962

BRANCH_CHANNEL_URL = (
    "https://discord.com/channels/1263067254153805905/"
    "1413895674705084567/1475200684138696916"
)
GUIDE_CHANNEL_ID = 1413895674705084567
GUIDE_CHANNEL_URL = (
    f"https://discord.com/channels/1263067254153805905/{GUIDE_CHANNEL_ID}"
)
INACTIVITY_CHANNEL_ID = 1452608211948408902
SENIOR_STAFF_ID = 955695820999639120


class StaffGuideLayout(LayoutView):
    """Components V2 layout for the staff guide DM.

    Resembles Discord's native onboarding UI with sections,
    separators, and link buttons for each step.
    """

    def __init__(self, member: discord.Member) -> None:
        super().__init__(timeout=None)

        container = Container(
            # Welcome header
            TextDisplay(
                "## Welcome to the Staff Team\n"
                f"Hey {member.mention}, welcome to the CodeVerse staff team.\n"
                "Please complete the steps below before you begin moderating."
            ),
            Separator(),
            # Step 1
            Section(
                "**Step 1 \u2014 Choose Your Branch**",
                (
                    "Select your staff branch and review the responsibilities "
                    "assigned to it."
                ),
                accessory=Button(
                    label="Open Staff Branch",
                    url=BRANCH_CHANNEL_URL,
                    style=ButtonStyle.link,
                ),
            ),
            Separator(),
            # Step 2
            Section(
                "**Step 2 \u2014 Read the Staff Guide**",
                (
                    "Carefully read the Staff Guide before performing any "
                    "moderation actions."
                ),
                accessory=Button(
                    label="Open Staff Guide",
                    url=GUIDE_CHANNEL_URL,
                    style=ButtonStyle.link,
                ),
            ),
            Separator(),
            # Staff Rules
            TextDisplay(
                "## Staff Rules\n"
                f"- Stay active and responsive. Consistency matters more "
                "than occasional bursts of activity. If you will be inactive, "
                f"notify the team beforehand in <#{INACTIVITY_CHANNEL_ID}>.\n"
                "- Avoid unnecessary conflicts or arguments. Escalate "
                "issues to senior staff whenever needed.\n"
                "- Always follow the server rules yourself. Staff members "
                "are expected to set the standard.\n"
                "- Communicate clearly within staff channels to keep "
                "everyone aligned.\n"
                "- Respect the staff hierarchy and decisions made by "
                "senior moderators and administrators.\n"
                "- Do not misuse your permissions under any circumstances. "
                "Doing so may result in disciplinary action.\n"
                "- Keep sensitive staff discussions confidential.\n"
                "- Contribute ideas that improve the server whenever "
                "possible."
            ),
            Separator(),
            # Need Help?
            TextDisplay(
                "**Need Help?**\n"
                "If you have any questions about moderation, procedures, "
                f"or permissions, contact a senior staff member or ping "
                f"<@{SENIOR_STAFF_ID}>."
            ),
            Separator(),
            # You're Ready
            TextDisplay(
                "**You\u2019re Ready**\n"
                "Once you've completed the steps above, you're all set to "
                "begin your duties as a member of the staff team."
            ),
            accent_color=0x000000,
        )

        self.add_item(container)


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

    def _build_staff_guide_view(self, member: discord.Member) -> StaffGuideLayout:
        """Build the staff guide as a Components V2 layout."""
        return StaffGuideLayout(member)

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
            view = self._build_staff_guide_view(member)
            await member.send(view=view)
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
            "SUCCESS": 0x00FF00,
            "FAILED": 0xFF0000,
            "SKIPPED": 0x07F9DD,
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

    async def _safe_respond(
        self,
        ctx: commands.Context,
        content: Optional[str] = None,
        *,
        embed: Optional[discord.Embed] = None,
        ephemeral: bool = False,
    ) -> None:
        """Respond without crashing on expired slash interactions.

        Hybrid commands invoked as slash commands may have an interaction that
        expires; fall back to a normal channel send if that happens.
        """
        interaction = getattr(ctx, "interaction", None)
        payload: dict = {}
        if content is not None:
            payload["content"] = content
        if embed is not None:
            payload["embed"] = embed

        if interaction is not None:
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        **payload, ephemeral=ephemeral
                    )
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

    async def cog_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        """Handle errors from staff guide commands with a clear message."""
        if isinstance(error, commands.CheckFailure):
            # The whole staffrules group is admin-only; tell non-admins
            # (including regular staff) instead of a generic error.
            if ctx.guild is None:
                message = "This command can only be used in a server."
            else:
                message = "This command is admin-only."
            await self._safe_respond(ctx, message, ephemeral=True)
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await self._safe_respond(
                ctx, "A required argument is missing.", ephemeral=True
            )
            return
        if isinstance(error, commands.BadArgument):
            await self._safe_respond(ctx, "Invalid argument provided.", ephemeral=True)
            return
        logger.error(f"Staff guide command error: {error}")
        await self._safe_respond(
            ctx, "An error occurred while processing your command.", ephemeral=True
        )

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
        description="Preview the staff guide in the current channel",
    )
    async def staffrules_preview(self, ctx: commands.Context) -> None:
        """Send the staff guide Components V2 layout in the current channel for preview."""
        if not isinstance(ctx.author, discord.Member):
            await ctx.send(
                embed=EmbedBuilder.error_embed(
                    "Error", "This command can only be used in a server."
                )
            )
            return
        view = self._build_staff_guide_view(ctx.author)
        await ctx.send(view=view)


async def setup(bot: commands.Bot) -> None:
    """Setup the StaffGuide cog."""
    await bot.add_cog(StaffGuide(bot))
