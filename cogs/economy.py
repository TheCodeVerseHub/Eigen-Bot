"""
Economy cog for wallet management and basic income commands.
"""

import time
from typing import List, Optional, Tuple

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Bet, Transaction, Wallet
from utils.anti_fraud import anti_fraud
from utils.cooldowns import check_cooldown, cooldown_manager
from utils.config import Config
from utils.economy_utils import EconomyUtils
from bot import Fun2OoshBot
from utils.helpers import EmbedBuilder, format_coins, responsible_gaming_notice


class Economy(commands.Cog):
    """Economy commands for the bot."""

    def __init__(self, bot: Fun2OoshBot, config: Config):
        self.bot = bot
        self.config = config

    async def cog_load(self):
        """Called when the cog is loaded."""
        pass

    @commands.command(name='balance', aliases=['bal', 'wallet'])
    async def balance(self, ctx: commands.Context, user: Optional[discord.User] = None):
        """Check your or another user's balance."""
        target_user = user or ctx.author

        async with self.bot.get_session() as session:
            wallet = await EconomyUtils.get_or_create_wallet(session, target_user.id)
            await session.commit()  # Ensure wallet is saved

        embed = EmbedBuilder.wallet_embed(target_user, wallet.balance, wallet.bank)
        await ctx.send(embed=embed)

    @app_commands.command(name='balance', description='Check your balance')
    async def balance_slash(self, interaction: discord.Interaction):
        """Slash command for balance."""
        async with self.bot.get_session() as session:
            wallet = await EconomyUtils.get_or_create_wallet(session, interaction.user.id)
            await session.commit()  # Ensure wallet is saved

        embed = EmbedBuilder.wallet_embed(interaction.user, wallet.balance, wallet.bank)
        await interaction.response.send_message(embed=embed)

    @commands.command(name='work')
    @check_cooldown('work', 1800)  # 30 minutes
    async def work(self, ctx: commands.Context):
        """Work to earn some coins."""
        reward = self.config.work_reward

        async with self.bot.get_session() as session:
            success = await EconomyUtils.add_money(
                session, ctx.author.id, reward, 'work', 'Daily work reward'
            )

            if success:
                await session.commit()
                embed = EmbedBuilder.success_embed(
                    "Work Complete!",
                    f"You worked hard and earned {format_coins(reward)}!"
                )
                await ctx.send(embed=embed)
            else:
                await ctx.send("An error occurred while processing your work reward.")

    @app_commands.command(name='work', description='Work to earn coins')
    @app_commands.checks.cooldown(1, 1800, key=lambda i: (i.guild_id, i.user.id))
    async def work_slash(self, interaction: discord.Interaction):
        """Slash command for work."""
        reward = self.config.work_reward

        async with self.bot.get_session() as session:
            success = await EconomyUtils.add_money(
                session, interaction.user.id, reward, 'work', 'Daily work reward'
            )

            if success:
                await session.commit()
                embed = EmbedBuilder.success_embed(
                    "Work Complete!",
                    f"You worked hard and earned {format_coins(reward)}!"
                )
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message("An error occurred while processing your work reward.")

    @commands.command(name='collect', aliases=['hourly'])
    @check_cooldown('collect', 3600)  # 1 hour
    async def collect(self, ctx: commands.Context):
        """Collect hourly reward."""
        reward = 50  # Fixed for now

        async with self.bot.get_session() as session:
            success = await EconomyUtils.add_money(
                session, ctx.author.id, reward, 'collect', 'Hourly collect reward'
            )

            if success:
                await session.commit()
                embed = EmbedBuilder.success_embed(
                    "Collection Complete!",
                    f"You collected {format_coins(reward)}!"
                )
                await ctx.send(embed=embed)
            else:
                await ctx.send("An error occurred while processing your collection.")

    @app_commands.command(name='collect', description='Collect hourly reward')
    @app_commands.checks.cooldown(1, 3600, key=lambda i: (i.guild_id, i.user.id))
    async def collect_slash(self, interaction: discord.Interaction):
        """Slash command for collect."""
        reward = 50  # Fixed for now

        async with self.bot.get_session() as session:
            success = await EconomyUtils.add_money(
                session, interaction.user.id, reward, 'collect', 'Hourly collect reward'
            )

            if success:
                await session.commit()
                embed = EmbedBuilder.success_embed(
                    "Collection Complete!",
                    f"You collected {format_coins(reward)}!"
                )
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message("An error occurred while processing your collection.")

    @commands.command(name='daily')
    @check_cooldown('daily', 86400)  # 24 hours
    async def daily(self, ctx: commands.Context):
        """Claim daily reward."""
        reward = self.config.daily_reward

        async with self.bot.get_session() as session:
            success = await EconomyUtils.add_money(
                session, ctx.author.id, reward, 'daily', 'Daily reward'
            )

            if success:
                await session.commit()
                embed = EmbedBuilder.success_embed(
                    "Daily Reward Claimed!",
                    f"You claimed your daily reward of {format_coins(reward)}!"
                )
                await ctx.send(embed=embed)
            else:
                await ctx.send("An error occurred while processing your daily reward.")

    @app_commands.command(name='daily', description='Claim daily reward')
    @app_commands.checks.cooldown(1, 86400, key=lambda i: (i.guild_id, i.user.id))
    async def daily_slash(self, interaction: discord.Interaction):
        """Slash command for daily."""
        reward = self.config.daily_reward

        async with self.bot.get_session() as session:
            success = await EconomyUtils.add_money(
                session, interaction.user.id, reward, 'daily', 'Daily reward'
            )

            if success:
                await session.commit()
                embed = EmbedBuilder.success_embed(
                    "Daily Reward Claimed!",
                    f"You claimed your daily reward of {format_coins(reward)}!"
                )
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message("An error occurred while processing your daily reward.")

    @commands.command(name='weekly')
    @check_cooldown('weekly', 604800)  # 7 days
    async def weekly(self, ctx: commands.Context):
        """Claim weekly reward."""
        reward = self.config.weekly_reward

        async with self.bot.get_session() as session:
            success = await EconomyUtils.add_money(
                session, ctx.author.id, reward, 'weekly', 'Weekly reward'
            )

            if success:
                await session.commit()
                embed = EmbedBuilder.success_embed(
                    "Weekly Reward Claimed!",
                    f"You claimed your weekly reward of {format_coins(reward)}!"
                )
                await ctx.send(embed=embed)
            else:
                await ctx.send("An error occurred while processing your weekly reward.")

    @app_commands.command(name='weekly', description='Claim weekly reward')
    @app_commands.checks.cooldown(1, 604800, key=lambda i: (i.guild_id, i.user.id))
    async def weekly_slash(self, interaction: discord.Interaction):
        """Slash command for weekly."""
        reward = self.config.weekly_reward

        async with self.bot.get_session() as session:
            success = await EconomyUtils.add_money(
                session, interaction.user.id, reward, 'weekly', 'Weekly reward'
            )

            if success:
                await session.commit()
                embed = EmbedBuilder.success_embed(
                    "Weekly Reward Claimed!",
                    f"You claimed your weekly reward of {format_coins(reward)}!"
                )
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message("An error occurred while processing your weekly reward.")

    @commands.command(name='deposit')
    async def deposit(self, ctx: commands.Context, amount: str):
        """Deposit coins from wallet to bank."""
        try:
            if amount.lower() == 'all':
                async with self.bot.get_session() as session:
                    wallet = await EconomyUtils.get_wallet(session, ctx.author.id)
                    if wallet and wallet.balance > 0:
                        amount_int = wallet.balance
                    else:
                        await ctx.send("You don't have any coins to deposit.")
                        return
            else:
                amount_int = int(amount)
                if amount_int <= 0:
                    await ctx.send("Deposit amount must be positive.")
                    return
        except ValueError:
            await ctx.send("Invalid amount. Please provide a number or 'all'.")
            return

        async with self.bot.get_session() as session:
            wallet = await EconomyUtils.get_wallet(session, ctx.author.id)
            if not wallet or wallet.balance < amount_int:
                await ctx.send("You don't have enough coins in your wallet.")
                return

            wallet.balance -= amount_int
            wallet.bank += amount_int

            tx = Transaction(
                user_id=ctx.author.id,
                type='deposit',
                amount=-amount_int,
                description=f'Deposited {amount_int} coins to bank'
            )
            session.add(tx)
            await session.commit()

        embed = EmbedBuilder.success_embed(
            "Deposit Successful",
            f"You deposited {format_coins(amount_int)} to your bank."
        )
        await ctx.send(embed=embed)

    @app_commands.command(name='deposit', description='Deposit coins from wallet to bank')
    @app_commands.describe(amount='Amount to deposit (number or "all")')
    async def deposit_slash(self, interaction: discord.Interaction, amount: str):
        """Slash command for deposit."""
        try:
            if amount.lower() == 'all':
                async with self.bot.get_session() as session:
                    wallet = await EconomyUtils.get_wallet(session, interaction.user.id)
                    if wallet and wallet.balance > 0:
                        amount_int = wallet.balance
                    else:
                        await interaction.response.send_message("You don't have any coins to deposit.")
                        return
            else:
                amount_int = int(amount)
                if amount_int <= 0:
                    await interaction.response.send_message("Deposit amount must be positive.")
                    return
        except ValueError:
            await interaction.response.send_message("Invalid amount. Please provide a number or 'all'.")
            return

        async with self.bot.get_session() as session:
            wallet = await EconomyUtils.get_wallet(session, interaction.user.id)
            if not wallet or wallet.balance < amount_int:
                await interaction.response.send_message("You don't have enough coins in your wallet.")
                return

            wallet.balance -= amount_int
            wallet.bank += amount_int

            tx = Transaction(
                user_id=interaction.user.id,
                type='deposit',
                amount=-amount_int,
                description=f'Deposited {amount_int} coins to bank'
            )
            session.add(tx)
            await session.commit()

        embed = EmbedBuilder.success_embed(
            "Deposit Successful",
            f"You deposited {format_coins(amount_int)} to your bank."
        )
        await interaction.response.send_message(embed=embed)

    @commands.command(name='withdraw')
    async def withdraw(self, ctx: commands.Context, amount: str):
        """Withdraw coins from bank to wallet."""
        try:
            if amount.lower() == 'all':
                async with self.bot.get_session() as session:
                    wallet = await EconomyUtils.get_wallet(session, ctx.author.id)
                    if wallet and wallet.bank > 0:
                        amount_int = wallet.bank
                    else:
                        await ctx.send("You don't have any coins in your bank.")
                        return
            else:
                amount_int = int(amount)
                if amount_int <= 0:
                    await ctx.send("Withdraw amount must be positive.")
                    return
        except ValueError:
            await ctx.send("Invalid amount. Please provide a number or 'all'.")
            return

        async with self.bot.get_session() as session:
            wallet = await EconomyUtils.get_wallet(session, ctx.author.id)
            if not wallet or wallet.bank < amount_int:
                await ctx.send("You don't have enough coins in your bank.")
                return

            wallet.bank -= amount_int
            wallet.balance += amount_int

            tx = Transaction(
                user_id=ctx.author.id,
                type='withdraw',
                amount=amount_int,
                description=f'Withdrew {amount_int} coins from bank'
            )
            session.add(tx)
            await session.commit()

        embed = EmbedBuilder.success_embed(
            "Withdrawal Successful",
            f"You withdrew {format_coins(amount_int)} from your bank."
        )
        await ctx.send(embed=embed)

    @app_commands.command(name='withdraw', description='Withdraw coins from bank to wallet')
    @app_commands.describe(amount='Amount to withdraw (number or "all")')
    async def withdraw_slash(self, interaction: discord.Interaction, amount: str):
        """Slash command for withdraw."""
        try:
            if amount.lower() == 'all':
                async with self.bot.get_session() as session:
                    wallet = await EconomyUtils.get_wallet(session, interaction.user.id)
                    if wallet and wallet.bank > 0:
                        amount_int = wallet.bank
                    else:
                        await interaction.response.send_message("You don't have any coins in your bank.")
                        return
            else:
                amount_int = int(amount)
                if amount_int <= 0:
                    await interaction.response.send_message("Withdraw amount must be positive.")
                    return
        except ValueError:
            await interaction.response.send_message("Invalid amount. Please provide a number or 'all'.")
            return

        async with self.bot.get_session() as session:
            wallet = await EconomyUtils.get_wallet(session, interaction.user.id)
            if not wallet or wallet.bank < amount_int:
                await interaction.response.send_message("You don't have enough coins in your bank.")
                return

            wallet.bank -= amount_int
            wallet.balance += amount_int

            tx = Transaction(
                user_id=interaction.user.id,
                type='withdraw',
                amount=amount_int,
                description=f'Withdrew {amount_int} coins from bank'
            )
            session.add(tx)
            await session.commit()

        embed = EmbedBuilder.success_embed(
            "Withdrawal Successful",
            f"You withdrew {format_coins(amount_int)} from your bank."
        )
        await interaction.response.send_message(embed=embed)

    @commands.command(name='transfer', aliases=['pay', 'give'])
    async def transfer(self, ctx: commands.Context, user: discord.User, amount: int):
        """Transfer coins to another user."""
        if user == ctx.author:
            await ctx.send("You can't transfer coins to yourself.")
            return

        if amount <= 0:
            await ctx.send("Transfer amount must be positive.")
            return

        # Check for fraud
        suspicious, reason = anti_fraud.is_suspicious(ctx.author.id, amount, 'transfer')
        if suspicious:
            await ctx.send(f"Transfer blocked: {reason}")
            return

        async with self.bot.get_session() as session:
            success = await EconomyUtils.transfer_money(
                session, ctx.author.id, user.id, amount,
                f'Transfer from {ctx.author.display_name}'
            )

        if success:
            embed = EmbedBuilder.success_embed(
                "Transfer Successful",
                f"You transferred {format_coins(amount)} to {user.mention}."
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("Transfer failed. Check your balance and try again.")

    @app_commands.command(name='transfer', description='Transfer coins to another user')
    @app_commands.describe(user='User to transfer to', amount='Amount to transfer')
    async def transfer_slash(self, interaction: discord.Interaction, user: discord.User, amount: int):
        """Slash command for transfer."""
        if user == interaction.user:
            await interaction.response.send_message("You can't transfer coins to yourself.")
            return

        if amount <= 0:
            await interaction.response.send_message("Transfer amount must be positive.")
            return

        # Check for fraud
        suspicious, reason = anti_fraud.is_suspicious(interaction.user.id, amount, 'transfer')
        if suspicious:
            await interaction.response.send_message(f"Transfer blocked: {reason}")
            return

        async with self.bot.get_session() as session:
            success = await EconomyUtils.transfer_money(
                session, interaction.user.id, user.id, amount,
                f'Transfer from {interaction.user.display_name}'
            )

        if success:
            embed = EmbedBuilder.success_embed(
                "Transfer Successful",
                f"You transferred {format_coins(amount)} to {user.mention}."
            )
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("Transfer failed. Check your balance and try again.")

    @commands.command(name='leaderboard', aliases=['lb', 'top'])
    async def leaderboard(self, ctx: commands.Context):
        """Show the top 10 richest users."""
        async with self.bot.get_session() as session:
            stmt = select(
                Wallet.user_id,
                (Wallet.balance + Wallet.bank).label('total')
            ).order_by(desc('total')).limit(10)
            result = await session.execute(stmt)
            leaderboard = [(row.user_id, row.total) for row in result.all()]

        embed = EmbedBuilder.leaderboard_embed(leaderboard, "🏆 Richest Players")
        await ctx.send(embed=embed)

    @app_commands.command(name='leaderboard', description='Show the leaderboard')
    async def leaderboard_slash(self, interaction: discord.Interaction):
        """Slash command for leaderboard."""
        async with self.bot.get_session() as session:
            stmt = select(
                Wallet.user_id,
                (Wallet.balance + Wallet.bank).label('total')
            ).order_by(desc('total')).limit(10)
            result = await session.execute(stmt)
            leaderboard = [(row.user_id, row.total) for row in result.all()]

        embed = EmbedBuilder.leaderboard_embed(leaderboard, "🏆 Richest Players")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    """Setup the economy cog."""
    config = bot.config
    await bot.add_cog(Economy(bot, config))
