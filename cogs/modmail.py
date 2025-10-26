"""
Modmail cog: Users DM the bot, messages are forwarded to a modmail channel. Mods can reply from the channel.
"""
import discord
from discord.ext import commands
from discord import app_commands
from utils.config import Config
from typing import Optional

class ModMail(commands.Cog):
    modmail_sessions: dict[int, str] = {}

    def __init__(self, bot: commands.Bot, config: Config):
        self.bot = bot
        self.config = config
        self.modmail_channel_id: Optional[int] = getattr(config, 'modmail_channel_id', None)

    class ConfirmView(discord.ui.View):
        def __init__(self, cog, user, message_content):
            super().__init__(timeout=300)  # 5 minutes
            self.cog = cog
            self.user = user
            self.message_content = message_content

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
            await interaction.response.send_message("Your message has been sent to the moderators. Please wait for a reply before sending anything else.", ephemeral=True)
            self.cog.modmail_sessions[self.user.id] = 'locked'
            self.stop()

        @discord.ui.button(label="No", style=discord.ButtonStyle.red)
        async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user != self.user:
                return
            await interaction.response.send_message("Message not sent. Send a new message below.", ephemeral=True)
            # Keep session 'open'
            self.stop()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is not None or message.author.bot:
            return
        if not self.modmail_channel_id:
            return
        user_id = message.author.id
        session_state = self.modmail_sessions.get(user_id)
        if session_state is None:
            guideline = (
                "**ModMail System**\n"
                "Send your message to the moderators below.\n"
                "You have only **one message**. After you send it, modmail will be locked until a moderator replies.\n"
                "Please include all your questions and details in this one message.\n"
                "Wait for a moderator to respond before sending anything else."
            )
            await message.author.send(guideline)
            self.modmail_sessions[user_id] = 'open'
            return
        if session_state == 'open':
            embed = discord.Embed(
                title="Confirm ModMail Message",
                description=f"Do you want to send this message to the moderators?\n\n**Message:** {message.content}",
                color=discord.Color.orange()
            )
            view = self.ConfirmView(self, message.author, message.content)
            await message.author.send(embed=embed, view=view)
            return
        if session_state == 'locked':
            try:
                await message.author.send("Your modmail is locked. Please wait for a moderator to reply before sending more messages.")
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
            await user.send(f"**ModMail Reply:** {response}")
            await ctx.send("Reply sent.")
            self.modmail_sessions[user_id] = 'open'
            await user.send("You may now send another message to the moderators if needed.")
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
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return
        try:
            await user.send(f"**ModMail Reply:** {response}")
            await interaction.response.send_message("Reply sent.", ephemeral=True)
            self.modmail_sessions[user.id] = 'open'
            await user.send("You may now send another message to the moderators if needed.")
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
