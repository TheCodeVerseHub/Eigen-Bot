"""
Admin commands cog for Eigen bot.
"""

import discord
from discord import app_commands
from discord.ext import commands

from utils.config import Config
from utils.helpers import EmbedBuilder


class Admin(commands.Cog):
    """Admin commands for server management."""

    def __init__(self, bot: commands.Bot, config: Config):
        self.bot = bot
        self.config = config

    async def _is_owner_or_admin_interaction(self, interaction: discord.Interaction) -> bool:
        """Allow owner or users with administrator permission for slash commands."""
        if self.config.owner_id and interaction.user.id == self.config.owner_id:
            return True

        if interaction.guild is None:
            return False

        if isinstance(interaction.user, discord.Member):
            return interaction.user.guild_permissions.administrator

        try:
            member = await interaction.guild.fetch_member(interaction.user.id)
        except Exception:
            return False
        return member.guild_permissions.administrator

    async def cog_check(self, ctx: commands.Context):
        """Allow owner or users with administrator permission."""
        if self.config.owner_id and ctx.author.id == self.config.owner_id:
            return True
        if ctx.guild is not None:
            member = ctx.guild.get_member(ctx.author.id)
            if member and member.guild_permissions.administrator:
                return True
        return False

    @commands.command(name='reload')
    @commands.has_permissions(administrator=True)
    async def reload_cog(self, ctx: commands.Context, cog_name: str):
        """Reload a cog (admin only)."""
        try:
            await self.bot.reload_extension(f'cogs.{cog_name}')
            embed = EmbedBuilder.success_embed(
                "Cog Reloaded",
                f"Successfully reloaded `{cog_name}`"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = EmbedBuilder.error_embed(
                "Failed to Reload",
                f"Could not reload `{cog_name}`: {e!s}"
            )
            await ctx.send(embed=embed)

    @app_commands.command(name='reload', description='Reload a cog (admin only)')
    @app_commands.describe(cog_name='Name of the cog to reload')
    @app_commands.default_permissions(administrator=True)
    async def reload_cog_slash(self, interaction: discord.Interaction, cog_name: str):
        """Slash command for reloading cogs."""
        if not await self._is_owner_or_admin_interaction(interaction):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
            return

        try:
            await self.bot.reload_extension(f'cogs.{cog_name}')
            embed = EmbedBuilder.success_embed(
                "Cog Reloaded",
                f"Successfully reloaded `{cog_name}`"
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            embed = EmbedBuilder.error_embed(
                "Failed to Reload",
                f"Could not reload `{cog_name}`: {e!s}"
            )
            await interaction.response.send_message(embed=embed)

    @commands.command(name='sync')
    @commands.has_permissions(administrator=True)
    async def sync_commands(self, ctx: commands.Context):
        """Sync slash commands (admin only)."""
        try:
            # Prefer syncing to the guild where the command was invoked.
            if ctx.guild is not None:
                guild_id = ctx.guild.id
                guild = discord.Object(id=guild_id)
                self.bot.tree.clear_commands(guild=guild)
                self.bot.tree.copy_global_to(guild=guild)
                synced = await self.bot.tree.sync(guild=guild)
                embed = EmbedBuilder.success_embed(
                    "Commands Synced",
                    f"Synced {len(synced)} commands to this guild ({guild_id})"
                )
            elif self.config.guild_ids:
                for guild_id in self.config.guild_ids:
                    guild = discord.Object(id=guild_id)
                    self.bot.tree.clear_commands(guild=guild)
                    self.bot.tree.copy_global_to(guild=guild)
                    synced = await self.bot.tree.sync(guild=guild)

                embed = EmbedBuilder.success_embed(
                    "Commands Synced",
                    f"Synced commands to {len(self.config.guild_ids)} configured guild(s)."
                )
            else:
                synced = await self.bot.tree.sync()
                embed = EmbedBuilder.success_embed(
                    "Commands Synced",
                    f"Synced {len(synced)} commands globally"
                )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = EmbedBuilder.error_embed(
                "Sync Failed",
                f"Failed to sync commands: {e!s}"
            )
            await ctx.send(embed=embed)

    @app_commands.command(name='sync', description='Sync slash commands (admin only)')
    @app_commands.default_permissions(administrator=True)
    async def sync_commands_slash(self, interaction: discord.Interaction):
        """Slash command for syncing commands."""
        if not await self._is_owner_or_admin_interaction(interaction):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            if interaction.guild_id is not None:
                guild_id = interaction.guild_id
                guild = discord.Object(id=guild_id)
                self.bot.tree.clear_commands(guild=guild)
                self.bot.tree.copy_global_to(guild=guild)
                synced = await self.bot.tree.sync(guild=guild)
                embed = EmbedBuilder.success_embed(
                    "Commands Synced",
                    f"Synced {len(synced)} commands to this guild ({guild_id})"
                )
            elif self.config.guild_ids:
                for guild_id in self.config.guild_ids:
                    guild = discord.Object(id=guild_id)
                    self.bot.tree.clear_commands(guild=guild)
                    self.bot.tree.copy_global_to(guild=guild)
                    await self.bot.tree.sync(guild=guild)

                embed = EmbedBuilder.success_embed(
                    "Commands Synced",
                    f"Synced commands to {len(self.config.guild_ids)} configured guild(s)."
                )
            else:
                synced = await self.bot.tree.sync()
                embed = EmbedBuilder.success_embed(
                    "Commands Synced",
                    f"Synced {len(synced)} commands globally"
                )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            embed = EmbedBuilder.error_embed(
                "Sync Failed",
                f"Failed to sync commands: {e!s}"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    """Setup the admin cog."""
    config = bot.config
    await bot.add_cog(Admin(bot, config))
