"""
Roulette game cog.
"""

import random
from typing import List, Optional

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy.ext.asyncio import AsyncSession

from models import Bet
from utils.config import Config
from utils.economy_utils import EconomyUtils
from utils.helpers import EmbedBuilder, format_coins
from bot import Fun2OoshBot


class Roulette(commands.Cog):
    """Roulette game commands."""

    def __init__(self, bot: Fun2OoshBot, config: Config):
        self.bot = bot
        self.config = config

        # Roulette wheel numbers
        self.numbers = list(range(0, 37))  # 0-36

        # Payout multipliers
        self.payouts = {
            'single': 35,  # Bet on single number
            'dozen': 2,    # Bet on dozen (1-12, 13-24, 25-36)
            'column': 2,   # Bet on column
            'red': 1,      # Bet on red
            'black': 1,    # Bet on black
            'even': 1,     # Bet on even
            'odd': 1,      # Bet on odd
            'low': 1,      # Bet on 1-18
            'high': 1      # Bet on 19-36
        }

        # Red numbers
        self.red_numbers = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}

    @commands.command(name='roulette', aliases=['roul'])
    async def roulette(self, ctx: commands.Context, bet_type: str, bet_value: str, amount: int):
        """Play roulette. Usage: ^roulette <type> <value> <amount>

        Types: single <number>, dozen <1-3>, red/black, even/odd, low/high
        Examples: ^roulette single 5 100, ^roulette red 100, ^roulette dozen 1 50
        """
        # Validate bet amount
        valid, reason = EconomyUtils.validate_bet_amount(self.config, amount, 0)
        if not valid:
            await ctx.send(reason)
            return

        # Parse bet
        bet_info = self.parse_bet(bet_type, bet_value)
        if not bet_info:
            await ctx.send("Invalid bet. Use ^commands for examples.")
            return

        bet_type_parsed, bet_value_parsed = bet_info

        # Check balance
        async with self.bot.get_session() as session:
            wallet = await EconomyUtils.get_wallet(session, ctx.author.id)
            if not wallet or wallet.balance < amount:
                await ctx.send("You don't have enough coins to place that bet.")
                return

            # Deduct bet
            success = await EconomyUtils.subtract_money(
                session, ctx.author.id, amount, 'bet', f'Roulette bet: {bet_type_parsed} {bet_value_parsed}', 'roulette'
            )
            if not success:
                await ctx.send("Failed to place bet.")
                return

            await session.commit()

        # Spin the wheel
        result_number = random.choice(self.numbers)
        result_color = 'red' if result_number in self.red_numbers else ('black' if result_number != 0 else 'green')

        # Check if bet wins
        win = self.check_win(bet_type_parsed, bet_value_parsed, result_number, result_color)
        payout = 0

        if win:
            multiplier = self.payouts[bet_type_parsed]
            payout = amount * multiplier

        # Process payout
        async with self.bot.get_session() as session:
            if payout > 0:
                await EconomyUtils.add_money(
                    session, ctx.author.id, payout, 'win', f'Roulette win of {payout}', 'roulette'
                )

            # Record bet
            bet_record = Bet(
                user_id=ctx.author.id,
                game='roulette',
                amount=amount,
                bet_type=f'{bet_type_parsed}:{bet_value_parsed}',
                outcome='win' if win else 'lose',
                payout=payout
            )
            session.add(bet_record)
            await session.commit()

        # Send result
        embed = self.create_roulette_embed(ctx.author, bet_type_parsed, bet_value_parsed, amount, result_number, result_color, win, payout)
        await ctx.send(embed=embed)

    @app_commands.command(name='roulette', description='Play roulette')
    @app_commands.describe(
        bet_type='Type of bet (single, dozen, red, black, even, odd, low, high)',
        bet_value='Value for the bet (number for single, 1-3 for dozen, or empty for others)',
        amount='Amount to bet'
    )
    async def roulette_slash(self, interaction: discord.Interaction, bet_type: str, bet_value: str, amount: int):
        """Slash command for roulette."""
        # Validate bet amount
        valid, reason = EconomyUtils.validate_bet_amount(self.config, amount, 0)
        if not valid:
            await interaction.response.send_message(reason)
            return

        # Parse bet
        bet_info = self.parse_bet(bet_type, bet_value)
        if not bet_info:
            await interaction.response.send_message("Invalid bet. Use /roulette for help.")
            return

        bet_type_parsed, bet_value_parsed = bet_info

        # Check balance
        async with self.bot.get_session() as session:
            wallet = await EconomyUtils.get_wallet(session, interaction.user.id)
            if not wallet or wallet.balance < amount:
                await interaction.response.send_message("You don't have enough coins to place that bet.")
                return

            # Deduct bet
            success = await EconomyUtils.subtract_money(
                session, interaction.user.id, amount, 'bet', f'Roulette bet: {bet_type_parsed} {bet_value_parsed}', 'roulette'
            )
            if not success:
                await interaction.response.send_message("Failed to place bet.")
                return

            await session.commit()

        # Spin the wheel
        result_number = random.choice(self.numbers)
        result_color = 'red' if result_number in self.red_numbers else ('black' if result_number != 0 else 'green')

        # Check if bet wins
        win = self.check_win(bet_type_parsed, bet_value_parsed, result_number, result_color)
        payout = 0

        if win:
            multiplier = self.payouts[bet_type_parsed]
            payout = amount * multiplier

        # Process payout
        async with self.bot.get_session() as session:
            if payout > 0:
                await EconomyUtils.add_money(
                    session, interaction.user.id, payout, 'win', f'Roulette win of {payout}', 'roulette'
                )

            # Record bet
            bet_record = Bet(
                user_id=interaction.user.id,
                game='roulette',
                amount=amount,
                bet_type=f'{bet_type_parsed}:{bet_value_parsed}',
                outcome='win' if win else 'lose',
                payout=payout
            )
            session.add(bet_record)
            await session.commit()

        # Send result
        embed = self.create_roulette_embed(interaction.user, bet_type_parsed, bet_value_parsed, amount, result_number, result_color, win, payout)
        await interaction.response.send_message(embed=embed)

    def parse_bet(self, bet_type: str, bet_value: str) -> Optional[tuple]:
        """Parse bet type and value."""
        bet_type = bet_type.lower()
        bet_value = bet_value.lower()

        if bet_type == 'single':
            try:
                number = int(bet_value)
                if 0 <= number <= 36:
                    return 'single', str(number)
            except ValueError:
                pass
        elif bet_type == 'dozen':
            try:
                dozen = int(bet_value)
                if 1 <= dozen <= 3:
                    return 'dozen', str(dozen)
            except ValueError:
                pass
        elif bet_type in ['red', 'black', 'even', 'odd', 'low', 'high']:
            return bet_type, bet_value

        return None

    def check_win(self, bet_type: str, bet_value: str, number: int, color: str) -> bool:
        """Check if bet wins."""
        if bet_type == 'single':
            return int(bet_value) == number
        elif bet_type == 'dozen':
            dozen = int(bet_value)
            if dozen == 1:
                return 1 <= number <= 12
            elif dozen == 2:
                return 13 <= number <= 24
            elif dozen == 3:
                return 25 <= number <= 36
        elif bet_type == 'red':
            return color == 'red'
        elif bet_type == 'black':
            return color == 'black'
        elif bet_type == 'even':
            return number != 0 and number % 2 == 0
        elif bet_type == 'odd':
            return number % 2 == 1
        elif bet_type == 'low':
            return 1 <= number <= 18
        elif bet_type == 'high':
            return 19 <= number <= 36

        return False

    def create_roulette_embed(self, user: discord.User | discord.Member, bet_type: str, bet_value: str, amount: int,
                             result_number: int, result_color: str, win: bool, payout: int) -> discord.Embed:
        """Create roulette result embed."""
        embed = EmbedBuilder.info_embed("🎡 Roulette", "")

        embed.add_field(name="Your Bet", value=f"{bet_type.title()} {bet_value}", inline=True)
        embed.add_field(name="Bet Amount", value=format_coins(amount), inline=True)
        embed.add_field(name="Result", value=f"{result_number} ({result_color.title()})", inline=True)

        if win:
            embed.add_field(name="Win", value=format_coins(payout), inline=True)
            embed.add_field(name="Net", value=format_coins(payout - amount), inline=True)
            embed.color = discord.Color.green()
        else:
            embed.add_field(name="Win", value="0 coins", inline=True)
            embed.add_field(name="Net", value=format_coins(-amount), inline=True)
            embed.color = discord.Color.red()

        return embed


async def setup(bot):
    """Setup the roulette cog."""
    config = bot.config
    await bot.add_cog(Roulette(bot, config))
