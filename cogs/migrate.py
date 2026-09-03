"""Move a recent conversation from one channel to another.

Grabs the last N messages in the current channel and reposts them in a
target channel via webhook (so author name/avatar are preserved), then
points people at the new channel.
"""

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

MAX_MESSAGES = 25
WEBHOOK_NAME = "Eigen Migration"
RELAYABLE_TYPES = (discord.MessageType.default, discord.MessageType.reply)


class MigrateConversation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _get_or_create_webhook(
        self, channel: discord.TextChannel
    ) -> discord.Webhook:
        for webhook in await channel.webhooks():
            if webhook.name == WEBHOOK_NAME:
                return webhook
        return await channel.create_webhook(
            name=WEBHOOK_NAME, reason="Conversation migration"
        )

    async def _fetch_messages_to_move(
        self, channel: discord.TextChannel, count: int
    ) -> list[discord.Message]:
        messages = [
            m async for m in channel.history(limit=count) if m.type in RELAYABLE_TYPES
        ]
        messages.reverse()  # oldest first, so they land in the right order
        return messages

    async def _relay_message(
        self, webhook: discord.Webhook, message: discord.Message
    ) -> None:
        files = [await a.to_file() for a in message.attachments]

        await webhook.send(
            content=message.content[:2000],
            username=message.author.display_name,
            avatar_url=message.author.display_avatar.url,
            embeds=message.embeds,
            files=files,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @app_commands.command(
        name="migrate-conversation",
        description="Move the recent conversation here to another channel",
    )
    @app_commands.describe(
        destination="Channel to move the conversation to",
        count="Number of recent messages to move (default 10, max 25)",
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.checks.cooldown(1, 30, key=lambda i: i.guild_id)
    async def migrate_conversation(
        self,
        interaction: discord.Interaction,
        destination: discord.TextChannel,
        count: app_commands.Range[int, 1, MAX_MESSAGES] = 10,
    ):
        if interaction.guild is None or not isinstance(
            interaction.channel, discord.TextChannel
        ):
            await interaction.response.send_message(
                "This command can only be used in a server text channel.",
                ephemeral=True,
            )
            return

        source = interaction.channel

        if destination.id == source.id:
            await interaction.response.send_message(
                "Pick a different channel to migrate to.", ephemeral=True
            )
            return

        bot_perms = destination.permissions_for(interaction.guild.me)
        if not bot_perms.manage_webhooks or not bot_perms.send_messages:
            await interaction.response.send_message(
                f"I need **Manage Webhooks** and **Send Messages** permission in {destination.mention} to do this.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        messages = await self._fetch_messages_to_move(source, count)
        if not messages:
            await interaction.followup.send(
                "No recent messages found to move.", ephemeral=True
            )
            return

        webhook = await self._get_or_create_webhook(destination)

        moved = 0
        for message in messages:
            try:
                await self._relay_message(webhook, message)
                moved += 1
            except discord.HTTPException:
                continue
            await asyncio.sleep(0.4)  # stay comfortably under webhook rate limits

        if moved == 0:
            await interaction.followup.send(
                "Couldn't move any messages, try again.", ephemeral=True
            )
            return

        await source.send(
            f"📦 This conversation has moved to {destination.mention}. Continue there!",
            allowed_mentions=discord.AllowedMentions.none(),
        )
        await interaction.followup.send(
            f"Moved **{moved}** message(s) to {destination.mention}.", ephemeral=True
        )

    @migrate_conversation.error
    async def migrate_conversation_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You need the **Manage Messages** permission to use this command.",
                ephemeral=True,
            )
        elif isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"This command is on cooldown. Try again in {error.retry_after:.1f}s.",
                ephemeral=True,
            )
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(MigrateConversation(bot))
