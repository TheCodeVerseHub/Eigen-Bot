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

    @commands.command(name='transfer', aliases=['pay'])
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

    @commands.command(name='beg')
    @check_cooldown('beg', 60)  # 1 minute
    async def beg(self, ctx: commands.Context):
        """Beg for coins from strangers."""
        import random
        
        # 70% chance to get coins
        if random.random() < 0.7:
            reward = random.randint(10, 100)
            
            responses = [
                f"A kind stranger gave you {format_coins(reward)}!",
                f"Someone felt generous and donated {format_coins(reward)}!",
                f"You found {format_coins(reward)} someone dropped!",
                f"A wealthy person tossed you {format_coins(reward)}!",
                f"You begged successfully and got {format_coins(reward)}!"
            ]
            
            async with self.bot.get_session() as session:
                await EconomyUtils.add_money(
                    session, ctx.author.id, reward, 'beg', 'Begging reward'
                )
                await session.commit()
            
            embed = EmbedBuilder.success_embed("💰 Success!", random.choice(responses))
            await ctx.send(embed=embed)
        else:
            responses = [
                "Everyone ignored you... 😢",
                "People walked past you without looking.",
                "No one gave you anything today.",
                "The streets are empty...",
                "Someone told you to get a job!"
            ]
            embed = discord.Embed(
                title="❌ No Luck",
                description=random.choice(responses),
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @commands.command(name='crime')
    @check_cooldown('crime', 300)  # 5 minutes
    async def crime(self, ctx: commands.Context):
        """Commit a crime for big rewards (or losses)."""
        import random
        
        # 40% success rate
        success = random.random() < 0.4
        
        crimes = [
            ("robbed a bank", 500, 1500),
            ("hacked a corporation", 800, 2000),
            ("stole a rare painting", 600, 1800),
            ("smuggled contraband", 400, 1200),
            ("pickpocketed tourists", 300, 800),
        ]
        
        crime_desc, min_reward, max_reward = random.choice(crimes)
        
        if success:
            reward = random.randint(min_reward, max_reward)
            
            async with self.bot.get_session() as session:
                await EconomyUtils.add_money(
                    session, ctx.author.id, reward, 'crime', f'Crime: {crime_desc}'
                )
                await session.commit()
            
            embed = EmbedBuilder.success_embed(
                "🎭 Crime Success!",
                f"You {crime_desc} and got away with {format_coins(reward)}!"
            )
            await ctx.send(embed=embed)
        else:
            fine = random.randint(200, 600)
            
            async with self.bot.get_session() as session:
                wallet = await EconomyUtils.get_or_create_wallet(session, ctx.author.id)
                if wallet.balance >= fine:
                    wallet.balance -= fine
                    await session.commit()
                    loss_msg = f"You were caught and fined {format_coins(fine)}!"
                else:
                    loss_msg = "You were caught but had no money to pay the fine!"
            
            embed = discord.Embed(
                title="🚔 Caught!",
                description=f"You tried to {crime_desc} but got caught!\n{loss_msg}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @commands.command(name='rob', aliases=['steal'])
    @check_cooldown('rob', 600)  # 10 minutes
    async def rob(self, ctx: commands.Context, user: discord.User):
        """Try to rob another user (risky!)."""
        import random
        
        if user == ctx.author:
            return await ctx.send("You can't rob yourself!")
        
        if user.bot:
            return await ctx.send("You can't rob bots!")
        
        async with self.bot.get_session() as session:
            robber_wallet = await EconomyUtils.get_or_create_wallet(session, ctx.author.id)
            victim_wallet = await EconomyUtils.get_or_create_wallet(session, user.id)
            
            # Need at least 200 coins to attempt robbery
            if robber_wallet.balance < 200:
                return await ctx.send("You need at least 200 coins to attempt a robbery!")
            
            # Victim needs coins to rob
            if victim_wallet.balance < 100:
                return await ctx.send(f"{user.display_name} doesn't have enough coins to rob!")
            
            # 35% success rate
            success = random.random() < 0.35
            
            if success:
                # Rob 10-30% of victim's balance
                rob_amount = int(victim_wallet.balance * random.uniform(0.1, 0.3))
                rob_amount = min(rob_amount, 5000)  # Cap at 5000
                
                victim_wallet.balance -= rob_amount
                robber_wallet.balance += rob_amount
                await session.commit()
                
                embed = EmbedBuilder.success_embed(
                    "💰 Robbery Success!",
                    f"You robbed {format_coins(rob_amount)} from {user.mention}!"
                )
                await ctx.send(embed=embed)
            else:
                # Failed - lose 200-500 coins
                fine = random.randint(200, 500)
                fine = min(fine, robber_wallet.balance)
                
                robber_wallet.balance -= fine
                victim_wallet.balance += fine // 2  # Victim gets half
                await session.commit()
                
                embed = discord.Embed(
                    title="🚔 Robbery Failed!",
                    description=f"You were caught trying to rob {user.mention}!\n"
                               f"You lost {format_coins(fine)} and they got {format_coins(fine // 2)}!",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)

    @commands.command(name='gamble', aliases=['bet'])
    @check_cooldown('gamble', 30)  # 30 seconds
    async def gamble(self, ctx: commands.Context, amount: int):
        """Gamble your coins! 45% chance to double, 55% chance to lose all."""
        import random
        
        if amount < 50:
            return await ctx.send("Minimum gamble is 50 coins!")
        
        if amount > 10000:
            return await ctx.send("Maximum gamble is 10,000 coins!")
        
        async with self.bot.get_session() as session:
            wallet = await EconomyUtils.get_or_create_wallet(session, ctx.author.id)
            
            if wallet.balance < amount:
                return await ctx.send(f"You don't have enough coins! Balance: {format_coins(wallet.balance)}")
            
            # Deduct bet
            wallet.balance -= amount
            
            # 45% win rate
            won = random.random() < 0.45
            
            if won:
                payout = amount * 2
                wallet.balance += payout
                await session.commit()
                
                embed = discord.Embed(
                    title="🎲 GAMBLE",
                    description="━━━━━━━━━━━━━━━━━━━━━━",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="OUTCOME",
                    value=f"```diff\n+ WIN\n```\n**Payout:** {format_coins(payout)}\n**Profit:** +{format_coins(amount)}",
                    inline=False
                )
                embed.add_field(
                    name="BALANCE",
                    value=f"```\n{wallet.balance:,} coins\n```",
                    inline=False
                )
            else:
                await session.commit()
                
                embed = discord.Embed(
                    title="🎲 GAMBLE",
                    description="━━━━━━━━━━━━━━━━━━━━━━",
                    color=discord.Color.red()
                )
                embed.add_field(
                    name="OUTCOME",
                    value=f"```diff\n- LOSS\n```\n**Lost:** {format_coins(amount)}",
                    inline=False
                )
                embed.add_field(
                    name="BALANCE",
                    value=f"```\n{wallet.balance:,} coins\n```",
                    inline=False
                )
            
            embed.set_footer(text="Economy • Quick Gamble")
            await ctx.send(embed=embed)

    @commands.command(name='richest', aliases=['top10', 'baltop'])
    async def richest(self, ctx: commands.Context):
        """Show the top 15 richest users with detailed stats."""
        async with self.bot.get_session() as session:
            stmt = select(
                Wallet.user_id,
                Wallet.balance,
                Wallet.bank,
                (Wallet.balance + Wallet.bank).label('total')
            ).order_by(desc('total')).limit(15)
            result = await session.execute(stmt)
            users = result.all()
        
        if not users:
            return await ctx.send("No users found in the economy!")
        
        embed = discord.Embed(
            title="💎 TOP 15 RICHEST PLAYERS",
            description="━━━━━━━━━━━━━━━━━━━━━━",
            color=discord.Color.gold()
        )
        
        medals = ["🥇", "🥈", "🥉"]
        
        for idx, user_data in enumerate(users, 1):
            try:
                user = await self.bot.fetch_user(user_data.user_id)
                name = user.display_name
            except:
                name = f"User {user_data.user_id}"
            
            medal = medals[idx - 1] if idx <= 3 else f"#{idx}"
            
            embed.add_field(
                name=f"{medal} {name}",
                value=f"```\nTotal: {user_data.total:,}\nWallet: {user_data.balance:,}\nBank: {user_data.bank:,}\n```",
                inline=True
            )
        
        embed.set_footer(text="Economy • Leaderboard")
        await ctx.send(embed=embed)

    @commands.command(name='give', aliases=['gift'])
    async def give(self, ctx: commands.Context, user: discord.User, amount: int):
        """Give coins to another user (no tax)."""
        if user == ctx.author:
            return await ctx.send("You can't give coins to yourself!")
        
        if user.bot:
            return await ctx.send("You can't give coins to bots!")
        
        if amount <= 0:
            return await ctx.send("Amount must be positive!")
        
        if amount < 10:
            return await ctx.send("Minimum gift amount is 10 coins!")
        
        async with self.bot.get_session() as session:
            sender_wallet = await EconomyUtils.get_or_create_wallet(session, ctx.author.id)
            
            if sender_wallet.balance < amount:
                return await ctx.send(f"You don't have enough coins! Balance: {format_coins(sender_wallet.balance)}")
            
            # Transfer
            sender_wallet.balance -= amount
            await EconomyUtils.add_money(
                session, user.id, amount, 'gift', f'Gift from {ctx.author.display_name}'
            )
            await session.commit()
        
        embed = EmbedBuilder.success_embed(
            "🎁 Gift Sent!",
            f"You gave {format_coins(amount)} to {user.mention}!"
        )
        await ctx.send(embed=embed)

    @commands.command(name='search')
    @check_cooldown('search', 45)  # 45 seconds
    async def search(self, ctx: commands.Context):
        """Search random places for coins."""
        import random
        
        locations = [
            ("couch cushions", 20, 80),
            ("park bench", 30, 100),
            ("parking lot", 15, 60),
            ("vending machine", 25, 90),
            ("library books", 10, 50),
            ("trash bin", 5, 40),
            ("car seats", 30, 110),
            ("beach sand", 40, 120),
        ]
        
        location, min_reward, max_reward = random.choice(locations)
        
        # 80% chance to find something
        if random.random() < 0.8:
            reward = random.randint(min_reward, max_reward)
            
            async with self.bot.get_session() as session:
                await EconomyUtils.add_money(
                    session, ctx.author.id, reward, 'search', f'Searched {location}'
                )
                await session.commit()
            
            embed = EmbedBuilder.success_embed(
                f"🔍 Found!",
                f"You searched the **{location}** and found {format_coins(reward)}!"
            )
        else:
            embed = discord.Embed(
                title="🔍 Nothing Found",
                description=f"You searched the **{location}** but found nothing...",
                color=discord.Color.orange()
            )
        
        await ctx.send(embed=embed)

    @commands.command(name='profile', aliases=['prof', 'stats'])
    async def profile(self, ctx: commands.Context, user: Optional[discord.User] = None):
        """View detailed profile and economy stats."""
        target = user or ctx.author
        
        async with self.bot.get_session() as session:
            wallet = await EconomyUtils.get_or_create_wallet(session, target.id)
            
            # Get transaction count
            tx_stmt = select(func.count(Transaction.id)).where(Transaction.user_id == target.id)
            tx_result = await session.execute(tx_stmt)
            tx_count = tx_result.scalar() or 0
            
            # Get total earned
            earn_stmt = select(func.sum(Transaction.amount)).where(
                Transaction.user_id == target.id,
                Transaction.amount > 0
            )
            earn_result = await session.execute(earn_stmt)
            total_earned = earn_result.scalar() or 0
        
        total_wealth = wallet.balance + wallet.bank
        
        embed = discord.Embed(
            title=f"📊 {target.display_name}'s Profile",
            description="━━━━━━━━━━━━━━━━━━━━━━",
            color=discord.Color.blue()
        )
        
        embed.set_thumbnail(url=target.display_avatar.url)
        
        embed.add_field(
            name="💰 WEALTH",
            value=f"```\nTotal: {total_wealth:,}\nWallet: {wallet.balance:,}\nBank: {wallet.bank:,}\n```",
            inline=False
        )
        
        embed.add_field(
            name="📈 STATISTICS",
            value=f"```\nTransactions: {tx_count}\nTotal Earned: {total_earned:,}\n```",
            inline=False
        )
        
        embed.set_footer(text=f"Economy • User ID: {target.id}")
        await ctx.send(embed=embed)


async def setup(bot):
    """Setup the economy cog."""
    config = bot.config
    await bot.add_cog(Economy(bot, config))
