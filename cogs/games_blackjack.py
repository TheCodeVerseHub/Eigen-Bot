"""
Blackjack game cog.
"""

import random
from typing import List, Optional

import discord
from discord import app_commands, ui
from discord.ext import commands
from sqlalchemy.ext.asyncio import AsyncSession

from models import Bet
from utils.anti_fraud import anti_fraud
from utils.config import Config
from utils.economy_utils import EconomyUtils
from utils.helpers import EmbedBuilder, format_coins, RNG
from bot import Fun2OoshBot


class Card:
    """Represents a playing card."""

    SUITS = ['♠', '♥', '♦', '♣']
    RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']

    def __init__(self, suit: str, rank: str):
        self.suit = suit
        self.rank = rank

    def value(self) -> int:
        """Get the numerical value of the card."""
        if self.rank in ['J', 'Q', 'K']:
            return 10
        elif self.rank == 'A':
            return 11  # Will be adjusted for aces
        else:
            return int(self.rank)

    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"


class Hand:
    """Represents a hand of cards."""

    def __init__(self):
        self.cards: List[Card] = []

    def add_card(self, card: Card):
        """Add a card to the hand."""
        self.cards.append(card)

    def value(self) -> int:
        """Calculate the total value of the hand."""
        value = 0
        aces = 0

        for card in self.cards:
            if card.rank == 'A':
                aces += 1
                value += 11
            else:
                value += card.value()

        # Adjust for aces
        while value > 21 and aces:
            value -= 10
            aces -= 1

        return value

    def is_blackjack(self) -> bool:
        """Check if hand is a blackjack."""
        return len(self.cards) == 2 and self.value() == 21

    def is_bust(self) -> bool:
        """Check if hand is bust."""
        return self.value() > 21

    def __str__(self) -> str:
        return ' '.join(str(card) for card in self.cards)


class Deck:
    """Represents a deck of cards."""

    def __init__(self):
        self.cards: List[Card] = []
        self.reset()

    def reset(self):
        """Reset the deck with all 52 cards."""
        self.cards = [Card(suit, rank) for suit in Card.SUITS for rank in Card.RANKS]
        random.shuffle(self.cards)

    def deal(self) -> Card:
        """Deal a card from the deck."""
        if not self.cards:
            self.reset()
        return self.cards.pop()


class BlackjackGame:
    """Represents a blackjack game."""

    def __init__(self, player_id: int, bet_amount: int):
        self.player_id = player_id
        self.bet_amount = bet_amount
        self.deck = Deck()
        self.player_hand = Hand()
        self.dealer_hand = Hand()
        self.game_over = False
        self.result = None

        # Initial deal
        self.player_hand.add_card(self.deck.deal())
        self.dealer_hand.add_card(self.deck.deal())
        self.player_hand.add_card(self.deck.deal())
        self.dealer_hand.add_card(self.deck.deal())

        # Check for initial blackjack
        if self.player_hand.is_blackjack():
            self.stand()  # Dealer plays

    def hit(self):
        """Player hits."""
        if self.game_over:
            return

        self.player_hand.add_card(self.deck.deal())
        if self.player_hand.is_bust():
            self.game_over = True
            self.result = 'lose'

    def stand(self):
        """Player stands, dealer plays."""
        if self.game_over:
            return

        # Dealer hits on 16, stands on 17
        while self.dealer_hand.value() < 17:
            self.dealer_hand.add_card(self.deck.deal())

        # Determine winner
        player_val = self.player_hand.value()
        dealer_val = self.dealer_hand.value()

        if self.dealer_hand.is_bust():
            self.result = 'win'
        elif player_val > dealer_val:
            self.result = 'win'
        elif player_val < dealer_val:
            self.result = 'lose'
        else:
            self.result = 'push'

        self.game_over = True

    def get_payout(self) -> int:
        """Calculate payout based on result."""
        if self.result == 'win':
            if self.player_hand.is_blackjack():
                return int(self.bet_amount * 2.5)  # 3:2 payout for blackjack
            else:
                return self.bet_amount * 2  # 1:1 payout
        elif self.result == 'push':
            return self.bet_amount  # Return bet
        else:
            return 0  # Loss


class BlackjackView(ui.View):
    """Button view for blackjack game interactions."""

    def __init__(self, cog: 'Blackjack', game: BlackjackGame, player_id: int):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
        self.game = game
        self.player_id = player_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if the interaction is from the correct player."""
        return interaction.user.id == self.player_id

    @ui.button(label="Hit", style=discord.ButtonStyle.primary, emoji="🃏")
    async def hit_button(self, interaction: discord.Interaction, button: ui.Button):
        """Handle hit button click."""
        if self.game.game_over:
            await interaction.response.send_message("This game has already ended!", ephemeral=True)
            return

        self.game.hit()

        if self.game.game_over:
            # Game ended, update the embed and disable buttons
            embed = self.cog.create_game_embed(self.game)
            self.disable_buttons()
            await interaction.response.edit_message(embed=embed, view=self)
            
            # Send result message
            payout = self.game.get_payout()
            await self.cog.process_game_end_slash(interaction, self.game, payout)
        else:
            # Game continues, update the embed
            embed = self.cog.create_game_embed(self.game)
            await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="Stand", style=discord.ButtonStyle.secondary, emoji="🛑")
    async def stand_button(self, interaction: discord.Interaction, button: ui.Button):
        """Handle stand button click."""
        if self.game.game_over:
            await interaction.response.send_message("This game has already ended!", ephemeral=True)
            return

        self.game.stand()
        
        # Game always ends when standing
        embed = self.cog.create_game_embed(self.game)
        self.disable_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
        
        # Send result message
        payout = self.game.get_payout()
        await self.cog.process_game_end_slash(interaction, self.game, payout)

    def disable_buttons(self):
        """Disable all buttons when game ends."""
        for child in self.children:
            if isinstance(child, ui.Button):
                child.disabled = True


class Blackjack(commands.Cog):
    """Blackjack game commands."""

    def __init__(self, bot: Fun2OoshBot, config: Config):
        self.bot = bot
        self.config = config
        self.active_games: dict[int, BlackjackGame] = {}

    @commands.command(name='blackjack', aliases=['bj'])
    async def blackjack(self, ctx: commands.Context, bet: int):
        """Start a blackjack game."""
        # Validate bet
        valid, reason = EconomyUtils.validate_bet_amount(self.config, bet, 0)  # TODO: track daily wagered
        if not valid:
            await ctx.send(reason)
            return

        # Check for active game
        if ctx.author.id in self.active_games:
            await ctx.send("You already have an active blackjack game. Use ^hit or ^stand to continue.")
            return

        # Check balance
        async with self.bot.get_session() as session:
            wallet = await EconomyUtils.get_wallet(session, ctx.author.id)
            if not wallet or wallet.balance < bet:
                await ctx.send("You don't have enough coins to place that bet.")
                return

            # Deduct bet
            success = await EconomyUtils.subtract_money(
                session, ctx.author.id, bet, 'bet', f'Blackjack bet of {bet}', 'blackjack'
            )
            if not success:
                await ctx.send("Failed to place bet.")
                return

            await session.commit()

        # Start game
        game = BlackjackGame(ctx.author.id, bet)
        self.active_games[ctx.author.id] = game

        # Create embed and button view
        embed = self.create_game_embed(game)
        view = BlackjackView(self, game, ctx.author.id)

        # Send initial game state with buttons
        await ctx.send(embed=embed, view=view)

    @app_commands.command(name='blackjack', description='Start a blackjack game')
    @app_commands.describe(bet='Amount to bet')
    async def blackjack_slash(self, interaction: discord.Interaction, bet: int):
        """Slash command for blackjack."""
        # Defer the response to give us more time for database operations
        await interaction.response.defer()

        # Validate bet
        valid, reason = EconomyUtils.validate_bet_amount(self.config, bet, 0)  # TODO: track daily wagered
        if not valid:
            await interaction.followup.send(reason)
            return

        # Check for active game
        if interaction.user.id in self.active_games:
            await interaction.followup.send("You already have an active blackjack game. Use the buttons in your game to continue.")
            return

        # Check balance
        async with self.bot.get_session() as session:
            wallet = await EconomyUtils.get_wallet(session, interaction.user.id)
            if not wallet or wallet.balance < bet:
                await interaction.followup.send("You don't have enough coins to place that bet.")
                return

            # Deduct bet
            success = await EconomyUtils.subtract_money(
                session, interaction.user.id, bet, 'bet', f'Blackjack bet of {bet}', 'blackjack'
            )
            if not success:
                await interaction.followup.send("Failed to place bet.")
                return

            await session.commit()

        # Start game
        game = BlackjackGame(interaction.user.id, bet)
        self.active_games[interaction.user.id] = game

        # Create embed and button view
        embed = self.create_game_embed(game)
        view = BlackjackView(self, game, interaction.user.id)

        # Send initial game state with buttons
        await interaction.followup.send(embed=embed, view=view)

    @commands.command(name='hit')
    async def hit(self, ctx: commands.Context):
        """Hit in blackjack."""
        if ctx.author.id not in self.active_games:
            await ctx.send("You don't have an active blackjack game. Start one with ^blackjack <bet>")
            return

        await ctx.send("Use the **Hit** button in your blackjack game instead of this command!")

    @app_commands.command(name='hit', description='Hit in blackjack (use buttons in game instead)')
    async def hit_slash(self, interaction: discord.Interaction):
        """Slash command for hit."""
        if interaction.user.id not in self.active_games:
            await interaction.response.send_message("You don't have an active blackjack game. Start one with /blackjack <bet>")
            return

        await interaction.response.send_message("Use the **Hit** button in your blackjack game instead of this command!", ephemeral=True)

    @commands.command(name='stand')
    async def stand(self, ctx: commands.Context):
        """Stand in blackjack."""
        if ctx.author.id not in self.active_games:
            await ctx.send("You don't have an active blackjack game. Start one with ^blackjack <bet>")
            return

        await ctx.send("Use the **Stand** button in your blackjack game instead of this command!")

    @app_commands.command(name='stand', description='Stand in blackjack (use buttons in game instead)')
    async def stand_slash(self, interaction: discord.Interaction):
        """Slash command for stand."""
        if interaction.user.id not in self.active_games:
            await interaction.response.send_message("You don't have an active blackjack game. Start one with /blackjack <bet>")
            return

        await interaction.response.send_message("Use the **Stand** button in your blackjack game instead of this command!", ephemeral=True)

    async def send_game_embed(self, ctx: commands.Context, game: BlackjackGame):
        """Send the current game state as an embed."""
        embed = EmbedBuilder.info_embed("🃏 Blackjack", "")

        embed.add_field(
            name="Your Hand",
            value=f"{game.player_hand} (Value: {game.player_hand.value()})",
            inline=False
        )

        dealer_cards = str(game.dealer_hand)
        if not game.game_over:
            # Hide dealer's second card
            cards = dealer_cards.split()
            dealer_cards = f"{cards[0]} ?? (Value: ?)"

        embed.add_field(
            name="Dealer Hand",
            value=f"{dealer_cards} (Value: {game.dealer_hand.value() if game.game_over else '?'})",
            inline=False
        )

        embed.add_field(name="Bet", value=format_coins(game.bet_amount), inline=True)

        if game.game_over:
            embed.add_field(name="Result", value=game.result.title() if game.result else "Unknown", inline=True)

        await ctx.send(embed=embed)

    async def send_game_embed_slash(self, interaction: discord.Interaction, game: BlackjackGame, use_followup: bool = False):
        """Send the current game state as an embed for slash commands."""
        embed = EmbedBuilder.info_embed("🃏 Blackjack", "")

        embed.add_field(
            name="Your Hand",
            value=f"{game.player_hand} (Value: {game.player_hand.value()})",
            inline=False
        )

        dealer_cards = str(game.dealer_hand)
        if not game.game_over:
            # Hide dealer's second card
            cards = dealer_cards.split()
            dealer_cards = f"{cards[0]} ?? (Value: ?)"

        embed.add_field(
            name="Dealer Hand",
            value=f"{dealer_cards} (Value: {game.dealer_hand.value() if game.game_over else '?'})",
            inline=False
        )

        embed.add_field(name="Bet", value=format_coins(game.bet_amount), inline=True)

        if game.game_over:
            embed.add_field(name="Result", value=game.result.title() if game.result else "Unknown", inline=True)

        if use_followup:
            await interaction.followup.send(embed=embed)
        else:
            await interaction.response.send_message(embed=embed)

    async def end_game(self, ctx: commands.Context, game: BlackjackGame):
        """End the game and process payout."""
        payout = game.get_payout()

        async with self.bot.get_session() as session:
            if payout > game.bet_amount:
                # Win
                win_amount = payout - game.bet_amount
                await EconomyUtils.add_money(
                    session, ctx.author.id, win_amount, 'win', f'Blackjack win of {win_amount}', 'blackjack'
                )
            elif payout == 0:
                # Loss - already deducted
                pass
            else:
                # Push - return bet
                await EconomyUtils.add_money(
                    session, ctx.author.id, game.bet_amount, 'push', 'Blackjack push', 'blackjack'
                )

            # Record bet
            bet_record = Bet(
                user_id=ctx.author.id,
                game='blackjack',
                amount=game.bet_amount,
                outcome=game.result,
                payout=payout
            )
            session.add(bet_record)
            await session.commit()

        # Send final embed
        await self.send_game_embed(ctx, game)

        # Send result message
        if game.result == 'win':
            await ctx.send(f"🎉 You won {format_coins(payout)}!")
        elif game.result == 'lose':
            await ctx.send("😞 You lost. Better luck next time!")
        else:
            await ctx.send("🤝 Push! Your bet has been returned.")

        # Clean up
        del self.active_games[ctx.author.id]

    async def end_game_slash(self, interaction: discord.Interaction, game: BlackjackGame, initial_response_sent: bool = True):
        """End the game and process payout for slash commands."""
        payout = game.get_payout()

        async with self.bot.get_session() as session:
            if payout > game.bet_amount:
                # Win
                win_amount = payout - game.bet_amount
                await EconomyUtils.add_money(
                    session, interaction.user.id, win_amount, 'win', f'Blackjack win of {win_amount}', 'blackjack'
                )
            elif payout == 0:
                # Loss - already deducted
                pass
            else:
                # Push - return bet
                await EconomyUtils.add_money(
                    session, interaction.user.id, game.bet_amount, 'push', 'Blackjack push', 'blackjack'
                )

            # Record bet
            bet_record = Bet(
                user_id=interaction.user.id,
                game='blackjack',
                amount=game.bet_amount,
                outcome=game.result,
                payout=payout
            )
            session.add(bet_record)
            await session.commit()

        # Send final embed
        if initial_response_sent:
            await self.send_game_embed_slash(interaction, game, use_followup=True)
        else:
            await self.send_game_embed_slash(interaction, game, use_followup=False)

        # Send result message
        if game.result == 'win':
            await interaction.followup.send(f"🎉 You won {format_coins(payout)}!")
        elif game.result == 'lose':
            await interaction.followup.send("😞 You lost. Better luck next time!")
        else:
            await interaction.followup.send("🤝 Push! Your bet has been returned.")

        # Clean up
        del self.active_games[interaction.user.id]

    def create_game_embed(self, game: BlackjackGame) -> discord.Embed:
        """Create the current game state as an embed."""
        embed = EmbedBuilder.info_embed("🃏 Blackjack", "")

        embed.add_field(
            name="Your Hand",
            value=f"{game.player_hand} (Value: {game.player_hand.value()})",
            inline=False
        )

        dealer_cards = str(game.dealer_hand)
        if not game.game_over:
            # Hide dealer's second card
            cards = dealer_cards.split()
            dealer_cards = f"{cards[0]} ?? (Value: ?)"

        embed.add_field(
            name="Dealer Hand",
            value=f"{dealer_cards} (Value: {game.dealer_hand.value() if game.game_over else '?'})",
            inline=False
        )

        embed.add_field(name="Bet", value=format_coins(game.bet_amount), inline=True)

        if game.game_over:
            embed.add_field(name="Result", value=game.result.title() if game.result else "Unknown", inline=True)

        return embed

    async def process_game_end_slash(self, interaction: discord.Interaction, game: BlackjackGame, payout: int):
        """Process game end and send result message."""
        # Send result message as followup
        if game.result == 'win':
            await interaction.followup.send(f"🎉 You won {format_coins(payout)}!")
        elif game.result == 'lose':
            await interaction.followup.send("😞 You lost. Better luck next time!")
        else:
            await interaction.followup.send("🤝 Push! Your bet has been returned.")

        # Clean up
        if interaction.user.id in self.active_games:
            del self.active_games[interaction.user.id]


async def setup(bot):
    """Setup the blackjack cog."""
    config = bot.config
    await bot.add_cog(Blackjack(bot, config))
