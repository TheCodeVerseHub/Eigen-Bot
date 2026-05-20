import asyncio
import io
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.database import DATABASE_NAME
from utils.helpers import create_error_embed, create_info_embed, create_success_embed

logger = logging.getLogger("codeverse.tickets")


class TicketCategoryView(discord.ui.View):
    """View for selecting ticket category"""

    def __init__(self, cog):
        super().__init__(timeout=180)
        self.cog = cog

    @discord.ui.select(
        placeholder="Choose a category...",
        options=[
            discord.SelectOption(label="General Support", value="support"),
            discord.SelectOption(label="Bug Reports", value="bug_reports"),
            discord.SelectOption(label="Feature Requests", value="feature_request"),
            discord.SelectOption(label="Partnership", value="partnership"),
            discord.SelectOption(label="Reports", value="report"),
            discord.SelectOption(label="Other Issues", value="other"),
        ],
    )
    async def category_select(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        category = select.values[0]
        await self.cog.show_ticket_info(interaction, category)


class TicketConfirmationView(discord.ui.View):
    """View for confirming ticket creation after seeing info"""

    def __init__(self, cog, category):
        super().__init__(timeout=120)
        self.cog = cog
        self.category = category

    @discord.ui.button(label="Create This Ticket", style=discord.ButtonStyle.grey)
    async def create_ticket_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Create the actual ticket"""
        await self.cog.create_ticket(interaction, self.category)

    @discord.ui.button(label="Back to Categories", style=discord.ButtonStyle.grey)
    async def back_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Go back to category selection"""
        view = TicketCategoryView(self.cog)
        embed = discord.Embed(
            title="🎫 Create a Ticket",
            description="Select a category from the dropdown below:\n\n**Available Categories:**\n• General Support\n• Bug Reports\n• Feature Requests\n• Partnership\n• Reports\n• Other Issues",
            color=0x2B2D31,
        )
        embed.set_footer(text="Choose the category that best fits your needs")

        await interaction.response.edit_message(embed=embed, view=view)


class TicketControlView(discord.ui.View):
    """Persistent view with ticket control buttons"""

    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="🔒 Close Ticket",
        style=discord.ButtonStyle.red,
        custom_id="ticket_close_button",
    )
    async def close_ticket(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Close the ticket"""
        await self.cog.handle_close_ticket(interaction)

    @discord.ui.button(
        label="📌 Claim Ticket",
        style=discord.ButtonStyle.primary,
        custom_id="ticket_claim_button",
    )
    async def claim_ticket(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Claim the ticket"""
        await self.cog.handle_claim_ticket(interaction)


class TicketPanelView(discord.ui.View):
    """Persistent view for the ticket panel"""

    def __init__(self, cog):
        super().__init__(timeout=None)  # Persistent view
        self.cog = cog

    @discord.ui.button(
        label="Create Ticket",
        style=discord.ButtonStyle.grey,
        custom_id="persistent_ticket_create_button",  # Static custom_id
    )
    async def create_ticket_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Handle ticket creation button"""
        # Check if user already has an open ticket
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT ticket_thread_id FROM tickets WHERE user_id = ? AND status = "open"',
            (interaction.user.id,),
        )
        existing = cursor.fetchone()
        conn.close()

        if existing:
            await interaction.response.send_message(
                embed=create_error_embed(
                    "Ticket Already Open",
                    f"You already have an open ticket: <#{existing[0]}>",
                ),
                ephemeral=True,
            )
            return

        # Show ticket category selection
        view = TicketCategoryView(self.cog)
        embed = discord.Embed(
            title="🎫 Create a Ticket",
            description="Select a category from the dropdown below:\n\n**Available Categories:**\n• General Support\n• Bug Reports\n• Feature Requests\n• Partnership\n• Reports\n• Other Issues",
            color=0x2B2D31,
        )
        embed.set_footer(text="Choose the category that best fits your needs")

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class Tickets(commands.Cog):
    """Advanced ticket system using threads for support and moderation"""

    def __init__(self, bot):
        self.bot = bot
        self._init_database()

        # Configuration
        self.ticket_channel_id = (
            None  # Set this to the channel where tickets will be created as threads
        )
        # Note: Logs will be sent to #ticketlog channel in each server (optional)
        self.staff_role_id = 1417900662053671073  # Your staff role ID

        # Ticket naming
        self.ticket_counter = self._get_ticket_counter()

        # Register persistent views on bot startup
        self.bot.loop.create_task(self._restore_persistent_views())

    async def _restore_persistent_views(self):
        """Restore persistent views for all ticket panels on bot startup"""
        await self.bot.wait_until_ready()

        try:
            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()

            # Get all ticket panels from database
            cursor.execute("SELECT guild_id, channel_id, message_id FROM ticket_panels")
            panels = cursor.fetchall()
            conn.close()

            # Re-register the view for each panel
            for guild_id, channel_id, message_id in panels:
                try:
                    guild = self.bot.get_guild(guild_id)
                    if not guild:
                        continue

                    channel = guild.get_channel(channel_id)
                    if not channel or not isinstance(channel, discord.TextChannel):
                        continue

                    # Fetch the message to ensure it exists
                    try:
                        await channel.fetch_message(message_id)
                        # Create and attach the persistent view
                        view = TicketPanelView(self)
                        # The view is automatically registered due to persistent custom_id
                        self.bot.add_view(view, message_id=message_id)
                        logger.info(
                            f"Restored ticket panel view for message {message_id} in guild {guild_id}"
                        )
                    except discord.NotFound:
                        # Message was deleted, remove from database
                        conn = sqlite3.connect(DATABASE_NAME)
                        cursor = conn.cursor()
                        cursor.execute(
                            "DELETE FROM ticket_panels WHERE message_id = ?",
                            (message_id,),
                        )
                        conn.commit()
                        conn.close()
                        logger.warning(
                            f"Ticket panel message {message_id} not found, removed from database"
                        )
                    except Exception as e:
                        logger.error(
                            f"Error fetching ticket panel message {message_id}: {e}"
                        )

                except Exception as e:
                    logger.error(
                        f"Error restoring ticket panel for guild {guild_id}: {e}"
                    )

            logger.info(f"Restored {len(panels)} ticket panel views")

        except Exception as e:
            logger.error(f"Error restoring persistent ticket views: {e}")

    def _init_database(self):
        """Initialize tickets database table"""
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_thread_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                status TEXT DEFAULT 'open',
                claimed_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP,
                close_reason TEXT
            )
        """)

        # Table for storing persistent ticket panels
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ticket_panels (
                panel_id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER NOT NULL,
                UNIQUE(guild_id, channel_id, message_id)
            )
        """)

        # Table for storing custom ticket log channel settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ticket_log_channels (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL,
                set_by INTEGER NOT NULL,
                set_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Table for storing ticket support team role settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ticket_support_roles (
                guild_id INTEGER PRIMARY KEY,
                role_id INTEGER NOT NULL,
                set_by INTEGER NOT NULL,
                set_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Table for storing ticket report team role settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ticket_report_roles (
                guild_id INTEGER PRIMARY KEY,
                role_id INTEGER NOT NULL,
                set_by INTEGER NOT NULL,
                set_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Table for storing ticket partner team role settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ticket_partner_roles (
                guild_id INTEGER PRIMARY KEY,
                role_id INTEGER NOT NULL,
                set_by INTEGER NOT NULL,
                set_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    def _get_ticket_counter(self) -> int:
        """Get the next ticket number"""
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tickets")
        count = cursor.fetchone()[0]
        conn.close()
        return count + 1

    def _get_ticket_log_channel(
        self, guild: discord.Guild
    ) -> Optional[discord.TextChannel]:
        """Get the ticketlog channel for the guild if it exists"""
        # Check for hardcoded ticket log channel
        TICKET_LOGS_CHANNEL = 1438487366305190018
        channel = guild.get_channel(TICKET_LOGS_CHANNEL)
        if channel and isinstance(channel, discord.TextChannel):
            return channel

        # First check if a custom channel is set in database
        try:
            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT channel_id FROM ticket_log_channels WHERE guild_id = ?",
                (guild.id,),
            )
            result = cursor.fetchone()
            conn.close()

            if result:
                channel = guild.get_channel(result[0])
                if channel and isinstance(channel, discord.TextChannel):
                    return channel
                else:
                    # Clean up invalid channel reference
                    conn = sqlite3.connect(DATABASE_NAME)
                    cursor = conn.cursor()
                    cursor.execute(
                        "DELETE FROM ticket_log_channels WHERE guild_id = ?",
                        (guild.id,),
                    )
                    conn.commit()
                    conn.close()
        except Exception as e:
            print(f"[Tickets] Error checking custom log channel: {e}")

        # Fall back to checking channel names
        for channel in guild.text_channels:
            if channel.name.lower() in [
                "ticketlog",
                "ticket-log",
                "ticketlogs",
                "ticket-logs",
            ]:
                return channel
        return None

    def _get_support_team_role(self, guild: discord.Guild) -> Optional[discord.Role]:
        """Get the support team role for the guild if it exists"""
        try:
            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role_id FROM ticket_support_roles WHERE guild_id = ?",
                (guild.id,),
            )
            result = cursor.fetchone()
            conn.close()

            if result:
                role = guild.get_role(result[0])
                if role:
                    return role
                else:
                    # Clean up invalid role reference
                    conn = sqlite3.connect(DATABASE_NAME)
                    cursor = conn.cursor()
                    cursor.execute(
                        "DELETE FROM ticket_support_roles WHERE guild_id = ?",
                        (guild.id,),
                    )
                    conn.commit()
                    conn.close()
        except Exception as e:
            print(f"[Tickets] Error checking custom support role: {e}")

        # Fall back to checking for default staff role
        for role in guild.roles:
            if role.id == self.staff_role_id:
                return role
        return None

    def _get_report_team_role(self, guild: discord.Guild) -> Optional[discord.Role]:
        """Get the report team role for the guild if it exists"""
        try:
            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role_id FROM ticket_report_roles WHERE guild_id = ?",
                (guild.id,),
            )
            result = cursor.fetchone()
            conn.close()

            if result:
                role = guild.get_role(result[0])
                if role:
                    return role
                else:
                    # Clean up invalid role reference
                    conn = sqlite3.connect(DATABASE_NAME)
                    cursor = conn.cursor()
                    cursor.execute(
                        "DELETE FROM ticket_report_roles WHERE guild_id = ?",
                        (guild.id,),
                    )
                    conn.commit()
                    conn.close()
        except Exception as e:
            print(f"[Tickets] Error checking report team role: {e}")

        # Fall back to support team role if no report role set
        return self._get_support_team_role(guild)

    def _get_partner_team_role(self, guild: discord.Guild) -> Optional[discord.Role]:
        """Get the partner team role for the guild if it exists"""
        try:
            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role_id FROM ticket_partner_roles WHERE guild_id = ?",
                (guild.id,),
            )
            result = cursor.fetchone()
            conn.close()

            if result:
                role = guild.get_role(result[0])
                if role:
                    return role
                else:
                    # Clean up invalid role reference
                    conn = sqlite3.connect(DATABASE_NAME)
                    cursor = conn.cursor()
                    cursor.execute(
                        "DELETE FROM ticket_partner_roles WHERE guild_id = ?",
                        (guild.id,),
                    )
                    conn.commit()
                    conn.close()
        except Exception as e:
            print(f"[Tickets] Error checking partner team role: {e}")

        # Fall back to support team role if no partner role set
        return self._get_support_team_role(guild)

    async def show_ticket_info(self, interaction: discord.Interaction, category: str):
        """Show information about the selected ticket type"""
        # Category information with detailed descriptions
        category_info = {
            "partnership": {
                "name": "Partnership",
                "description": "We value building a strong, engaging community and have established clear criteria for our partnership program",
                "guidelines": (
                    # "**Server Requirements:**\n"
                    # "100+ active members with 1/9 online during peak hours\n"
                    # "350+ daily messages in active channels\n"
                    # "SFW content and family-friendly environment\n"
                    # "Tech/IT focus but different from CodeVerse specialization\n"
                    # "Active, reliable moderation team\n\n"
                    # "**Partnership Benefits:**\n"
                    # "Custom advertisement channels\n"
                    # "Cross-community engagement opportunities\n"
                    # "Collaborative events and knowledge sharing\n\n"
                    "**Partnership Terms:**\n"
                    "Partnership may be removed if requirements are no longer met, channels are deleted, or community guidelines are violated.\n\n"
                    "**Ready to apply?** Click 'Create This Ticket' to begin the partnership application process."
                ),
                "examples": "Discord server partnerships, tech community collaborations, educational alliances",
                "color": 0x2B2D31,
            },
            "support": {
                "name": "General Support",
                "description": "Get help with using our services, platforms, or community features",
                "guidelines": (
                    "**Be specific about your question** - What do you need help with?\n"
                    "**Mention what you've tried** - What steps have you already taken?\n"
                    "**Provide context** - What are you trying to accomplish?\n"
                    "**Include relevant details** - Account info, error messages, etc.\n"
                    "**Be patient** - Our team will help you as soon as possible"
                ),
                "examples": "How to use features, account questions, general guidance",
                "color": 0x2B2D31,
            },
            "bug_reports": {
                "name": "Bug Reports",
                "description": "Report bugs, glitches, or technical issues with the bot or server features",
                "guidelines": (
                    "**What happened?** - Describe the bug clearly\n"
                    "**Expected behavior** - What should have happened instead?\n"
                    "**Steps to reproduce** - How can we recreate this issue?\n"
                    "**Error messages** - Include any error messages you saw\n"
                    "**When it happened** - Date and time (approximate)"
                ),
                "examples": "Bot commands not working, features broken, error messages, unexpected behavior",
                "color": 0x2B2D31,
            },
            "report": {
                "name": "Reports",
                "description": "Report inappropriate behavior, rule violations, or misconduct",
                "guidelines": (
                    "**User information** - Who are you reporting? (ID, username)\n"
                    "**Detailed description** - What did they do wrong?\n"
                    "**Evidence** - Screenshots, message links, timestamps\n"
                    "**Rule violations** - Which rules were broken? (optional)\n"
                    "**Your involvement** - Were you directly affected?"
                ),
                "examples": "Harassment, spam, rule breaking, inappropriate content",
                "color": 0x2B2D31,
            },
            "feature_requests": {
                "name": "Feature Requests",
                "description": "Suggest new features, improvements, or changes to existing functionality",
                "guidelines": (
                    "**Feature description** - What feature would you like to see?\n"
                    "**Why it's useful** - How would this benefit the community?\n"
                    "**How it should work** - Explain your vision for implementation\n"
                    "**Similar examples** - Any inspiration from other bots/servers?\n"
                    "**Priority** - How important is this to you? (low/medium/high)"
                ),
                "examples": "New bot commands, server improvements, quality of life changes, feature enhancements",
                "color": 0x2B2D31,
            },
            "other": {
                "name": "Other Issues",
                "description": "Anything else that doesn't fit the above categories",
                "guidelines": (
                    "**Clear subject line** - Summarize your issue in one sentence\n"
                    "**Detailed explanation** - Provide all relevant information\n"
                    "**Urgency level** - Is this time-sensitive?\n"
                    "**Preferred contact method** - How should we follow up?\n"
                    "**Additional context** - Any other details that might help"
                ),
                "examples": "Feedback, suggestions, questions not covered by other categories",
                "color": 0x2B2D31,
            },
        }

        info = category_info.get(category, category_info["other"])

        embed = discord.Embed(
            title=info["name"], description=info["description"], color=info["color"]
        )

        embed.add_field(
            name="Guidelines for this ticket type:",
            value=info["guidelines"],
            inline=False,
        )

        embed.add_field(name="Examples:", value=info["examples"], inline=False)

        embed.add_field(
            name="What happens next?",
            value=(
                "Your ticket will be created as a private thread\n"
                "Our support team will be notified automatically\n"
                "You'll receive help from qualified staff members\n"
                "The ticket will remain open until your issue is resolved"
            ),
            inline=False,
        )

        embed.set_footer(
            text="Click 'Create This Ticket' if you're ready to proceed, or go back to choose a different category."
        )

        view = TicketConfirmationView(self, category)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def create_ticket(self, interaction: discord.Interaction, category: str):
        """Create a new ticket thread"""
        # Defer the response to avoid timeout
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild:
            return

        guild = interaction.guild
        user = interaction.user

        # Category emojis and names
        category_info = {
            "support": ("❓", "General Support"),
            "bug_reports": ("🎭", "Bug Reports"),
            "feature_requests": ("⚖️", "Feature Requests"),
            "partnership": ("🤝", "Partnership"),
            "report": ("🚨", "Reports"),
            "other": ("📝", "Other Issues"),
        }

        emoji, category_name = category_info.get(category, ("", "Ticket"))

        # Get ticket channel
        ticket_channel_id = self.ticket_channel_id or interaction.channel_id
        if ticket_channel_id is None:
            await interaction.followup.send(
                embed=create_error_embed(
                    "Configuration Error", "No ticket channel configured."
                ),
                ephemeral=True,
            )
            return

        ticket_channel = guild.get_channel(ticket_channel_id)

        if not ticket_channel or not isinstance(ticket_channel, discord.TextChannel):
            await interaction.followup.send(
                embed=create_error_embed(
                    "Configuration Error", "Ticket channel not properly configured."
                ),
                ephemeral=True,
            )
            return

        # Create ticket thread
        ticket_number = self.ticket_counter
        self.ticket_counter += 1

        thread_name = f"{emoji} Ticket-{ticket_number:04d} | {category_name}"

        try:
            # Create the thread
            thread = await ticket_channel.create_thread(
                name=thread_name,
                auto_archive_duration=4320,  # 3 days
            )

            # Add user to thread
            await thread.add_user(user)

            # Add staff role members based on ticket category
            staff_role = None
            if category == "report":
                staff_role = self._get_report_team_role(guild)
            elif category == "partnership":
                staff_role = self._get_partner_team_role(guild)
            else:
                staff_role = self._get_support_team_role(guild)

        except Exception as e:
            await interaction.followup.send(
                embed=create_error_embed("Failed to Create Ticket", f"Error: {str(e)}"),
                ephemeral=True,
            )
            return

        # Save to database
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tickets (ticket_thread_id, user_id, category) VALUES (?, ?, ?)",
            (thread.id, user.id, category),
        )
        ticket_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Send welcome message in thread
        embed = discord.Embed(
            title=f"{emoji} Ticket #{ticket_number} - {category_name}",
            description=f"Welcome {user.mention}! Thank you for creating a ticket.\n\nPlease describe your issue in detail, and our staff team will assist you shortly.",
            color=0x2ECC71,
        )
        embed.add_field(
            name="📋 Ticket Information",
            value=(
                f"**Category:** {category_name}\n"
                f"**Created:** <t:{int(datetime.now(timezone.utc).timestamp())}:R>\n"
                f"**Status:** 🟢 Open"
            ),
            inline=False,
        )
        embed.add_field(
            name="🎛️ Ticket Controls",
            value=(
                "• **🔒 Close** - Close this ticket\n"
                "• **📌 Claim** - Claim this ticket (Staff)"
            ),
            inline=False,
        )
        embed.set_footer(text=f"Ticket ID: {ticket_id} | CodeVerse Support")

        view = TicketControlView(self)
        staff_mention = staff_role.mention if staff_role else "@Staff"
        await thread.send(
            content=f"{user.mention} | Staff: {staff_mention}", embed=embed, view=view
        )

        # Confirm to user
        await interaction.followup.send(
            embed=create_success_embed(
                "Ticket Created", f"Your ticket has been created: {thread.mention}"
            ),
            ephemeral=True,
        )

        # Log to staff channel
        if ticket_id is not None:
            await self._log_ticket_action(
                "CREATED", ticket_id, thread, user, category_name
            )

        print(
            f"[Tickets] Ticket #{ticket_number} created by {user} ({user.id}) - Category: {category_name}"
        )

    async def handle_close_ticket(self, interaction: discord.Interaction):
        """Handle ticket closure"""
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                embed=create_error_embed(
                    "Not a Ticket", "This command can only be used in ticket threads."
                ),
                ephemeral=True,
            )
            return

        thread = interaction.channel

        # Get ticket info from database
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT ticket_id, user_id, category FROM tickets WHERE ticket_thread_id = ? AND status = "open"',
            (thread.id,),
        )
        result = cursor.fetchone()

        if not result:
            await interaction.response.send_message(
                embed=create_error_embed(
                    "Not a Ticket", "This is not an open ticket thread."
                ),
                ephemeral=True,
            )
            conn.close()
            return

        ticket_id, user_id, category = result

        # Check permissions (ticket owner or staff)
        has_permission = False
        if isinstance(interaction.user, discord.Member):
            has_permission = (
                interaction.user.id == user_id
                or any(role.id == self.staff_role_id for role in interaction.user.roles)
                or interaction.user.guild_permissions.administrator
            )
        elif interaction.user.id == user_id:
            has_permission = True

        if not has_permission:
            await interaction.response.send_message(
                embed=create_error_embed(
                    "No Permission",
                    "Only the ticket owner or staff can close this ticket.",
                ),
                ephemeral=True,
            )
            conn.close()
            return

        # Update database
        cursor.execute(
            'UPDATE tickets SET status = "closed", closed_at = CURRENT_TIMESTAMP, close_reason = ? WHERE ticket_id = ?',
            (f"Closed by {interaction.user}", ticket_id),
        )
        conn.commit()
        conn.close()

        # Send closure message
        embed = discord.Embed(
            title="🔒 Ticket Closed",
            description=f"This ticket has been closed by {interaction.user.mention}",
            color=0xE74C3C,
        )
        embed.add_field(
            name="📋 Next Steps",
            value="This thread will be archived and locked in 10 seconds.\nA transcript has been saved.",
            inline=False,
        )
        embed.timestamp = datetime.now(timezone.utc)

        await interaction.response.send_message(embed=embed)

        # Log closure
        await self._log_ticket_action(
            "CLOSED",
            ticket_id,
            thread,
            interaction.user,
            category,
            f"Closed by {interaction.user.name}",
        )

        # Generate transcript before archiving
        await self._generate_transcript(thread, ticket_id, save_to_log=True)

        # Archive and lock thread after delay
        await asyncio.sleep(10)
        try:
            if isinstance(thread, discord.Thread):
                await thread.edit(archived=True, locked=True)
        except Exception as e:
            print(f"[Tickets] Failed to archive ticket thread: {e}")

        print(f"[Tickets] Ticket #{ticket_id} closed by {interaction.user}")

    async def handle_claim_ticket(self, interaction: discord.Interaction):
        """Handle ticket claiming by staff"""
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                embed=create_error_embed(
                    "Not a Ticket", "This command can only be used in ticket threads."
                ),
                ephemeral=True,
            )
            return

        thread = interaction.channel

        # Check if user is staff
        is_staff = False
        if isinstance(interaction.user, discord.Member):
            is_staff = (
                any(role.id == self.staff_role_id for role in interaction.user.roles)
                or interaction.user.guild_permissions.administrator
            )

        if not is_staff:
            await interaction.response.send_message(
                embed=create_error_embed(
                    "No Permission", "Only staff members can claim tickets."
                ),
                ephemeral=True,
            )
            return

        # Get ticket info
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT ticket_id, user_id, claimed_by FROM tickets WHERE ticket_thread_id = ? AND status = "open"',
            (thread.id,),
        )
        result = cursor.fetchone()

        if not result:
            await interaction.response.send_message(
                embed=create_error_embed(
                    "Not a Ticket", "This is not an open ticket thread."
                ),
                ephemeral=True,
            )
            conn.close()
            return

        ticket_id, user_id, claimed_by = result

        if claimed_by:
            try:
                claimer = await self.bot.fetch_user(claimed_by)
                await interaction.response.send_message(
                    embed=create_info_embed(
                        "Already Claimed",
                        f"This ticket is already claimed by {claimer.mention}",
                    ),
                    ephemeral=True,
                )
            except:
                await interaction.response.send_message(
                    embed=create_info_embed(
                        "Already Claimed", "This ticket is already claimed by someone."
                    ),
                    ephemeral=True,
                )
            conn.close()
            return

        # Claim ticket
        cursor.execute(
            "UPDATE tickets SET claimed_by = ? WHERE ticket_id = ?",
            (interaction.user.id, ticket_id),
        )
        conn.commit()
        conn.close()

        # Send claim message
        embed = discord.Embed(
            title="📌 Ticket Claimed",
            description=f"{interaction.user.mention} is now handling this ticket.",
            color=0x3498DB,
        )
        embed.timestamp = datetime.now(timezone.utc)

        await interaction.response.send_message(embed=embed)

        print(f"[Tickets] Ticket #{ticket_id} claimed by {interaction.user}")

    async def _generate_transcript(
        self, thread: discord.Thread, ticket_id: int, save_to_log: bool = False
    ) -> Optional[str]:
        """Generate a text transcript of the ticket"""
        try:
            messages = []
            async for message in thread.history(limit=500, oldest_first=True):
                timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
                author = f"{message.author.display_name}"
                content = message.content or "[No text content]"

                # Include attachments
                if message.attachments:
                    for attachment in message.attachments:
                        content += f"\n[Attachment: {attachment.url}]"

                messages.append(f"[{timestamp}] {author}: {content}")

            transcript = f"Ticket #{ticket_id} Transcript\n"
            transcript += f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            transcript += "=" * 80 + "\n\n"
            transcript += "\n".join(messages)

            # Save to log channel if requested
            if save_to_log and thread.guild:
                log_channel = self._get_ticket_log_channel(thread.guild)
                if log_channel:
                    file = discord.File(
                        io.BytesIO(transcript.encode("utf-8")),
                        filename=f"ticket-{ticket_id}-transcript.txt",
                    )

                    embed = discord.Embed(
                        title=f"📄 Ticket #{ticket_id} Transcript",
                        description="Transcript saved for closed ticket.",
                        color=0x95A5A6,
                    )
                    embed.timestamp = datetime.now(timezone.utc)

                    await log_channel.send(embed=embed, file=file)

            return transcript
        except Exception as e:
            print(f"[Tickets] Failed to generate transcript: {e}")
            return None

    async def _log_ticket_action(
        self,
        action: str,
        ticket_id: int,
        thread: discord.Thread,
        user: discord.User | discord.Member,
        category: Optional[str] = None,
        reason: Optional[str] = None,
    ):
        """Log ticket actions to the ticket log channel in the server (if it exists)"""
        if not thread.guild:
            return

        log_channel = self._get_ticket_log_channel(thread.guild)
        if not log_channel:
            print(
                f"[Tickets] No #ticketlog channel found in {thread.guild.name} - skipping log"
            )
            return

        colors = {"CREATED": 0x2ECC71, "CLOSED": 0xE74C3C, "CLAIMED": 0x3498DB}

        titles = {
            "CREATED": "✨ Ticket Created",
            "CLOSED": "🔒 Ticket Closed",
            "CLAIMED": "📌 Ticket Claimed",
        }

        embed = discord.Embed(
            title=titles.get(action, f"🎫 Ticket {action}"),
            color=colors.get(action, 0x95A5A6),
        )

        embed.add_field(name="Ticket ID", value=f"#{ticket_id}", inline=True)
        embed.add_field(name="User", value=f"{user.mention} ({user.id})", inline=True)
        embed.add_field(name="Thread", value=thread.mention, inline=True)

        if category:
            embed.add_field(name="Category", value=category, inline=True)

        if reason:
            embed.add_field(name="📝 Reason", value=reason, inline=False)

        embed.timestamp = datetime.now(timezone.utc)
        embed.set_footer(text="Ticket System")

        try:
            await log_channel.send(embed=embed)
        except Exception as e:
            print(f"[Tickets] Failed to send log: {e}")

    @commands.hybrid_command(name="ticketpanel")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(
        channel="Channel to send the ticket panel to",
        support_role="Role to ping when new tickets are created (optional)",
        report_role="Role to ping for report tickets (optional)",
        partner_role="Role to ping for partnership tickets (optional)",
    )
    async def ticket_panel(
        self,
        ctx,
        channel: Optional[discord.TextChannel] = None,
        support_role: Optional[discord.Role] = None,
        report_role: Optional[discord.Role] = None,
        partner_role: Optional[discord.Role] = None,
    ):
        """Create a ticket panel with a button to open tickets"""
        target_channel = channel or ctx.channel

        if not isinstance(target_channel, discord.TextChannel):
            await ctx.send(
                embed=create_error_embed(
                    "Invalid Channel", "Please provide a valid text channel."
                ),
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="🎫 Support Tickets",
            description="Need help? Click **Create Ticket** below to get started!\n\n**Available Categories:**\n• General Support\n• Bug Reports\n• Feature Requests\n• Partnership\n• Reports\n• Other Issues",
            color=0x2B2D31,
        )

        embed.set_footer(text="Private • Fast • Organized")
        if ctx.guild and ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)

        view = TicketPanelView(self)
        panel_message = await target_channel.send(embed=embed, view=view)

        # Save panel to database for persistence
        if ctx.guild:
            try:
                conn = sqlite3.connect(DATABASE_NAME)
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT OR IGNORE INTO ticket_panels (guild_id, channel_id, message_id, created_by)
                    VALUES (?, ?, ?, ?)
                """,
                    (ctx.guild.id, target_channel.id, panel_message.id, ctx.author.id),
                )

                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"Error saving ticket panel to database: {e}")

        # Set ticket channel to this channel
        self.ticket_channel_id = target_channel.id

        # Save roles if provided
        roles_saved = []
        if ctx.guild:
            try:
                conn = sqlite3.connect(DATABASE_NAME)
                cursor = conn.cursor()

                # Save support role
                if support_role:
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO ticket_support_roles (guild_id, role_id, set_by, set_at)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                        (ctx.guild.id, support_role.id, ctx.author.id),
                    )
                    roles_saved.append(f"**Support:** {support_role.mention}")

                # Save report role
                if report_role:
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO ticket_report_roles (guild_id, role_id, set_by, set_at)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                        (ctx.guild.id, report_role.id, ctx.author.id),
                    )
                    roles_saved.append(f"**Report:** {report_role.mention}")

                # Save partner role
                if partner_role:
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO ticket_partner_roles (guild_id, role_id, set_by, set_at)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                        (ctx.guild.id, partner_role.id, ctx.author.id),
                    )
                    roles_saved.append(f"**Partner:** {partner_role.mention}")

                conn.commit()
                conn.close()

                if roles_saved:
                    role_info = "\n".join(roles_saved)
                    success_message = f"Ticket panel created in {target_channel.mention}\nTickets will be created as threads in that channel.\n\n{role_info}"
                else:
                    # Show current role settings
                    current_support = self._get_support_team_role(ctx.guild)
                    current_report = self._get_report_team_role(ctx.guild)
                    current_partner = self._get_partner_team_role(ctx.guild)

                    current_roles = []
                    if current_support:
                        current_roles.append(f"**Support:** {current_support.mention}")
                    if current_report and current_report != current_support:
                        current_roles.append(f"**Report:** {current_report.mention}")
                    if current_partner and current_partner != current_support:
                        current_roles.append(f"**Partner:** {current_partner.mention}")

                    if current_roles:
                        role_info = "\n".join(current_roles)
                        success_message = f"Ticket panel created in {target_channel.mention}\nTickets will be created as threads in that channel.\n\n**Current Role Settings:**\n{role_info}"
                    else:
                        success_message = f"Ticket panel created in {target_channel.mention}\nTickets will be created as threads in that channel.\n\n💡 Use `/ticketpanel #channel @support @report @partner` to set specialized roles."

            except Exception as e:
                print(f"[Tickets] Failed to save roles: {e}")
                success_message = f"Ticket panel created in {target_channel.mention}\nTickets will be created as threads in that channel.\n\n⚠️ Failed to save role settings."
        else:
            success_message = f"Ticket panel created in {target_channel.mention}\nTickets will be created as threads in that channel."

        await ctx.send(
            embed=create_success_embed("Panel Created", success_message), ephemeral=True
        )

    @commands.hybrid_command(name="ticketlog")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(
        channel="The channel to use for ticket logs (leave empty to view current setting)"
    )
    async def ticket_log_setup(
        self, ctx, channel: Optional[discord.TextChannel] = None
    ):
        """Set up, view, or disable the ticket log channel for this server"""
        if not ctx.guild:
            await ctx.send(
                embed=create_error_embed(
                    "Error", "This command can only be used in servers."
                ),
                ephemeral=True,
            )
            return

        if channel is None:
            # View current setting
            current_log_channel = self._get_ticket_log_channel(ctx.guild)
            if current_log_channel:
                embed = discord.Embed(
                    title="📋 Ticket Log Channel",
                    description=f"Current ticket log channel: {current_log_channel.mention}",
                    color=0x5865F2,
                )
                embed.add_field(
                    name="ℹ️ Information",
                    value="Ticket actions (create, close, claim) will be logged to this channel.\n\n"
                    "• **Change it:** `/ticketlog #new-channel`\n"
                    "• **Disable custom:** `/ticketlog-disable`\n"
                    "• **Quick disable:** Rename this channel",
                    inline=False,
                )
            else:
                embed = discord.Embed(
                    title="📋 Ticket Log Channel",
                    description="❌ No ticket log channel is currently set up.",
                    color=0xE74C3C,
                )
                embed.add_field(
                    name="🔧 Setup Instructions",
                    value="To enable ticket logging:\n"
                    "1. Create a channel named `ticketlog`\n"
                    "2. Or use `/ticketlog #channel` to set a specific channel\n"
                    "3. Make sure the bot has permission to send messages there",
                    inline=False,
                )

            await ctx.send(embed=embed, ephemeral=True)
            return

        # Set new log channel
        try:
            # Test if bot can send messages to the channel
            test_embed = discord.Embed(
                title="🧪 Test Message",
                description="Testing ticket log setup...",
                color=0x95A5A6,
            )
            test_message = await channel.send(embed=test_embed)

            # Delete test message
            await test_message.delete()

            # Save the channel to database
            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO ticket_log_channels (guild_id, channel_id, set_by, set_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (ctx.guild.id, channel.id, ctx.author.id),
            )
            conn.commit()
            conn.close()

            # Update the helper function to recognize this specific channel
            # We'll store it in a simple way by checking if it's the designated channel
            success_embed = discord.Embed(
                title="✅ Ticket Log Channel Set",
                description=f"Ticket logs will now be sent to {channel.mention}",
                color=0x2ECC71,
            )
            success_embed.add_field(
                name="📝 What gets logged?",
                value="• New ticket creation\n• Ticket closing\n• Ticket claiming\n• Ticket transcripts",
                inline=False,
            )
            success_embed.add_field(
                name="💡 Note",
                value="The bot automatically detects channels named `ticketlog`, `ticket-log`, etc.\n"
                f"You can also rename {channel.mention} to any of these names.",
                inline=False,
            )

            await ctx.send(embed=success_embed, ephemeral=True)

            # Send a confirmation to the log channel
            log_embed = discord.Embed(
                title="🎫 Ticket Logging Enabled",
                description=f"This channel has been set up for ticket logging by {ctx.author.mention}",
                color=0x5865F2,
            )
            log_embed.add_field(
                name="📊 What you'll see here:",
                value="• Ticket creation notifications\n• Ticket closure logs\n• Staff claim notifications\n• Ticket transcripts",
                inline=False,
            )
            log_embed.timestamp = datetime.now(timezone.utc)
            log_embed.set_footer(text="CodeVerse Ticket System")

            await channel.send(embed=log_embed)

        except discord.Forbidden:
            await ctx.send(
                embed=create_error_embed(
                    "Permission Error",
                    f"I don't have permission to send messages in {channel.mention}.\n"
                    "Please make sure I have `Send Messages` permission in that channel.",
                ),
                ephemeral=True,
            )
        except Exception as e:
            await ctx.send(
                embed=create_error_embed(
                    "Setup Error", f"Failed to set up ticket logging: {str(e)}"
                ),
                ephemeral=True,
            )

    @commands.hybrid_command(name="ticketlog-disable")
    @commands.has_permissions(administrator=True)
    async def ticket_log_disable(self, ctx):
        """Disable ticket logging for this server"""
        if not ctx.guild:
            await ctx.send(
                embed=create_error_embed(
                    "Error", "This command can only be used in servers."
                ),
                ephemeral=True,
            )
            return

        try:
            # Remove custom log channel setting from database
            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM ticket_log_channels WHERE guild_id = ?", (ctx.guild.id,)
            )
            deleted = cursor.rowcount > 0
            conn.commit()
            conn.close()

            if deleted:
                embed = discord.Embed(
                    title="🚫 Ticket Logging Disabled",
                    description="Custom ticket log channel has been removed.",
                    color=0xE74C3C,
                )
                embed.add_field(
                    name="ℹ️ Note",
                    value="The bot will still log to channels named `ticketlog`, `ticket-log`, etc. if they exist.\n"
                    "To completely disable logging, rename or delete those channels.",
                    inline=False,
                )
            else:
                embed = discord.Embed(
                    title="ℹ️ No Custom Channel Set",
                    description="There was no custom ticket log channel to disable.",
                    color=0x95A5A6,
                )
                embed.add_field(
                    name="Current Status",
                    value="The bot is using automatic detection for channels named `ticketlog`, `ticket-log`, etc.",
                    inline=False,
                )

            await ctx.send(embed=embed, ephemeral=True)

        except Exception as e:
            await ctx.send(
                embed=create_error_embed(
                    "Error", f"Failed to disable ticket logging: {str(e)}"
                ),
                ephemeral=True,
            )

    @commands.hybrid_command(name="ticketsupport")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(
        role="The role to ping when new tickets are created (leave empty to view current setting)"
    )
    async def ticket_support_role(self, ctx, role: Optional[discord.Role] = None):
        """Set up or view the support team role for ticket notifications"""
        if not ctx.guild:
            await ctx.send(
                embed=create_error_embed(
                    "Error", "This command can only be used in servers."
                ),
                ephemeral=True,
            )
            return

        if role is None:
            # View current setting
            current_role = self._get_support_team_role(ctx.guild)
            if current_role:
                embed = discord.Embed(
                    title="👥 Ticket Support Role",
                    description=f"Current support role: {current_role.mention}",
                    color=0x5865F2,
                )
                embed.add_field(
                    name="ℹ️ Information",
                    value="This role will be pinged when new tickets are created.\n\n"
                    "• **Change it:** `/ticketsupport @new-role`\n"
                    "• **Remove it:** `/ticketsupport-disable`\n"
                    "• **Set via panel:** `/ticketpanel #channel @role`",
                    inline=False,
                )
            else:
                embed = discord.Embed(
                    title="👥 Ticket Support Role",
                    description="❌ No support role is currently set up.",
                    color=0xE74C3C,
                )
                embed.add_field(
                    name="🔧 Setup Instructions",
                    value="To set a support role:\n"
                    "1. Use `/ticketsupport @role` to set a role\n"
                    "2. Or use `/ticketpanel #channel @role` when creating panels\n"
                    "3. The role will be pinged when new tickets are created",
                    inline=False,
                )

            await ctx.send(embed=embed, ephemeral=True)
            return

        # Set new support role
        try:
            # Save the role to database
            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO ticket_support_roles (guild_id, role_id, set_by, set_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (ctx.guild.id, role.id, ctx.author.id),
            )
            conn.commit()
            conn.close()

            success_embed = discord.Embed(
                title="✅ Support Role Set",
                description=f"Support role set to {role.mention}",
                color=0x2ECC71,
            )
            success_embed.add_field(
                name="📝 What happens now?",
                value=f"• {role.mention} will be pinged when new tickets are created\n"
                f"• Role members will be added to ticket threads automatically\n"
                f"• This setting applies to all new tickets in this server",
                inline=False,
            )
            success_embed.add_field(
                name="💡 Tips",
                value="• Make sure the role is mentionable\n"
                "• You can change this anytime with `/ticketsupport @new-role`\n"
                "• Use `/ticketsupport-disable` to remove the setting",
                inline=False,
            )

            await ctx.send(embed=success_embed, ephemeral=True)

        except Exception as e:
            await ctx.send(
                embed=create_error_embed(
                    "Setup Error", f"Failed to set support role: {str(e)}"
                ),
                ephemeral=True,
            )

    @commands.hybrid_command(name="ticketsupport-disable")
    @commands.has_permissions(administrator=True)
    async def ticket_support_role_disable(self, ctx):
        """Disable the custom support role for tickets"""
        if not ctx.guild:
            await ctx.send(
                embed=create_error_embed(
                    "Error", "This command can only be used in servers."
                ),
                ephemeral=True,
            )
            return

        try:
            # Remove support role setting from database
            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM ticket_support_roles WHERE guild_id = ?", (ctx.guild.id,)
            )
            deleted = cursor.rowcount > 0
            conn.commit()
            conn.close()

            if deleted:
                embed = discord.Embed(
                    title="🚫 Support Role Disabled",
                    description="Custom support role has been removed.",
                    color=0xE74C3C,
                )
                embed.add_field(
                    name="ℹ️ Note",
                    value=f"New tickets will fall back to using the default staff role (ID: {self.staff_role_id}) if it exists.\n"
                    "Use `/ticketsupport @role` to set a new support role.",
                    inline=False,
                )
            else:
                embed = discord.Embed(
                    title="ℹ️ No Custom Role Set",
                    description="There was no custom support role to disable.",
                    color=0x95A5A6,
                )
                embed.add_field(
                    name="Current Status",
                    value=f"Using default staff role (ID: {self.staff_role_id}) if it exists.",
                    inline=False,
                )

            await ctx.send(embed=embed, ephemeral=True)

        except Exception as e:
            await ctx.send(
                embed=create_error_embed(
                    "Error", f"Failed to disable support role: {str(e)}"
                ),
                ephemeral=True,
            )

    @commands.hybrid_command(name="tickets")
    @commands.has_permissions(manage_messages=True)
    @app_commands.describe(
        status="Filter tickets by status (open, closed, all)",
        user="Filter tickets by user",
    )
    async def tickets_list(
        self, ctx, status: str = "open", user: Optional[discord.User] = None
    ):
        """View all tickets or filter by status/user"""
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        query = "SELECT ticket_id, ticket_thread_id, user_id, category, status, claimed_by, created_at FROM tickets"
        params = []

        if status != "all":
            query += " WHERE status = ?"
            params.append(status)

        if user:
            if params:
                query += " AND user_id = ?"
            else:
                query += " WHERE user_id = ?"
            params.append(user.id)

        query += " ORDER BY created_at DESC LIMIT 20"

        cursor.execute(query, params)
        tickets = cursor.fetchall()
        conn.close()

        if not tickets:
            await ctx.send(
                embed=create_info_embed("No Tickets", f"No {status} tickets found."),
                ephemeral=True,
            )
            return

        embed = discord.Embed(title=f" {status.title()} Tickets", color=0x5865F2)

        for ticket in tickets[:10]:  # Show max 10
            (
                ticket_id,
                thread_id,
                user_id,
                category,
                ticket_status,
                claimed_by,
                created_at,
            ) = ticket

            try:
                ticket_user = await self.bot.fetch_user(user_id)
                user_name = f"{ticket_user.name}"
            except:
                user_name = f"Unknown ({user_id})"

            status_emoji = "🟢" if ticket_status == "open" else ""

            claimer_text = ""
            if claimed_by:
                try:
                    claimer = await self.bot.fetch_user(claimed_by)
                    claimer_text = f"\n**Claimed by:** {claimer.name}"
                except:
                    claimer_text = "\n**Claimed by:** Unknown"

            embed.add_field(
                name=f"{status_emoji} Ticket #{ticket_id}",
                value=(
                    f"**User:** {user_name}\n"
                    f"**Category:** {category.title()}\n"
                    f"**Thread:** <#{thread_id}>\n"
                    f"**Created:** <t:{int(datetime.fromisoformat(created_at.replace(' ', 'T')).replace(tzinfo=timezone.utc).timestamp())}:R>"
                    f"{claimer_text}"
                ),
                inline=True,
            )

        embed.set_footer(text=f"Showing {len(tickets[:10])} of {len(tickets)} tickets")

        await ctx.send(embed=embed)

    @commands.hybrid_command(name="ticketstats")
    @commands.has_permissions(manage_messages=True)
    async def ticket_stats(self, ctx):
        """View ticket statistics"""
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        # Get various stats
        cursor.execute("SELECT COUNT(*) FROM tickets")
        total_tickets = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM tickets WHERE status = "open"')
        open_tickets = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM tickets WHERE status = "closed"')
        closed_tickets = cursor.fetchone()[0]

        cursor.execute(
            "SELECT category, COUNT(*) FROM tickets GROUP BY category ORDER BY COUNT(*) DESC"
        )
        categories = cursor.fetchall()

        conn.close()

        embed = discord.Embed(title="📊 Ticket Statistics", color=0x5865F2)

        embed.add_field(
            name="📋 Overview",
            value=(
                f"**Total Tickets:** {total_tickets}\n"
                f"**🟢 Open:** {open_tickets}\n"
                f"**🔴 Closed:** {closed_tickets}"
            ),
            inline=True,
        )

        if categories:
            category_text = "\n".join(
                [f"**{cat.title()}:** {count}" for cat, count in categories[:5]]
            )
            embed.add_field(name="📂 By Category", value=category_text, inline=True)

        embed.timestamp = datetime.now(timezone.utc)
        embed.set_footer(text="CodeVerse Ticket System")

        await ctx.send(embed=embed)

    @commands.hybrid_command(name="forceclose")
    @commands.has_permissions(manage_messages=True)
    @app_commands.describe(
        ticket_id="The ID of the ticket to force close",
        reason="Reason for force closing the ticket",
    )
    async def force_close_ticket(
        self, ctx, ticket_id: int, *, reason: str = "Force closed by staff"
    ):
        """Force close a ticket by its ID (Staff only)"""
        # Get ticket info from database
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT ticket_thread_id, user_id, category FROM tickets WHERE ticket_id = ? AND status = "open"',
            (ticket_id,),
        )
        result = cursor.fetchone()

        if not result:
            await ctx.send(
                embed=create_error_embed(
                    "Ticket Not Found", f"No open ticket found with ID #{ticket_id}"
                ),
                ephemeral=True,
            )
            conn.close()
            return

        thread_id, user_id, category = result

        # Get the thread
        if ctx.guild:
            thread = ctx.guild.get_thread(thread_id)
            if not thread:
                # Try to fetch the thread if not in cache
                try:
                    thread = await ctx.guild.fetch_channel(thread_id)
                except:
                    thread = None
        else:
            thread = None

        # Update database to mark as closed
        cursor.execute(
            'UPDATE tickets SET status = "closed", closed_at = CURRENT_TIMESTAMP, close_reason = ? WHERE ticket_id = ?',
            (f"Force closed by {ctx.author}: {reason}", ticket_id),
        )
        conn.commit()
        conn.close()

        # Send confirmation to command channel
        embed = discord.Embed(
            title="🔒 Ticket Force Closed",
            description=f"Ticket **#{ticket_id}** has been force closed.",
            color=0xE74C3C,
        )
        embed.add_field(
            name="👤 Ticket Owner", value=f"<@{user_id}> ({user_id})", inline=True
        )
        embed.add_field(name="👮 Closed By", value=ctx.author.mention, inline=True)
        embed.add_field(name="📁 Category", value=category.title(), inline=True)
        embed.add_field(name="📝 Reason", value=reason, inline=False)

        if thread:
            embed.add_field(name="📺 Thread", value=thread.mention, inline=True)

        embed.timestamp = datetime.now(timezone.utc)
        embed.set_footer(text="Force Close Command")

        await ctx.send(embed=embed)

        # Send message to thread if it exists and is accessible
        if thread and isinstance(thread, discord.Thread):
            try:
                closure_embed = discord.Embed(
                    title="🔒 Ticket Force Closed",
                    description=f"This ticket has been force closed by {ctx.author.mention}",
                    color=0xE74C3C,
                )
                closure_embed.add_field(name="📝 Reason", value=reason, inline=False)
                closure_embed.add_field(
                    name="ℹ️ Next Steps",
                    value="This thread will be archived and locked in 10 seconds.\nA transcript has been saved.",
                    inline=False,
                )
                closure_embed.timestamp = datetime.now(timezone.utc)

                await thread.send(embed=closure_embed)

                # Generate transcript before archiving
                await self._generate_transcript(thread, ticket_id, save_to_log=True)

                # Archive and lock thread after delay
                try:
                    await asyncio.sleep(10)
                except asyncio.CancelledError:
                    # Shutdown in progress; abort archiving
                    print(
                        f"[Tickets] Archiving for ticket #{ticket_id} cancelled due to shutdown"
                    )
                else:
                    try:
                        await thread.edit(archived=True, locked=True)
                        print(
                            f"[Tickets] 🔒 Thread archived for force closed ticket #{ticket_id}"
                        )
                    except Exception as e:
                        print(
                            f"[Tickets] ❌ Failed to archive force closed ticket thread: {e}"
                        )

            except Exception as e:
                print(f"[Tickets] ❌ Failed to send force close message to thread: {e}")
                # Still continue with logging even if thread message fails

        # Log to staff channel
        if thread:
            await self._log_ticket_action(
                "CLOSED",
                ticket_id,
                thread,
                ctx.author,
                category,
                f"Force closed by {ctx.author.name}: {reason}",
            )

        # Try to DM the ticket owner about the force closure
        try:
            user = await self.bot.fetch_user(user_id)
            if user:
                dm_embed = discord.Embed(
                    title="🔒 Your Ticket Has Been Closed",
                    description=f"Your ticket **#{ticket_id}** in **{ctx.guild.name}** has been closed by staff.",
                    color=0xE74C3C,
                )
                dm_embed.add_field(
                    name="📁 Category", value=category.title(), inline=True
                )
                dm_embed.add_field(
                    name="👮 Closed By", value=str(ctx.author), inline=True
                )
                dm_embed.add_field(name="📝 Reason", value=reason, inline=False)
                dm_embed.set_footer(text=f"{ctx.guild.name} • Ticket System")

                await user.send(embed=dm_embed)
                print(f"[Tickets] 📧 Sent force closure notification to {user}")
        except Exception as e:
            print(f"[Tickets] ❌ Failed to DM user about force closure: {e}")

        print(
            f"[Tickets] 🔒 Ticket #{ticket_id} force closed by {ctx.author} - Reason: {reason}"
        )

    @commands.hybrid_command(name="ticketreport")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(
        role="The role to ping when report tickets are created (leave empty to view current setting)"
    )
    async def ticket_report_role(self, ctx, role: Optional[discord.Role] = None):
        """Set up or view the report team role for report ticket notifications"""
        if not ctx.guild:
            await ctx.send(
                embed=create_error_embed(
                    "Error", "This command can only be used in servers."
                ),
                ephemeral=True,
            )
            return

        if role is None:
            # View current setting
            current_role = self._get_report_team_role(ctx.guild)
            support_role = self._get_support_team_role(ctx.guild)

            if current_role and current_role != support_role:
                embed = discord.Embed(
                    title="📋 Ticket Report Role",
                    description=f"Current report role: {current_role.mention}",
                    color=0xE67E22,
                )
                embed.add_field(
                    name="ℹ️ Information",
                    value="This role will be pinged when report tickets are created.\n\n"
                    "• **Change it:** `/ticketreport @new-role`\n"
                    "• **Remove it:** `/ticketreport-disable`\n"
                    "• **Set via panel:** `/ticketpanel report_role:@role`",
                    inline=False,
                )
            else:
                fallback_msg = (
                    f"\n**Fallback:** Using support role: {support_role.mention}"
                    if support_role
                    else ""
                )
                embed = discord.Embed(
                    title="📋 Ticket Report Role",
                    description=f"❌ No specialized report role is currently set up.{fallback_msg}",
                    color=0xE74C3C,
                )
                embed.add_field(
                    name="🔧 Setup Instructions",
                    value="To set a report role:\n"
                    "1. Use `/ticketreport @role` to set a role\n"
                    "2. Or use `/ticketpanel report_role:@role` when creating panels\n"
                    "3. The role will be pinged when report tickets are created",
                    inline=False,
                )

            await ctx.send(embed=embed, ephemeral=True)
            return

        # Set new report role
        try:
            # Save the role to database
            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO ticket_report_roles (guild_id, role_id, set_by, set_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (ctx.guild.id, role.id, ctx.author.id),
            )
            conn.commit()
            conn.close()

            success_embed = discord.Embed(
                title="✅ Report Role Set",
                description=f"Report role set to {role.mention}",
                color=0x2ECC71,
            )
            success_embed.add_field(
                name="📝 What happens now?",
                value=f"• {role.mention} will be pinged when report tickets are created\n"
                f"• Role members will be added to report ticket threads automatically\n"
                f"• Other ticket types will use the general support role",
                inline=False,
            )
            success_embed.add_field(
                name="💡 Tips",
                value="• Make sure the role is mentionable\n"
                "• You can change this anytime with `/ticketreport @new-role`\n"
                "• Use `/ticketreport-disable` to remove the setting",
                inline=False,
            )

            await ctx.send(embed=success_embed, ephemeral=True)

        except Exception as e:
            await ctx.send(
                embed=create_error_embed(
                    "Setup Error", f"Failed to set report role: {str(e)}"
                ),
                ephemeral=True,
            )

    @commands.hybrid_command(name="ticketreport-disable")
    @commands.has_permissions(administrator=True)
    async def ticket_report_role_disable(self, ctx):
        """Disable the custom report role for tickets"""
        if not ctx.guild:
            await ctx.send(
                embed=create_error_embed(
                    "Error", "This command can only be used in servers."
                ),
                ephemeral=True,
            )
            return

        try:
            # Remove report role setting from database
            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM ticket_report_roles WHERE guild_id = ?", (ctx.guild.id,)
            )
            deleted = cursor.rowcount > 0
            conn.commit()
            conn.close()

            if deleted:
                embed = discord.Embed(
                    title="🚫 Report Role Disabled",
                    description="Custom report role has been removed.",
                    color=0xE74C3C,
                )
                embed.add_field(
                    name="ℹ️ Note",
                    value="Report tickets will now fall back to using the general support role.\n"
                    "Use `/ticketreport @role` to set a new report role.",
                    inline=False,
                )
            else:
                embed = discord.Embed(
                    title="ℹ️ No Custom Role Set",
                    description="There was no custom report role to disable.",
                    color=0x95A5A6,
                )

            await ctx.send(embed=embed, ephemeral=True)

        except Exception as e:
            await ctx.send(
                embed=create_error_embed(
                    "Database Error", f"Failed to disable report role: {str(e)}"
                ),
                ephemeral=True,
            )

    @commands.hybrid_command(name="ticketpartner")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(
        role="The role to ping when partnership tickets are created (leave empty to view current setting)"
    )
    async def ticket_partner_role(self, ctx, role: Optional[discord.Role] = None):
        """Set up or view the partner team role for partnership ticket notifications"""
        if not ctx.guild:
            await ctx.send(
                embed=create_error_embed(
                    "Error", "This command can only be used in servers."
                ),
                ephemeral=True,
            )
            return

        if role is None:
            # View current setting
            current_role = self._get_partner_team_role(ctx.guild)
            support_role = self._get_support_team_role(ctx.guild)

            if current_role and current_role != support_role:
                embed = discord.Embed(
                    title="🤝 Ticket Partner Role",
                    description=f"Current partner role: {current_role.mention}",
                    color=0x9B59B6,
                )
                embed.add_field(
                    name="ℹ️ Information",
                    value="This role will be pinged when partnership tickets are created.\n\n"
                    "• **Change it:** `/ticketpartner @new-role`\n"
                    "• **Remove it:** `/ticketpartner-disable`\n"
                    "• **Set via panel:** `/ticketpanel partner_role:@role`",
                    inline=False,
                )
            else:
                fallback_msg = (
                    f"\n**Fallback:** Using support role: {support_role.mention}"
                    if support_role
                    else ""
                )
                embed = discord.Embed(
                    title="🤝 Ticket Partner Role",
                    description=f"❌ No specialized partner role is currently set up.{fallback_msg}",
                    color=0xE74C3C,
                )
                embed.add_field(
                    name="🔧 Setup Instructions",
                    value="To set a partner role:\n"
                    "1. Use `/ticketpartner @role` to set a role\n"
                    "2. Or use `/ticketpanel partner_role:@role` when creating panels\n"
                    "3. The role will be pinged when partnership tickets are created",
                    inline=False,
                )

            await ctx.send(embed=embed, ephemeral=True)
            return

        # Set new partner role
        try:
            # Save the role to database
            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO ticket_partner_roles (guild_id, role_id, set_by, set_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (ctx.guild.id, role.id, ctx.author.id),
            )
            conn.commit()
            conn.close()

            success_embed = discord.Embed(
                title="✅ Partner Role Set",
                description=f"Partner role set to {role.mention}",
                color=0x2ECC71,
            )
            success_embed.add_field(
                name="📝 What happens now?",
                value=f"• {role.mention} will be pinged when partnership tickets are created\n"
                f"• Role members will be added to partnership ticket threads automatically\n"
                f"• Other ticket types will use the general support role",
                inline=False,
            )
            success_embed.add_field(
                name="💡 Tips",
                value="• Make sure the role is mentionable\n"
                "• You can change this anytime with `/ticketpartner @new-role`\n"
                "• Use `/ticketpartner-disable` to remove the setting",
                inline=False,
            )

            await ctx.send(embed=success_embed, ephemeral=True)

        except Exception as e:
            await ctx.send(
                embed=create_error_embed(
                    "Setup Error", f"Failed to set partner role: {str(e)}"
                ),
                ephemeral=True,
            )

    @commands.hybrid_command(name="ticketpartner-disable")
    @commands.has_permissions(administrator=True)
    async def ticket_partner_role_disable(self, ctx):
        """Disable the custom partner role for tickets"""
        if not ctx.guild:
            await ctx.send(
                embed=create_error_embed(
                    "Error", "This command can only be used in servers."
                ),
                ephemeral=True,
            )
            return

        try:
            # Remove partner role setting from database
            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM ticket_partner_roles WHERE guild_id = ?", (ctx.guild.id,)
            )
            deleted = cursor.rowcount > 0
            conn.commit()
            conn.close()

            if deleted:
                embed = discord.Embed(
                    title="🚫 Partner Role Disabled",
                    description="Custom partner role has been removed.",
                    color=0xE74C3C,
                )
                embed.add_field(
                    name="ℹ️ Note",
                    value="Partnership tickets will now fall back to using the general support role.\n"
                    "Use `/ticketpartner @role` to set a new partner role.",
                    inline=False,
                )
            else:
                embed = discord.Embed(
                    title="ℹ️ No Custom Role Set",
                    description="There was no custom partner role to disable.",
                    color=0x95A5A6,
                )

            await ctx.send(embed=embed, ephemeral=True)

        except Exception as e:
            await ctx.send(
                embed=create_error_embed(
                    "Database Error", f"Failed to disable partner role: {str(e)}"
                ),
                ephemeral=True,
            )


async def setup(bot):
    await bot.add_cog(Tickets(bot))
