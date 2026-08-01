"""
Misc commands cog.
"""

import calendar
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

# better_profanity is optional. If it's not installed, provide a no-op fallback so the cog can still load.
try:
    from better_profanity import profanity
except Exception:

    class _DummyProfanity:
        @staticmethod
        def censor(text):
            try:
                # Keep behavior safe for non-str inputs
                return str(text)
            except Exception:
                return text

    profanity = _DummyProfanity()

from utils.codebuddy_database import DB_PATH
from utils.config import Config
from utils.language_resources import (
    LanguageResource,
    find_language_resource,
    get_supported_language_names,
    suggest_language_names,
)


class _EditSayModal(discord.ui.Modal, title="Edit Bot Message"):
    def __init__(self, *, target_message: discord.Message):
        super().__init__(timeout=300)
        self._target_message = target_message
        default_text = (target_message.content or "")[:2000]
        self.message_text = discord.ui.TextInput(
            label="Message",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=2000,
            default=default_text,
        )
        self.add_item(self.message_text)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        new_text = str(self.message_text.value).strip()
        if not new_text:
            await interaction.response.send_message(
                "❌ Message cannot be empty.",
                ephemeral=True,
            )
            return
        try:
            await self._target_message.edit(content=new_text)
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to edit that message.",
                ephemeral=True,
            )
            return
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Could not edit message: {e}",
                ephemeral=True,
            )
            return

        await interaction.response.send_message("✅ Message edited!", ephemeral=True)


class Misc(commands.Cog):
    """Miscellaneous commands."""

    def __init__(self, bot: commands.Bot, config: Config):
        self.bot = bot
        self.config = config

    def _resolve_resource_channel(
        self, guild: discord.Guild, channel_name: str, channel_id: Optional[int] = None
    ) -> Optional[discord.abc.GuildChannel]:
        """Resolve a configured channel by ID first, then by name."""
        if channel_id:
            channel = guild.get_channel(int(channel_id))
            if channel is not None:
                return channel

        normalized_name = channel_name.strip().lower()
        for channel in guild.channels:
            if channel.name.lower() == normalized_name:
                return channel
        return None

    def _format_channel_mentions(
        self, guild: Optional[discord.Guild], resource: LanguageResource
    ) -> str:
        """Format channel references for display, preferring clickable mentions."""
        if guild is None:
            if resource.related_channel_names:
                return "\n".join(
                    f"• `{name}`" for name in resource.related_channel_names
                )
            if resource.related_channel_ids:
                return "\n".join(
                    f"• `<{channel_id}>`" for channel_id in resource.related_channel_ids
                )
            return "• No configured Discord channels."

        resolved: list[str] = []
        resolved_mentions: set[str] = set()
        missing: list[str] = []

        for channel_id in resource.related_channel_ids:
            channel = guild.get_channel(int(channel_id))
            if channel is not None:
                mention = channel.mention
                if mention not in resolved_mentions:
                    resolved.append(f"• {mention}")
                    resolved_mentions.add(mention)
            else:
                missing.append(f"{channel_id}")

        for channel_name in resource.related_channel_names:
            channel = self._resolve_resource_channel(guild, channel_name)
            if channel is not None:
                mention = channel.mention
                if mention not in resolved_mentions:
                    resolved.append(f"• {mention}")
                    resolved_mentions.add(mention)
            else:
                missing.append(f"{channel_name}")

        if not resolved and not missing:
            return "• No configured Discord channels."

        lines = resolved[:]
        if missing:
            lines.extend(f"• {item}" for item in missing)
        return "\n".join(lines)

    @staticmethod
    def _format_link_block(links: tuple, empty_text: str) -> str:
        if not links:
            return empty_text
        return "\n".join(f"• [{link.label}]({link.url})" for link in links)

    def _build_resource_embed(
        self, guild: Optional[discord.Guild], resource: LanguageResource
    ) -> discord.Embed:
        embed = discord.Embed(
            title=f"{resource.display_name} Resources",
            description=resource.description,
            color=0x000000,
        )

        embed.add_field(
            name="Discord Channels",
            value=self._format_channel_mentions(guild, resource),
            inline=False,
        )
        embed.add_field(
            name="Official Documentation",
            value=f"[Open documentation]({resource.documentation_url})",
            inline=False,
        )
        embed.add_field(
            name="Our Website",
            value=f"[Open resource page]({resource.codeverse_hub_url})",
            inline=False,
        )

        beginner_links = self._format_link_block(
            resource.beginner_resources,
            "• No beginner resources configured yet.",
        )
        embed.add_field(
            name="Beginner / Recommended",
            value=beginner_links,
            inline=False,
        )

        if resource.extra_resources:
            embed.add_field(
                name="Extra Resources",
                value=self._format_link_block(resource.extra_resources, ""),
                inline=False,
            )

        embed.set_footer(text="Use ?resource <language> to look up another language")
        return embed

    async def _send_resource_response(
        self,
        ctx: commands.Context,
        embed: discord.Embed,
    ) -> None:
        if ctx.interaction:
            if not ctx.interaction.response.is_done():
                await ctx.interaction.response.send_message(embed=embed)
            else:
                await ctx.interaction.followup.send(embed=embed)
            return
        await ctx.reply(embed=embed, mention_author=False)

    async def _send_resource_usage(self, ctx: commands.Context) -> None:
        supported = get_supported_language_names()
        embed = discord.Embed(
            title="Usage: ?resource <language>",
            description=(
                "Provide a programming language to see related Discord channels, "
                "official documentation, the CodeVerse Hub Resources page, and curated beginner resources."
            ),
            color=0x000000,
        )

        if supported:
            embed.add_field(
                name="Supported Languages",
                value=", ".join(f"`{name}`" for name in supported),
                inline=False,
            )
        else:
            embed.add_field(
                name="Supported Languages",
                value="No language resources are configured yet.",
                inline=False,
            )

        await self._send_resource_response(ctx, embed)

    async def cog_load(self):
        # Track which messages were created via /say so only those are editable via /edit.
        try:
            async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS say_messages (
                        message_id INTEGER PRIMARY KEY,
                        guild_id INTEGER NOT NULL,
                        channel_id INTEGER NOT NULL,
                        author_id INTEGER NOT NULL,
                        created_at INTEGER NOT NULL
                    )
                    """
                )
                await db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_say_messages_guild ON say_messages (guild_id)"
                )
                await db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_say_messages_channel ON say_messages (channel_id)"
                )
                await db.commit()
        except Exception as e:
            print(f"[Misc] Error ensuring say_messages table: {e}")

    async def _is_say_message(
        self, guild_id: int, message_id: int
    ) -> Optional[tuple[int, int]]:
        """Return (guild_id, channel_id) if message is tracked as /say."""
        try:
            async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
                async with db.execute(
                    "SELECT guild_id, channel_id FROM say_messages WHERE message_id = ?",
                    (message_id,),
                ) as cursor:
                    row = await cursor.fetchone()
            if not row:
                return None
            if int(row[0]) != int(guild_id):
                return None
            return int(row[0]), int(row[1])
        except Exception:
            return None

    async def _record_say_message(
        self,
        guild_id: int,
        channel_id: int,
        message_id: int,
        author_id: int,
    ) -> None:
        try:
            async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO say_messages (message_id, guild_id, channel_id, author_id, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        int(message_id),
                        int(guild_id),
                        int(channel_id),
                        int(author_id),
                        int(datetime.now(timezone.utc).timestamp()),
                    ),
                )
                await db.commit()
        except Exception as e:
            print(f"[Misc] Error recording /say message: {e}")

    @commands.hybrid_command(
        name="join-vc", description="Join your voice channel for fun"
    )
    async def join_vc(self, ctx: commands.Context):
        """Join the invoker's voice channel (only if it is not empty)."""
        if ctx.guild is None:
            return await ctx.send("Server only command.")

        if not isinstance(ctx.author, discord.Member):
            return await ctx.send("Server member only.")

        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("Join a voice channel first.")

        channel = ctx.author.voice.channel
        non_bot_members = [m for m in channel.members if not m.bot]
        if len(non_bot_members) == 0:
            return await ctx.send("I will not join an empty voice channel.")

        vc = ctx.voice_client

        try:
            if isinstance(vc, discord.VoiceClient) and vc.is_connected():
                if vc.is_playing() or vc.is_paused():
                    return await ctx.send(
                        "I am currently playing audio in a voice channel."
                    )

                if vc.channel == channel:
                    return await ctx.send("I am already in your voice channel.")

                await vc.move_to(channel)
            else:
                await channel.connect()

        except discord.Forbidden:
            return await ctx.send(
                "I do not have permission to join that voice channel."
            )
        except discord.ClientException:
            return await ctx.send("I could not connect to that voice channel.")

        await ctx.send(f"Joined {channel.mention}.")

    @commands.hybrid_command(
        name="resource",
        description="Find learning resources for a programming language.",
    )
    @app_commands.describe(language="Programming language to look up")
    async def resource(self, ctx: commands.Context, *, language: str):
        """Show learning resources for a programming language."""
        if ctx.guild is None:
            await self._send_resource_response(
                ctx,
                discord.Embed(
                    title="Server Only",
                    description="This command is only available inside a server.",
                    color=0x000000,
                ),
            )
            return

        resource = find_language_resource(language)

        if resource is None:
            suggestions = suggest_language_names(language)
            supported = get_supported_language_names()
            embed = discord.Embed(
                title="Language Not Supported",
                description=f"`{language}` is not currently configured.",
                color=0x000000,
            )
            if suggestions:
                embed.add_field(
                    name="Closest Matches",
                    value=", ".join(f"`{name}`" for name in suggestions),
                    inline=False,
                )
            if supported:
                embed.add_field(
                    name="Available Languages",
                    value=", ".join(f"`{name}`" for name in supported),
                    inline=False,
                )
            await self._send_resource_response(ctx, embed)
            return

        embed = self._build_resource_embed(ctx.guild, resource)
        view = discord.ui.View(timeout=None)
        view.add_item(
            discord.ui.Button(
                label="Open in Our Website",
                url=resource.codeverse_hub_url,
                style=discord.ButtonStyle.link,
            )
        )

        if ctx.interaction:
            if not ctx.interaction.response.is_done():
                await ctx.interaction.response.send_message(embed=embed, view=view)
            else:
                await ctx.interaction.followup.send(embed=embed, view=view)
            return

        await ctx.reply(embed=embed, view=view, mention_author=False)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """Auto-leave when the last non-bot member leaves the bot's channel."""
        if member.bot:
            return

        vc = getattr(member.guild, "voice_client", None)
        if (
            not isinstance(vc, discord.VoiceClient)
            or not vc.is_connected()
            or not vc.channel
        ):
            return

        # Only react to events involving the channel we're currently in.
        if before.channel != vc.channel and after.channel != vc.channel:
            return

        # If nobody (except bots) is left in the channel, disconnect.
        remaining_humans = [m for m in vc.channel.members if not m.bot]
        if len(remaining_humans) != 0:
            return

        if vc.is_playing() or vc.is_paused():
            return

        try:
            await vc.disconnect()
        except Exception:
            return

    @commands.hybrid_command(name="about", description="Learn about Eigen Bot")
    async def about(self, ctx: commands.Context):
        """Show information about the bot."""
        embed = discord.Embed(
            title="Eigen Bot",
            description=(
                "Feature-rich Discord bot for community engagement, "
                "support tickets, and utilities. Built with discord.py."
            ),
            color=0x000000,
        )

        # Add bot stats
        total_guilds = len(self.bot.guilds)
        total_users = sum(
            guild.member_count for guild in self.bot.guilds if guild.member_count
        )
        total_commands = len(self.bot.tree.get_commands())

        embed.add_field(
            name="Statistics",
            value=(
                f"Servers: **{total_guilds}**\n"
                f"Users: **{total_users:,}**\n"
                f"Commands: **{total_commands}**"
            ),
            inline=True,
        )

        embed.add_field(
            name="Features",
            value=(
                "Support Tickets\n"
                "Starboard\n"
                "Custom Tags\n"
                "Elections\n"
                "Invite Tracker\n"
                "AFK System\n"
                "Fun Commands\n"
                "Utilities"
            ),
            inline=True,
        )

        embed.add_field(
            name="Links",
            value=(
                "[GitHub](https://github.com/TheCodeVerseHub/Eigen-Bot) · "
                "[Invite](https://discord.com/api/oauth2/authorize) · "
            ),
            inline=False,
        )

        embed.set_footer(text=f"discord.py {discord.__version__} · TheCodeVerseHub")

        # Set bot thumbnail
        if self.bot.user and self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)

        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="song",
        aliases=["sp", "spotify"],
        description="Show what you are currently listening to on Spotify",
    )
    async def song(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        """Display the current song/music that a user is listening to on Spotify or other music apps."""
        target_user = user or ctx.author

        # Ensure target_user is a Member (has activities attribute)
        if not isinstance(target_user, discord.Member):
            embed = discord.Embed(
                title="❌ Error",
                description="This command only works in servers, not in DMs.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        # Check all activities - be more comprehensive
        spotify_activity = None
        music_activity = None

        for activity in target_user.activities:
            # Check for Spotify specifically
            if isinstance(activity, discord.Spotify):
                spotify_activity = activity
                break
            # Check for any listening activity (including other music apps)
            elif activity.type == discord.ActivityType.listening:
                music_activity = activity

        if spotify_activity:
            # Create rich embed for Spotify
            embed = discord.Embed(
                title="Now Playing · Spotify",
                description=f"{target_user.display_name}",
                color=0x000000,
            )

            # Song details
            embed.add_field(
                name="Track",
                value=f"**[{profanity.censor(spotify_activity.title)}]({spotify_activity.track_url})**",
                inline=False,
            )

            embed.add_field(
                name="Artist",
                value=profanity.censor(", ".join(spotify_activity.artists)),
                inline=True,
            )

            embed.add_field(
                name="Album",
                value=profanity.censor(spotify_activity.album),
                inline=True,
            )

            # Duration
            duration = spotify_activity.duration
            current = (discord.utils.utcnow() - spotify_activity.start).total_seconds()

            duration_str = f"{int(duration.total_seconds() // 60)}:{int(duration.total_seconds() % 60):02d}"
            current_str = f"{int(current // 60)}:{int(current % 60):02d}"

            # Progress bar
            progress = min(current / duration.total_seconds(), 1.0)
            bar_length = 20
            filled = int(bar_length * progress)
            bar = "━" * filled + "○" + "─" * (bar_length - filled - 1)

            embed.add_field(
                name="Duration",
                value=f"`{current_str}` {bar} `{duration_str}`",
                inline=False,
            )

            # Add album art if available
            if spotify_activity.album_cover_url:
                embed.set_thumbnail(url=spotify_activity.album_cover_url)

            embed.set_footer(text=f"Requested by {ctx.author.display_name}")

        elif music_activity:
            # Found other music activity (not Spotify)
            # Generic music activity
            embed = discord.Embed(
                title="Now Listening",
                description=f"{target_user.display_name}",
                color=0x000000,
            )

            embed.add_field(
                name="Activity",
                value=f"**{profanity.censor(music_activity.name)}**",
                inline=False,
            )

            # Use getattr to safely access optional attributes
            details = getattr(music_activity, "details", None)
            if details:
                embed.add_field(
                    name="Details", value=profanity.censor(details), inline=False
                )

            state = getattr(music_activity, "state", None)
            if state:
                embed.add_field(
                    name="State", value=profanity.censor(state), inline=False
                )

            embed.set_footer(
                text=f"Requested by {ctx.author.display_name}",
                icon_url=ctx.author.display_avatar.url,
            )
        else:
            # No music activity found - show debug info
            if target_user == ctx.author:
                # Show what activities were detected
                activities_list = []
                for activity in target_user.activities:
                    activities_list.append(
                        f"• **{activity.name}** (Type: {activity.type.name})"
                    )

                if activities_list:
                    debug_info = "\n".join(activities_list)
                    message = (
                        "❌ **No music activity detected!**\n\n"
                        f"**Your current activities:**\n{debug_info}\n\n"
                        "**Possible solutions:**\n"
                        "• Make sure you're listening to music on Spotify, Apple Music, YouTube Music, etc.\n"
                        "• Enable 'Display current activity' in Discord Settings → Activity Privacy\n"
                        "• Restart your Discord client\n"
                        "• Make sure the music app is connected to Discord (check User Settings → Connections)"
                    )
                else:
                    message = (
                        "❌ **You are not currently listening to any music!**\n\n"
                        "**To use this command:**\n"
                        "• Be listening to Spotify or another music app\n"
                        "• Enable 'Display current activity' in Discord Settings → Activity Privacy\n"
                        "• Have your Discord client open and showing your activity\n"
                        "• Connect your music app in Discord Settings → Connections (for Spotify)"
                    )
            else:
                message = (
                    f"❌ **{target_user.display_name} is not currently listening to any music!**\n\n"
                    "They must be listening to Spotify or another music app with activity status enabled."
                )

            embed = discord.Embed(
                title="No Music Playing", description=message, color=0x000000
            )
            embed.set_footer(text="Activity Privacy must be enabled")

        await ctx.send(embed=embed)

    @commands.command(name="uptime", hidden=True)
    async def uptime(self, ctx: commands.Context):
        """Show the bot's uptime."""
        start_time = getattr(self.bot, "start_time", None)
        if not start_time:
            await ctx.send("Start time not tracked.")
            return

        now = discord.utils.utcnow()
        delta = now - start_time

        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"
        await ctx.send(f"⏱️ **Uptime:** {uptime_str}")

    @commands.command(name="diagnose", hidden=True)
    @commands.has_permissions(administrator=True)
    async def diagnose(self, ctx: commands.Context):
        """Show diagnostic information (Admin only)."""
        # Slash commands count
        slash_commands = len(self.bot.tree.get_commands())
        # Prefix commands count
        prefix_commands = len(self.bot.commands)
        # Guilds
        guilds = len(self.bot.guilds)
        # Users
        users = sum(g.member_count for g in self.bot.guilds if g.member_count)
        # Latency
        latency = round(self.bot.latency * 1000)

        embed = discord.Embed(title="Diagnostic Info", color=0x000000)
        embed.add_field(name="Slash Commands", value=str(slash_commands), inline=True)
        embed.add_field(name="Prefix Commands", value=str(prefix_commands), inline=True)
        embed.add_field(name="Guilds", value=str(guilds), inline=True)
        embed.add_field(name="Users", value=str(users), inline=True)
        embed.add_field(name="Latency", value=f"{latency}ms", inline=True)

        start_time = getattr(self.bot, "start_time", None)
        if start_time:
            embed.add_field(
                name="Start Time",
                value=discord.utils.format_dt(start_time, "R"),
                inline=True,
            )

        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="bug", description="Report a bug to the bot dev - Only for small bugs"
    )
    @app_commands.describe(bug="Describe the bug you encountered")
    async def bug_report(self, ctx: commands.Context, *, bug: str):
        """Report a bug to the support server."""
        # Support server channel ID
        SUPPORT_CHANNEL_ID = 1452739906525728828

        user = ctx.author
        guild = ctx.guild

        try:
            # Get the support channel
            support_channel = self.bot.get_channel(SUPPORT_CHANNEL_ID)

            if not support_channel or not isinstance(
                support_channel, discord.TextChannel
            ):
                response = "❌ Could not access the support channel."
                if ctx.interaction:
                    await ctx.interaction.response.send_message(
                        response, ephemeral=True
                    )
                else:
                    await ctx.send(response)
                return

            # Create bug report embed
            embed = discord.Embed(title="Bug Report", color=0x000000)

            # Add bug details
            embed.add_field(name="Details", value="*" + bug + "*", inline=False)

            # Add reporter and server info inline
            reporter_info = f"{user.mention} · `{user.id}`"
            location_info = (
                f"{guild.name} · `{guild.id}`" if guild else "Direct Message"
            )

            embed.add_field(name="Reported by", value=reporter_info, inline=True)
            embed.add_field(name="Server", value=location_info, inline=True)

            # Send to support channel
            await support_channel.send(embed=embed)

            # Confirm to user
            response = "✅ Your bug report has been submitted to our support team. Thank you for helping us improve!\n\n"
            if ctx.interaction:
                if not ctx.interaction.response.is_done():
                    await ctx.interaction.response.send_message(
                        response, ephemeral=True
                    )
                else:
                    await ctx.interaction.followup.send(response, ephemeral=True)
            else:
                await ctx.send(response)

        except Exception as e:
            response = (
                f"❌ An error occurred while submitting your bug report: {str(e)}\n\n"
            )
            if ctx.interaction:
                if not ctx.interaction.response.is_done():
                    await ctx.interaction.response.send_message(
                        response, ephemeral=True
                    )
                else:
                    await ctx.interaction.followup.send(response, ephemeral=True)
            else:
                await ctx.send(response)

    @commands.hybrid_command(
        name="support", description="Get the support server invite link"
    )
    async def support(self, ctx: commands.Context):
        """Send the support server invite link."""
        content = "Coming Soon!"

        if ctx.interaction:
            await ctx.interaction.response.send_message(content, ephemeral=True)
        else:
            try:
                await ctx.author.send(content)
                try:
                    await ctx.message.add_reaction("✅")
                except:
                    pass
            except:
                await ctx.send(content, delete_after=10)

    @app_commands.command(
        name="newfeature", description="Suggest a new feature for the bot"
    )
    @app_commands.describe(feature="Describe the feature you would like to see")
    async def new_feature(self, interaction: discord.Interaction, feature: str):
        """Submit a feature request to the support server."""
        # Feature requests channel ID
        FEATURE_CHANNEL_ID = 1452740031419777096

        try:
            # Get the feature requests channel
            feature_channel = self.bot.get_channel(FEATURE_CHANNEL_ID)

            if not feature_channel or not isinstance(
                feature_channel, discord.TextChannel
            ):
                await interaction.response.send_message(
                    "❌ Could not access the feature requests channel.",
                    ephemeral=True,
                )
                return

            # Create feature request embed
            embed = discord.Embed(title="Feature Request", color=0x000000)

            # Add feature details
            embed.add_field(name="Details", value="*" + feature + "*", inline=False)

            # Add requester and server info inline
            requester_info = f"{interaction.user.mention} · `{interaction.user.id}`"
            location_info = (
                f"{interaction.guild.name} · `{interaction.guild.id}`"
                if interaction.guild
                else "Direct Message"
            )

            embed.add_field(name="Requested By", value=requester_info, inline=True)
            embed.add_field(name="Location", value=location_info, inline=True)

            # Send to feature requests channel
            await feature_channel.send(embed=embed)

            # Confirm to user
            await interaction.response.send_message(
                "✅ Your feature request has been submitted! Our team will review it soon.\n\n",
                ephemeral=True,
            )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred while submitting your feature request: {str(e)}\n\n",
                ephemeral=True,
            )

    @app_commands.command(
        name="feedback", description="Share your feedback about the bot"
    )
    @app_commands.describe(
        rating="Rate your experience (1-5 stars)",
        feedback="Share your thoughts, suggestions, or testimonial",
    )
    @app_commands.choices(
        rating=[
            app_commands.Choice(name="⭐ 1 Star - Poor", value=1),
            app_commands.Choice(name="⭐⭐ 2 Stars - Fair", value=2),
            app_commands.Choice(name="⭐⭐⭐ 3 Stars - Good", value=3),
            app_commands.Choice(name="⭐⭐⭐⭐ 4 Stars - Very Good", value=4),
            app_commands.Choice(name="⭐⭐⭐⭐⭐ 5 Stars - Excellent", value=5),
        ]
    )
    async def feedback_command(
        self, interaction: discord.Interaction, rating: int, feedback: str
    ):
        """Submit feedback/testimonial to the support server."""
        # Feedback/testimonials channel ID
        FEEDBACK_CHANNEL_ID = 1453356371952275527

        try:
            # Get the feedback channel
            feedback_channel = self.bot.get_channel(FEEDBACK_CHANNEL_ID)

            if not feedback_channel or not isinstance(
                feedback_channel, discord.TextChannel
            ):
                await interaction.response.send_message(
                    "❌ Could not access the feedback channel.",
                    ephemeral=True,
                )
                return

            # Create star rating display
            stars = "⭐" * rating
            rating_text = ["Poor", "Fair", "Good", "Very Good", "Excellent"][rating - 1]

            # Create feedback embed with professional black design
            embed = discord.Embed(
                title=f"{stars} {rating}/5 · {rating_text}", color=0x000000
            )

            # Add feedback content
            embed.add_field(name="Feedback", value="*" + feedback + "*", inline=False)

            # Add reviewer and server info inline
            reviewer_info = f"{interaction.user.mention} · `{interaction.user.id}`"
            location_info = (
                f"{interaction.guild.name} · `{interaction.guild.id}`"
                if interaction.guild
                else "Direct Message"
            )

            embed.add_field(name="User", value=reviewer_info, inline=True)
            embed.add_field(name="Server", value=location_info, inline=True)

            # Send to feedback channel
            await feedback_channel.send(embed=embed)

            # Confirm to user with different messages based on rating
            if rating >= 4:
                message = "✅ Thank you for your positive feedback! We're thrilled you're enjoying the bot! 🎉\n\n"
            else:
                message = "✅ Thank you for your feedback! We appreciate your honesty and will work on improvements.\n\n"

            await interaction.response.send_message(message, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred while submitting your feedback: {str(e)}\n\n",
                ephemeral=True,
            )

    @app_commands.command(
        name="timestamp", description="Generate Discord timestamps for any date/time"
    )
    @app_commands.describe(
        year="Year (e.g., 2025)",
        month="Month (1-12)",
        day="Day of month (1-31)",
        hour="Hour in 24-hour format (0-23, optional)",
        minute="Minute (0-59, optional)",
        utc_offset="UTC offset in hours (e.g., -5 for EST, 5.5 for IST, optional)",
    )
    async def timestamp_command(
        self,
        interaction: discord.Interaction,
        year: int,
        month: app_commands.Range[int, 1, 12],
        day: app_commands.Range[int, 1, 31],
        hour: Optional[app_commands.Range[int, 0, 23]] = None,
        minute: Optional[app_commands.Range[int, 0, 59]] = None,
        utc_offset: float = 0.0,
    ):
        """Generate Discord timestamps with all available formats."""
        # Set defaults if None
        if hour is None:
            hour = 0
        if minute is None:
            minute = 0

        try:
            # Validate UTC offset range
            if utc_offset < -12 or utc_offset > 14:
                await interaction.response.send_message(
                    "❌ UTC offset must be between -12 and +14 hours!", ephemeral=True
                )
                return

            # Validate the date
            if day > calendar.monthrange(year, month)[1]:
                await interaction.response.send_message(
                    f"❌ Invalid date: {month}/{day}/{year} does not exist!",
                    ephemeral=True,
                )
                return

            # Create datetime object in UTC
            # User provides time in their timezone, convert to UTC
            offset_hours = int(utc_offset)
            offset_minutes = int((utc_offset - offset_hours) * 60)

            # Create the datetime in user's timezone
            user_dt = datetime(year, month, day, hour, minute)

            # Convert to UTC by subtracting the offset
            utc_dt = user_dt.replace(tzinfo=None)
            # Subtract offset to get UTC time
            utc_dt = utc_dt - timedelta(hours=offset_hours, minutes=offset_minutes)

            # Get Unix timestamp
            unix_timestamp = int(utc_dt.replace(tzinfo=timezone.utc).timestamp())

            # Create embed with all timestamp formats
            embed = discord.Embed(
                title="Discord Timestamps",
                description=f"{month}/{day}/{year} {hour:02d}:{minute:02d} (UTC{utc_offset:+.1f})",
                color=0x000000,
            )

            # Add all timestamp formats
            formats = [
                ("Short Time", "t", f"<t:{unix_timestamp}:t>"),
                ("Long Time", "T", f"<t:{unix_timestamp}:T>"),
                ("Short Date", "d", f"<t:{unix_timestamp}:d>"),
                ("Long Date", "D", f"<t:{unix_timestamp}:D>"),
                ("Short Date/Time", "f", f"<t:{unix_timestamp}:f>"),
                ("Long Date/Time", "F", f"<t:{unix_timestamp}:F>"),
                ("Relative Time", "R", f"<t:{unix_timestamp}:R>"),
            ]

            format_text = ""
            for name, code, timestamp_code in formats:
                # Show both the code and how it renders
                format_text += (
                    f"**{name}** (`{code}`)\n`{timestamp_code}` → {timestamp_code}\n\n"
                )

            embed.add_field(
                name="Available Formats", value=format_text.strip(), inline=False
            )

            # Add copy-paste section
            embed.add_field(
                name="Quick Copy",
                value=(
                    f"**Unix Timestamp:** `{unix_timestamp}`\n"
                    f"**Default:** `<t:{unix_timestamp}>`\n"
                    f"**Relative:** `<t:{unix_timestamp}:R>`"
                ),
                inline=False,
            )

            embed.set_footer(text="Click 'Copy' on any code block to use it")

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except ValueError as e:
            await interaction.response.send_message(
                f"❌ Invalid date/time: {str(e)}", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}", ephemeral=True
            )

    @app_commands.command(
        name="say", description="Make the bot say something (Admin only)"
    )
    @app_commands.describe(text="The text you want the bot to say")
    @app_commands.default_permissions(administrator=True)
    async def say(self, interaction: discord.Interaction, text: str):
        """Make the bot send a message (admin only to prevent abuse)."""
        # Double-check permissions (extra safety)
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server.", ephemeral=True
            )
            return

        if (
            not isinstance(interaction.user, discord.Member)
            or not interaction.user.guild_permissions.administrator
        ):
            await interaction.response.send_message(
                "❌ This command is restricted to administrators only.", ephemeral=True
            )
            return

        # Check if channel is messageable
        if not isinstance(interaction.channel, discord.abc.Messageable):
            await interaction.response.send_message(
                "❌ Cannot send messages in this channel type.", ephemeral=True
            )
            return

        # Send the text in the channel
        sent = await interaction.channel.send(text)

        # Track this message so it can be edited later via /edit.
        try:
            await self._record_say_message(
                interaction.guild.id,
                sent.channel.id,
                sent.id,
                interaction.user.id,
            )
        except Exception:
            pass

        # Confirm to admin (ephemeral so only they see it)
        await interaction.response.send_message("✅ Message sent!", ephemeral=True)

    @app_commands.command(
        name="edit",
        description="Edit a bot message sent via /say (Admin only).",
    )
    @app_commands.describe(message_id="Message ID of the /say message to edit")
    @app_commands.default_permissions(administrator=True)
    async def edit(self, interaction: discord.Interaction, message_id: str):
        """Open a modal to edit an existing /say message by ID."""
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server.",
                ephemeral=True,
            )
            return

        if (
            not isinstance(interaction.user, discord.Member)
            or not interaction.user.guild_permissions.administrator
        ):
            await interaction.response.send_message(
                "❌ This command is restricted to administrators only.",
                ephemeral=True,
            )
            return

        try:
            mid = int(str(message_id).strip())
        except Exception:
            await interaction.response.send_message(
                "❌ Invalid message ID.",
                ephemeral=True,
            )
            return

        say_row = await self._is_say_message(interaction.guild.id, mid)
        if not say_row:
            await interaction.response.send_message(
                "❌ Only messages sent using /say are editable with /edit.",
                ephemeral=True,
            )
            return

        _guild_id, channel_id = say_row
        channel = interaction.guild.get_channel(channel_id) or self.bot.get_channel(
            channel_id
        )
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message(
                "❌ Could not find the channel for that message.",
                ephemeral=True,
            )
            return

        try:
            target_message = await channel.fetch_message(mid)
        except discord.NotFound:
            await interaction.response.send_message(
                "❌ Message not found (it may have been deleted).",
                ephemeral=True,
            )
            return
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Could not fetch message: {e}",
                ephemeral=True,
            )
            return

        if self.bot.user is None or target_message.author.id != self.bot.user.id:
            await interaction.response.send_message(
                "❌ That message wasn't sent by me.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(
            _EditSayModal(target_message=target_message)
        )

    @app_commands.command(
        name="react",
        description="React to a message as the bot (Admin only).",
    )
    @app_commands.describe(
        emoji="Emoji to react with (unicode or custom emoji like <:name:id>)",
        message_link="Optional message link to react to; if omitted, reacts to the last message in this channel",
    )
    @app_commands.default_permissions(administrator=True)
    async def react(
        self,
        interaction: discord.Interaction,
        emoji: str,
        message_link: Optional[str] = None,
    ):
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server.",
                ephemeral=True,
            )
            return

        if (
            not isinstance(interaction.user, discord.Member)
            or not interaction.user.guild_permissions.administrator
        ):
            await interaction.response.send_message(
                "❌ This command is restricted to administrators only.",
                ephemeral=True,
            )
            return

        if not isinstance(interaction.channel, discord.abc.Messageable):
            await interaction.response.send_message(
                "❌ Cannot use this command in this channel type.",
                ephemeral=True,
            )
            return

        target_channel: Optional[discord.abc.Messageable] = interaction.channel
        target_message: Optional[discord.Message] = None

        if message_link:
            raw = message_link.strip().lstrip("<").rstrip(">")
            match = re.search(r"channels/(\d+)/(\d+)/(\d+)", raw)
            if match:
                guild_id = int(match.group(1))
                channel_id = int(match.group(2))
                message_id = int(match.group(3))
                if guild_id != interaction.guild.id:
                    await interaction.response.send_message(
                        "❌ That message link is from a different server.",
                        ephemeral=True,
                    )
                    return
                ch = interaction.guild.get_channel(channel_id) or self.bot.get_channel(
                    channel_id
                )
                if not isinstance(ch, (discord.TextChannel, discord.Thread)):
                    await interaction.response.send_message(
                        "❌ Could not access that channel.",
                        ephemeral=True,
                    )
                    return
                target_channel = ch
                try:
                    target_message = await ch.fetch_message(message_id)
                except Exception:
                    target_message = None
            else:
                # Allow providing just a message ID for the current channel.
                try:
                    message_id = int(raw)
                    if isinstance(
                        interaction.channel, (discord.TextChannel, discord.Thread)
                    ):
                        target_message = await interaction.channel.fetch_message(
                            message_id
                        )
                except Exception:
                    target_message = None

            if target_message is None:
                await interaction.response.send_message(
                    "❌ Could not find that message.",
                    ephemeral=True,
                )
                return
        else:
            # React to the last message in this channel.
            try:
                async for m in interaction.channel.history(limit=1):
                    target_message = m
                    break
            except Exception:
                target_message = None

            if target_message is None:
                await interaction.response.send_message(
                    "❌ No messages found in this channel.",
                    ephemeral=True,
                )
                return

        try:
            await target_message.add_reaction(emoji)
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to add reactions here.",
                ephemeral=True,
            )
            return
        except discord.HTTPException:
            await interaction.response.send_message(
                "❌ Failed to add that reaction (invalid emoji or missing access).",
                ephemeral=True,
            )
            return
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to react: {e}",
                ephemeral=True,
            )
            return

        await interaction.response.send_message("✅ Reaction added!", ephemeral=True)

    @commands.command(
        name="dm", description="Explains why you should not DM members for help"
    )
    async def dm_command(self, ctx: commands.Context):
        """Explains why questions should be asked in the server instead of DMs."""
        message = (
            "Please keep questions and answers within CVH. Do not DM them to other members. "
            "By sending your questions in the server, you maximize the number of people that see it, "
            "which can give you a higher quality response faster than if you were to DM an individual person. "
            "By DM-ing someone, you're also putting unfair pressure on that person to answer you, "
            "when they may not be in a position to do so at the moment."
        )
        await ctx.send(message)

    # ── Bot owner IDs authorised for ?todo ────────────────────────────────
    _TODO_OWNER_IDS = {955695820999639120, 1286998001902030908}
    _TODO_GUILD_ID = 1410939321812258928
    _TODO_CHANNEL_ID = 1491280085808840724

    @commands.command(name="todo", hidden=True)
    async def todo_command(self, ctx: commands.Context, *, task: str):
        """Add a todo task (bot owners only)."""
        # ── Permission check ──────────────────────────────────────────
        if ctx.author.id not in self._TODO_OWNER_IDS:
            embed = discord.Embed(
                title="Access Denied",
                description="Only bot owners can use this command.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        # ── Resolve target guild ──────────────────────────────────────
        target_guild = self.bot.get_guild(self._TODO_GUILD_ID)
        if target_guild is None:
            embed = discord.Embed(
                title="Error",
                description="The configured target guild could not be found. "
                "Make sure the bot is a member of that server.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        # ── Resolve target channel ────────────────────────────────────
        target_channel = target_guild.get_channel(self._TODO_CHANNEL_ID)
        if target_channel is None:
            embed = discord.Embed(
                title="Error",
                description="The configured todo channel could not be found.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        if not isinstance(target_channel, discord.TextChannel):
            embed = discord.Embed(
                title="Error",
                description="The target channel is not a text channel.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        # ── Build and send the todo embed ─────────────────────────────
        todo_embed = discord.Embed(
            title="New Todo Task",
            description=task,
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )
        todo_embed.set_author(
            name=ctx.author.display_name,
            icon_url=ctx.author.display_avatar.url,
        )
        todo_embed.set_footer(text=f"Added by {ctx.author}")

        await target_channel.send(embed=todo_embed)

        # ── Confirm to the caller ─────────────────────────────────────
        confirm_embed = discord.Embed(
            title="✅ Todo Task Added",
            description=f"Your task has been posted in {target_channel.mention}.",
            color=discord.Color.green(),
        )
        await ctx.send(embed=confirm_embed)


async def setup(bot):
    """Setup the misc cog."""
    config = bot.config
    await bot.add_cog(Misc(bot, config))
