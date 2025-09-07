"""
Slots game cog.
"""

import random
from typing import List, Tuple

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy.ext.asyncio import AsyncSession

from models import Bet
from utils.config import Config
from utils.economy_utils import EconomyUtils
from utils.helpers import EmbedBuilder, format_coins
from bot import Fun2OoshBot


class Slots(commands.Cog):
    """Slots game commands."""

    def __init__(self, bot: Fun2OoshBot, config: Config):
        self.bot = bot
        self.config = config

        # Slot symbols and their weights
        self.symbols = ['🍒', '🍋', '🍊', '🍇', '🔔', '💎', '7️⃣']
        self.weights = [30, 25, 20, 15, 7, 2, 1]  # Higher weight = more common

        # Paytable: symbol -> multiplier for matches
        self.paytable = {
            '🍒': {2: 2, 3: 5},
            '🍋': {2: 3, 3: 8},
            '🍊': {2: 4, 3: 10},
            '🍇': {2: 5, 3: 15},
            '🔔': {2: 8, 3: 25},
            '💎': {2: 10, 3: 50},
            '7️⃣': {2: 15, 3: 100}  # Jackpot
        }

    @commands.command(name='slots', aliases=['slot'])
    async def slots(self, ctx: commands.Context, bet: int):
        """Play slots."""
        # Validate bet
        valid, reason = EconomyUtils.validate_bet_amount(self.config, bet, 0)
        if not valid:
            await ctx.send(reason)
            return

        # Check balance
        async with self.bot.get_session() as session:
            wallet = await EconomyUtils.get_wallet(session, ctx.author.id)
            if not wallet or wallet.balance < bet:
                await ctx.send("You don't have enough coins to place that bet.")
                return

            # Deduct bet
            success = await EconomyUtils.subtract_money(
                session, ctx.author.id, bet, 'bet', f'Slots bet of {bet}', 'slots'
            )
            if not success:
                await ctx.send("Failed to place bet.")
                return

            await session.commit()

        # Spin the reels
        reel1 = random.choices(self.symbols, weights=self.weights)[0]
        reel2 = random.choices(self.symbols, weights=self.weights)[0]
        reel3 = random.choices(self.symbols, weights=self.weights)[0]

        reels = [reel1, reel2, reel3]

        # Calculate winnings
        payout = self.calculate_payout(reels, bet)

        # Process payout
        async with self.bot.get_session() as session:
            if payout > 0:
                await EconomyUtils.add_money(
                    session, ctx.author.id, payout, 'win', f'Slots win of {payout}', 'slots'
                )

            # Record bet
            bet_record = Bet(
                user_id=ctx.author.id,
                game='slots',
                amount=bet,
                outcome='win' if payout > 0 else 'lose',
                payout=payout
            )
            session.add(bet_record)
            await session.commit()

        # Send result
        embed = self.create_slots_embed(ctx.author, reels, bet, payout)
        await ctx.send(embed=embed)

    @app_commands.command(name='slots', description='Play slots')
    @app_commands.describe(bet='Amount to bet')
    async def slots_slash(self, interaction: discord.Interaction, bet: int):
        """Slash command for slots."""
        # Validate bet
        valid, reason = EconomyUtils.validate_bet_amount(self.config, bet, 0)
        if not valid:
            await interaction.response.send_message(reason)
            return

        # Check balance
        async with self.bot.get_session() as session:
            wallet = await EconomyUtils.get_wallet(session, interaction.user.id)
            if not wallet or wallet.balance < bet:
                await interaction.response.send_message("You don't have enough coins to place that bet.")
                return

            # Deduct bet
            success = await EconomyUtils.subtract_money(
                session, interaction.user.id, bet, 'bet', f'Slots bet of {bet}', 'slots'
            )
            if not success:
                await interaction.response.send_message("Failed to place bet.")
                return

            await session.commit()

        # Spin the reels
        reel1 = random.choices(self.symbols, weights=self.weights)[0]
        reel2 = random.choices(self.symbols, weights=self.weights)[0]
        reel3 = random.choices(self.symbols, weights=self.weights)[0]

        reels = [reel1, reel2, reel3]

        # Calculate winnings
        payout = self.calculate_payout(reels, bet)

        # Process payout
        async with self.bot.get_session() as session:
            if payout > 0:
                await EconomyUtils.add_money(
                    session, interaction.user.id, payout, 'win', f'Slots win of {payout}', 'slots'
                )

            # Record bet
            bet_record = Bet(
                user_id=interaction.user.id,
                game='slots',
                amount=bet,
                outcome='win' if payout > 0 else 'lose',
                payout=payout
            )
            session.add(bet_record)
            await session.commit()

        # Send result
        embed = self.create_slots_embed(interaction.user, reels, bet, payout)
        await interaction.response.send_message(embed=embed)

    def calculate_payout(self, reels: List[str], bet: int) -> int:
        """Calculate payout based on reels."""
        if reels[0] == reels[1] == reels[2]:
            # Three of a kind
            symbol = reels[0]
            multiplier = self.paytable.get(symbol, {}).get(3, 0)
            return bet * multiplier
        elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
            # Two of a kind
            # Find which two match
            if reels[0] == reels[1]:
                symbol = reels[0]
            elif reels[1] == reels[2]:
                symbol = reels[1]
            else:
                symbol = reels[0]

            multiplier = self.paytable.get(symbol, {}).get(2, 0)
            return bet * multiplier
        else:
            return 0

    def create_slots_embed(self, user: discord.User | discord.Member, reels: List[str], bet: int, payout: int) -> discord.Embed:
        """Create slots result embed."""
        embed = EmbedBuilder.info_embed("🎰 Slots", "")

        # Display reels
        reel_display = f"│ {reels[0]} │ {reels[1]} │ {reels[2]} │"
        embed.add_field(name="Reels", value=f"```\n{reel_display}\n```", inline=False)

        embed.add_field(name="Bet", value=format_coins(bet), inline=True)

        if payout > 0:
            embed.add_field(name="Win", value=format_coins(payout), inline=True)
            embed.add_field(name="Net", value=format_coins(payout - bet), inline=True)
            embed.color = discord.Color.green()
        else:
            embed.add_field(name="Win", value="0 coins", inline=True)
            embed.add_field(name="Net", value=format_coins(-bet), inline=True)
            embed.color = discord.Color.red()

        return embed


async def setup(bot):
    """Setup the slots cog."""
    config = bot.config
    await bot.add_cog(Slots(bot, config))
