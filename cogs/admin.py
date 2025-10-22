"""
Admin commands cog.
"""

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from models import User, Wallet
from utils.config import Config
from utils.economy_utils import EconomyUtils
from utils.helpers import EmbedBuilder
from bot import Fun2OoshBot


class Admin(commands.Cog):
    """Admin commands."""

    def __init__(self, bot: Fun2OoshBot, config: Config):
        self.bot = bot
        self.config = config

    async def cog_check(self, ctx: commands.Context):
        """Check if user is owner."""
        return ctx.author.id == self.config.owner_id

    @commands.command(name='add_money')
    async def add_money(self, ctx: commands.Context, user: discord.User, amount: int):
        """Add money to a user (admin only)."""
        async with self.bot.get_session() as session:
            success = await EconomyUtils.add_money(
                session, user.id, amount, 'admin', f'Admin added {amount} coins'
            )

            if success:
                await session.commit()
                await ctx.send(f"Added {amount} coins to {user.mention}.")
            else:
                await ctx.send("Failed to add money.")

    @app_commands.command(name='add_money', description='Add money to a user (admin only)')
    @app_commands.describe(user='User to add money to', amount='Amount to add')
    async def add_money_slash(self, interaction: discord.Interaction, user: discord.User, amount: int):
        """Slash command for adding money."""
        if interaction.user.id != self.config.owner_id:
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return

        async with self.bot.get_session() as session:
            success = await EconomyUtils.add_money(
                session, user.id, amount, 'admin', f'Admin added {amount} coins'
            )

            if success:
                await session.commit()
                await interaction.response.send_message(f"Added {amount} coins to {user.mention}.")
            else:
                await interaction.response.send_message("Failed to add money.")

    @commands.command(name='reset_economy')
    async def reset_economy(self, ctx: commands.Context, confirmation: str = ""):
        """Reset all economy data (admin only - dangerous).
        
        Usage: ^reset_economy CONFIRM
        This will delete ALL wallets, transactions, and bets. Use with extreme caution!
        """
        if confirmation.upper() != "CONFIRM":
            embed = EmbedBuilder.error_embed(
                "⚠️ Dangerous Operation",
                "This command will **permanently delete** all economy data including:\n"
                "• All user wallets and balances\n"
                "• All transaction history\n"
                "• All bet records\n\n"
                f"To confirm, type: `{ctx.prefix}reset_economy CONFIRM`"
            )
            await ctx.send(embed=embed)
            return

        # Double confirmation with reaction
        embed = EmbedBuilder.error_embed(
            "🚨 FINAL WARNING 🚨",
            "You are about to **IRREVERSIBLY DELETE** all economy data!\n\n"
            "React with ✅ to proceed or ❌ to cancel."
        )
        message = await ctx.send(embed=embed)
        await message.add_reaction("✅")
        await message.add_reaction("❌")

        def check(reaction, user):
            return (
                user == ctx.author
                and str(reaction.emoji) in ["✅", "❌"]
                and reaction.message.id == message.id
            )

        try:
            reaction, user = await self.bot.wait_for("reaction_add", timeout=30.0, check=check)
            
            if str(reaction.emoji) == "❌":
                await ctx.send("Economy reset cancelled.")
                return
                
            if str(reaction.emoji) == "✅":
                # Proceed with reset
                async with self.bot.get_session() as session:
                    # Delete all data in correct order (respecting foreign keys)
                    await session.execute(text("DELETE FROM bets"))
                    await session.execute(text("DELETE FROM transactions")) 
                    await session.execute(text("DELETE FROM wallets"))
                    await session.commit()
                
                embed = EmbedBuilder.success_embed(
                    "✅ Economy Reset Complete",
                    "All economy data has been permanently deleted and reset."
                )
                await ctx.send(embed=embed)
                
        except TimeoutError:
            await ctx.send("Economy reset timed out. Operation cancelled.")

    @app_commands.command(name='reset_economy', description='Reset all economy data (admin only - dangerous)')
    @app_commands.describe(confirmation='Type CONFIRM to proceed')
    async def reset_economy_slash(self, interaction: discord.Interaction, confirmation: str):
        """Slash command for resetting economy."""
        if interaction.user.id != self.config.owner_id:
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return

        if confirmation.upper() != "CONFIRM":
            embed = EmbedBuilder.error_embed(
                "⚠️ Dangerous Operation",
                "This command will **permanently delete** all economy data including:\n"
                "• All user wallets and balances\n"
                "• All transaction history\n"
                "• All bet records\n\n"
                "To confirm, type: `CONFIRM`"
            )
            await interaction.response.send_message(embed=embed)
            return

        # Simple confirmation for slash commands
        embed = EmbedBuilder.error_embed(
            "🚨 FINAL WARNING 🚨",
            "You are about to **IRREVERSIBLY DELETE** all economy data!\n\n"
            "This action cannot be undone. Are you sure?"
        )
        await interaction.response.send_message(embed=embed)

        # For slash commands, we'll just proceed since they already confirmed
        async with self.bot.get_session() as session:
            # Delete all data in correct order (respecting foreign keys)
            await session.execute(text("DELETE FROM bets"))
            await session.execute(text("DELETE FROM transactions")) 
            await session.execute(text("DELETE FROM wallets"))
            await session.commit()
        
        embed = EmbedBuilder.success_embed(
            "✅ Economy Reset Complete",
            "All economy data has been permanently deleted and reset."
        )
        await interaction.followup.send(embed=embed)


async def setup(bot):
    """Setup the admin cog."""
    config = bot.config
    await bot.add_cog(Admin(bot, config))
