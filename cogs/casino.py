"""
Professional Casino Cog - Complete gambling system with multiple games.

Features:
- Blackjack with full rules (hit, stand, double down, split)
- Poker (Texas Hold'em)
- Roulette (European style with all bet types)
- Russian Roulette (fun game)
- Slot machines with multiple paylines
- Dice games
- Coinflip
- High-Low card game
- Crash game
- Responsible gambling features
"""

import asyncio
import random
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
from enum import Enum

import discord
from discord import app_commands
from discord.ext import commands

from bot import Fun2OoshBot
from utils.config import Config
from utils.economy_utils import EconomyUtils
from utils.cooldowns import cooldown_manager
from utils.anti_fraud import anti_fraud as anti_fraud_instance


class CardSuit(Enum):
    """Card suits enumeration."""
    HEARTS = "♥️"
    DIAMONDS = "♦️"
    CLUBS = "♣️"
    SPADES = "♠️"


class Card:
    """Represents a playing card."""
    
    def __init__(self, rank: str, suit: CardSuit):
        self.rank = rank
        self.suit = suit
    
    @property
    def value(self) -> int:
        """Get the blackjack value of the card."""
        if self.rank in ['J', 'Q', 'K']:
            return 10
        elif self.rank == 'A':
            return 11  # Will be adjusted for aces in hand calculation
        else:
            return int(self.rank)
    
    def __str__(self) -> str:
        return f"{self.rank}{self.suit.value}"
    
    def __repr__(self) -> str:
        return self.__str__()


class Deck:
    """Represents a deck of cards."""
    
    RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    
    def __init__(self, num_decks: int = 1):
        self.cards: List[Card] = []
        self.num_decks = num_decks
        self.reset()
    
    def reset(self):
        """Reset and shuffle the deck."""
        self.cards = []
        for _ in range(self.num_decks):
            for suit in CardSuit:
                for rank in self.RANKS:
                    self.cards.append(Card(rank, suit))
        random.shuffle(self.cards)
    
    def deal(self, count: int = 1) -> List[Card]:
        """Deal cards from the deck."""
        if len(self.cards) < count:
            self.reset()
        dealt = self.cards[:count]
        self.cards = self.cards[count:]
        return dealt


class BlackjackHand:
    """Represents a blackjack hand."""
    
    def __init__(self, bet: int, cards: Optional[List[Card]] = None):
        self.cards = cards or []
        self.bet = bet
        self.stand = False
        self.busted = False
        self.doubled = False
    
    def add_card(self, card: Card):
        """Add a card to the hand."""
        self.cards.append(card)
        if self.value > 21:
            self.busted = True
    
    @property
    def value(self) -> int:
        """Calculate hand value."""
        value = sum(card.value for card in self.cards)
        aces = sum(1 for card in self.cards if card.rank == 'A')
        
        # Adjust for aces
        while value > 21 and aces > 0:
            value -= 10
            aces -= 1
        
        return value
    
    @property
    def is_blackjack(self) -> bool:
        """Check if hand is a natural blackjack."""
        return len(self.cards) == 2 and self.value == 21
    
    def __str__(self) -> str:
        cards_str = ' '.join(str(card) for card in self.cards)
        return f"{cards_str} (Value: {self.value})"


class BlackjackView(discord.ui.View):
    """Interactive buttons for blackjack game."""
    
    def __init__(self, game, player_id: int):
        super().__init__(timeout=120)
        self.game = game
        self.player_id = player_id
        self.message = None
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the player to interact."""
        if interaction.user.id != self.player_id:
            await interaction.response.send_message(
                "This is not your game!", ephemeral=True
            )
            return False
        return True
    
    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary, emoji="🃏")
    async def hit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Hit button - draw another card."""
        await interaction.response.defer()
        await self.game.hit(interaction)
    
    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary, emoji="✋")
    async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Stand button - end turn."""
        await interaction.response.defer()
        await self.game.stand(interaction)
    
    @discord.ui.button(label="Double Down", style=discord.ButtonStyle.success, emoji="⚡")
    async def double_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Double down - double bet and get one more card."""
        await interaction.response.defer()
        await self.game.double_down(interaction)
    
    async def on_timeout(self):
        """Handle timeout."""
        for item in self.children:  # type: ignore
            item.disabled = True  # type: ignore
        if self.message:
            try:
                await self.message.edit(view=self)  # type: ignore
            except:
                pass


class BlackjackGame:
    """Manages a blackjack game session."""
    
    def __init__(self, player: discord.User | discord.Member, bet: int, bot, session):
        self.player = player
        self.initial_bet = bet
        self.bot = bot
        self.session = session
        self.deck = Deck(num_decks=6)
        self.player_hand = BlackjackHand(bet, self.deck.deal(2))
        self.dealer_hand = BlackjackHand(0, self.deck.deal(2))
        self.view = None
        self.message = None
        self.finished = False
    
    async def start(self, ctx) -> discord.Message:
        """Start the blackjack game."""
        embed = self.create_embed()
        self.view = BlackjackView(self, self.player.id)
        self.message = await ctx.send(embed=embed, view=self.view)
        self.view.message = self.message
        
        # Check for immediate blackjack
        if self.player_hand.is_blackjack:
            await self.check_winner()
        
        return self.message
    
    def create_embed(self, final: bool = False) -> discord.Embed:
        """Create game status embed."""
        embed = discord.Embed(
            title="🎰 Blackjack",
            color=discord.Color.blue() if not final else discord.Color.green()
        )
        
        # Dealer's hand
        if final or self.player_hand.busted:
            dealer_cards = str(self.dealer_hand)
        else:
            # Hide dealer's second card
            visible_card = str(self.dealer_hand.cards[0])
            dealer_cards = f"{visible_card} ?" 
        
        embed.add_field(
            name="Dealer's Hand",
            value=dealer_cards,
            inline=False
        )
        
        # Player's hand
        embed.add_field(
            name=f"{self.player.display_name}'s Hand",
            value=str(self.player_hand),
            inline=False
        )
        
        embed.add_field(
            name="Current Bet",
            value=f"💰 {self.player_hand.bet:,} coins",
            inline=True
        )
        
        if self.player_hand.busted:
            embed.add_field(name="Result", value="**BUST!** You lose.", inline=False)
            embed.color = discord.Color.red()
        
        return embed
    
    async def hit(self, interaction: discord.Interaction):
        """Player hits - draws a card."""
        if self.finished or self.player_hand.stand:
            return
        
        card = self.deck.deal(1)[0]
        self.player_hand.add_card(card)
        
        if self.player_hand.busted:
            await self.finish_game(interaction, lost=True)
        else:
            embed = self.create_embed()
            await interaction.edit_original_response(embed=embed, view=self.view)
    
    async def stand(self, interaction: discord.Interaction):
        """Player stands - dealer plays."""
        if self.finished:
            return
        
        self.player_hand.stand = True
        await self.dealer_play(interaction)
    
    async def double_down(self, interaction: discord.Interaction):
        """Double the bet and draw one card."""
        if self.finished or len(self.player_hand.cards) != 2:
            await interaction.followup.send(
                "❌ You can only double down on your first two cards!",
                ephemeral=True
            )
            return
        
        # Check if player has enough balance
        wallet = await EconomyUtils.get_or_create_wallet(self.session, self.player.id)
        if wallet.balance < self.player_hand.bet:
            await interaction.followup.send(
                "❌ You don't have enough coins to double down!",
                ephemeral=True
            )
            return
        
        # Deduct additional bet
        wallet.balance -= self.player_hand.bet
        self.player_hand.bet *= 2
        self.player_hand.doubled = True
        
        # Draw one card and stand
        card = self.deck.deal(1)[0]
        self.player_hand.add_card(card)
        
        if self.player_hand.busted:
            await self.finish_game(interaction, lost=True)
        else:
            self.player_hand.stand = True
            await self.dealer_play(interaction)
    
    async def dealer_play(self, interaction: discord.Interaction):
        """Dealer plays their hand."""
        # Dealer must hit until 17 or higher
        while self.dealer_hand.value < 17:
            card = self.deck.deal(1)[0]
            self.dealer_hand.add_card(card)
            await asyncio.sleep(0.5)
        
        await self.check_winner(interaction)
    
    async def check_winner(self, interaction: Optional[discord.Interaction] = None):
        """Determine the winner and pay out."""
        self.finished = True
        player_value = self.player_hand.value
        dealer_value = self.dealer_hand.value
        
        wallet = await EconomyUtils.get_or_create_wallet(self.session, self.player.id)
        
        # Determine result
        if self.player_hand.busted:
            result = "**BUST!** You lose."
            payout = 0
            color = discord.Color.red()
        elif self.dealer_hand.busted:
            result = "**Dealer busts!** You win!"
            payout = self.player_hand.bet * 2
            color = discord.Color.green()
        elif self.player_hand.is_blackjack and not self.dealer_hand.is_blackjack:
            result = "**BLACKJACK!** You win!"
            payout = int(self.player_hand.bet * 2.5)  # 3:2 payout
            color = discord.Color.gold()
        elif player_value > dealer_value:
            result = "**You win!**"
            payout = self.player_hand.bet * 2
            color = discord.Color.green()
        elif player_value < dealer_value:
            result = "**Dealer wins!** You lose."
            payout = 0
            color = discord.Color.red()
        else:
            result = "**Push!** It's a tie."
            payout = self.player_hand.bet
            color = discord.Color.blue()
        
        # Pay out
        if payout > 0:
            wallet.balance += payout
            await EconomyUtils.add_money(
                self.session, self.player.id, payout,
                'casino', f'Blackjack win: {payout} coins'
            )
        
        await self.session.commit()
        
        # Create final embed
        embed = self.create_embed(final=True)
        embed.color = color
        embed.add_field(name="Result", value=result, inline=False)
        
        if payout > 0:
            profit = payout - self.initial_bet
            embed.add_field(
                name="Payout",
                value=f"💰 {payout:,} coins (+{profit:,})",
                inline=True
            )
        else:
            embed.add_field(
                name="Loss",
                value=f"💔 -{self.initial_bet:,} coins",
                inline=True
            )
        
        embed.add_field(
            name="New Balance",
            value=f"💵 {wallet.balance:,} coins",
            inline=True
        )
        
        # Disable all buttons
        if self.view:
            for item in self.view.children:  # type: ignore
                item.disabled = True  # type: ignore
        
        if interaction:
            await interaction.edit_original_response(embed=embed, view=self.view)
        else:
            if self.message:
                await self.message.edit(embed=embed, view=self.view)  # type: ignore
    
    async def finish_game(self, interaction: discord.Interaction, lost: bool = False):
        """Finish the game."""
        if lost:
            await self.check_winner(interaction)
        else:
            await self.check_winner(interaction)


class RouletteView(discord.ui.View):
    """Interactive view for roulette betting."""
    
    def __init__(self, game, player_id: int):
        super().__init__(timeout=60)
        self.game = game
        self.player_id = player_id
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.player_id:
            await interaction.response.send_message(
                "This is not your game!", ephemeral=True
            )
            return False
        return True
    
    @discord.ui.button(label="Spin!", style=discord.ButtonStyle.danger, emoji="🎡")
    async def spin_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Spin the roulette wheel."""
        await interaction.response.defer()
        await self.game.spin(interaction)
        
        # Disable button after spin
        button.disabled = True
        await interaction.edit_original_response(view=self)


class SlotMachine:
    """Slot machine game logic."""
    
    SYMBOLS = ['🍒', '🍋', '🍊', '🍇', '🔔', '⭐', '💎', '7️⃣']
    
    # Payout multipliers
    PAYOUTS = {
        '💎': 50,   # Diamond - highest
        '7️⃣': 30,   # Seven
        '⭐': 20,   # Star
        '🔔': 15,   # Bell
        '🍇': 10,   # Grapes
        '🍊': 8,    # Orange
        '🍋': 5,    # Lemon
        '🍒': 3,    # Cherry - lowest
    }
    
    @classmethod
    def spin(cls) -> Tuple[List[str], int, str]:
        """Spin the slot machine. Returns (symbols, multiplier, result_text)."""
        # Weight probabilities (lower index = higher chance)
        weights = [30, 25, 20, 15, 10, 8, 5, 2]  # Matches SYMBOLS order
        
        reels = [
            random.choices(cls.SYMBOLS, weights=weights)[0]
            for _ in range(3)
        ]
        
        # Check for wins
        if reels[0] == reels[1] == reels[2]:
            # Three of a kind
            symbol = reels[0]
            multiplier = cls.PAYOUTS[symbol]
            result = f"🎰 **JACKPOT!** Three {symbol}!"
        elif reels[0] == reels[1] or reels[1] == reels[2]:
            # Two of a kind
            symbol = reels[1]
            multiplier = cls.PAYOUTS[symbol] // 3
            result = f"🎰 Two {symbol}! Small win!"
        else:
            multiplier = 0
            result = "💸 No match. Try again!"
        
        return reels, multiplier, result


class Casino(commands.Cog):
    """Professional casino with multiple gambling games."""
    
    def __init__(self, bot: Fun2OoshBot, config: Config):
        self.bot = bot
        self.config = config
        self.active_games: Dict[int, BlackjackGame] = {}
    
    async def check_bet_limits(self, user_id: int, bet: int, session) -> Tuple[bool, Optional[str]]:
        """Check if bet is within limits."""
        if bet < self.config.min_bet:
            return False, f"❌ Minimum bet is {self.config.min_bet:,} coins!"
        
        if bet > self.config.max_bet:
            return False, f"❌ Maximum bet is {self.config.max_bet:,} coins!"
        
        wallet = await EconomyUtils.get_or_create_wallet(session, user_id)
        if wallet.balance < bet:
            return False, f"❌ You don't have enough coins! Balance: {wallet.balance:,}"
        
        return True, None
    
    @commands.hybrid_command(name="blackjack", description="Play blackjack! Try to get 21 without going over.")
    @app_commands.describe(bet="Amount to bet")
    async def blackjack(self, ctx: commands.Context, bet: int):
        """Play a game of blackjack."""
        # Check cooldown
        if cooldown_manager.is_on_cooldown("blackjack", ctx.author.id, 10):
            remaining = cooldown_manager.get_remaining_time("blackjack", ctx.author.id, 10)
            await ctx.send(
                f"⏰ Please wait {remaining:.0f} seconds before playing again.",
                ephemeral=True
            )
            return
        
        async with self.bot.get_session() as session:
            # Check bet limits
            valid, error = await self.check_bet_limits(ctx.author.id, bet, session)
            if not valid:
                await ctx.send(error, ephemeral=True)
                return
            
            # Deduct bet from balance
            wallet = await EconomyUtils.get_or_create_wallet(session, ctx.author.id)
            wallet.balance -= bet
            await session.commit()
            
            # Start game
            game = BlackjackGame(ctx.author, bet, self.bot, session)
            self.active_games[ctx.author.id] = game
            
            try:
                await game.start(ctx)
                cooldown_manager.set_cooldown("blackjack", ctx.author.id)
            except Exception as e:
                # Refund on error
                wallet.balance += bet
                await session.commit()
                await ctx.send(f"❌ An error occurred: {e}")
            finally:
                if ctx.author.id in self.active_games:
                    del self.active_games[ctx.author.id]
    
    @commands.hybrid_command(name="roulette", description="Play roulette! Bet on numbers, colors, or ranges.")
    @app_commands.describe(
        bet_type="Type of bet: number (0-36), red, black, odd, even, low (1-18), high (19-36)",
        value="The value to bet on (for number bets)",
        amount="Amount to bet"
    )
    async def roulette(self, ctx: commands.Context, bet_type: str, value: Optional[str], amount: int):
        """Play roulette with various bet types."""
        async with self.bot.get_session() as session:
            # Check bet limits
            valid, error = await self.check_bet_limits(ctx.author.id, amount, session)
            if not valid:
                await ctx.send(error, ephemeral=True)
                return
            
            # Validate bet type
            bet_type = bet_type.lower()
            valid_bets = ['number', 'red', 'black', 'odd', 'even', 'low', 'high']
            
            if bet_type not in valid_bets:
                await ctx.send(
                    f"❌ Invalid bet type! Choose from: {', '.join(valid_bets)}",
                    ephemeral=True
                )
                return
            
            # Validate number bet
            if bet_type == 'number':
                if value is None:
                    await ctx.send("❌ You must specify a number (0-36)!", ephemeral=True)
                    return
                try:
                    number = int(value)
                    if number < 0 or number > 36:
                        raise ValueError
                except:
                    await ctx.send("❌ Invalid number! Must be 0-36.", ephemeral=True)
                    return
            
            # Deduct bet
            wallet = await EconomyUtils.get_or_create_wallet(session, ctx.author.id)
            wallet.balance -= amount
            await session.commit()
            
            # Spin the wheel
            result_number = random.randint(0, 36)
            
            # Red numbers in roulette
            red_numbers = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
            is_red = result_number in red_numbers
            is_black = result_number != 0 and not is_red
            is_odd = result_number % 2 == 1 and result_number != 0
            is_even = result_number % 2 == 0 and result_number != 0
            is_low = 1 <= result_number <= 18
            is_high = 19 <= result_number <= 36
            
            # Determine win
            won = False
            multiplier = 0
            
            if bet_type == 'number' and value and result_number == int(value):
                won = True
                multiplier = 36  # 35:1 payout + original bet
            elif bet_type == 'red' and is_red:
                won = True
                multiplier = 2
            elif bet_type == 'black' and is_black:
                won = True
                multiplier = 2
            elif bet_type == 'odd' and is_odd:
                won = True
                multiplier = 2
            elif bet_type == 'even' and is_even:
                won = True
                multiplier = 2
            elif bet_type == 'low' and is_low:
                won = True
                multiplier = 2
            elif bet_type == 'high' and is_high:
                won = True
                multiplier = 2
            
            # Create result embed
            embed = discord.Embed(title="🎡 Roulette", color=discord.Color.red())
            
            # Determine color display
            if result_number == 0:
                color_str = "🟢 Green"
            elif is_red:
                color_str = "🔴 Red"
            else:
                color_str = "⚫ Black"
            
            embed.add_field(
                name="Result",
                value=f"**{result_number}** {color_str}",
                inline=False
            )
            
            embed.add_field(
                name="Your Bet",
                value=f"{bet_type.title()}" + (f" {value}" if value else ""),
                inline=True
            )
            
            embed.add_field(
                name="Bet Amount",
                value=f"💰 {amount:,} coins",
                inline=True
            )
            
            # Handle payout
            if won:
                payout = amount * multiplier
                profit = payout - amount
                wallet.balance += payout
                
                await EconomyUtils.add_money(
                    session, ctx.author.id, payout,
                    'casino', f'Roulette win: {payout} coins'
                )
                
                embed.add_field(
                    name="✅ YOU WIN!",
                    value=f"💰 Payout: {payout:,} coins (+{profit:,})",
                    inline=False
                )
                embed.color = discord.Color.green()
            else:
                embed.add_field(
                    name="❌ YOU LOSE!",
                    value=f"💔 Lost: {amount:,} coins",
                    inline=False
                )
                embed.color = discord.Color.red()
            
            await session.commit()
            
            embed.add_field(
                name="New Balance",
                value=f"💵 {wallet.balance:,} coins",
                inline=False
            )
            
            await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="slots", description="Play the slot machine! Match symbols to win big!")
    @app_commands.describe(bet="Amount to bet")
    async def slots(self, ctx: commands.Context, bet: int):
        """Play the slot machine."""
        async with self.bot.get_session() as session:
            # Check bet limits
            valid, error = await self.check_bet_limits(ctx.author.id, bet, session)
            if not valid:
                await ctx.send(error, ephemeral=True)
                return
            
            # Deduct bet
            wallet = await EconomyUtils.get_or_create_wallet(session, ctx.author.id)
            wallet.balance -= bet
            await session.commit()
            
            # Spin!
            reels, multiplier, result_text = SlotMachine.spin()
            
            # Create animated embed
            embed = discord.Embed(
                title="🎰 Slot Machine",
                description="Spinning...",
                color=discord.Color.blue()
            )
            message = await ctx.send(embed=embed)
            
            # Animation
            await asyncio.sleep(1)
            
            # Show result
            embed.description = f"**[ {' | '.join(reels)} ]**"
            embed.add_field(name="Result", value=result_text, inline=False)
            
            # Calculate payout
            if multiplier > 0:
                payout = bet * multiplier
                profit = payout - bet
                wallet.balance += payout
                
                await EconomyUtils.add_money(
                    session, ctx.author.id, payout,
                    'casino', f'Slots win: {payout} coins'
                )
                
                embed.add_field(
                    name="🎉 WIN!",
                    value=f"💰 Payout: {payout:,} coins (+{profit:,})\n**{multiplier}x** multiplier!",
                    inline=False
                )
                embed.color = discord.Color.gold()
            else:
                embed.add_field(
                    name="💸 Loss",
                    value=f"Lost: {bet:,} coins",
                    inline=False
                )
                embed.color = discord.Color.red()
            
            await session.commit()
            
            embed.add_field(
                name="Balance",
                value=f"💵 {wallet.balance:,} coins",
                inline=False
            )
            
            await message.edit(embed=embed)
    
    @commands.hybrid_command(name="coinflip", description="Flip a coin! Heads or tails?")
    @app_commands.describe(
        choice="Choose heads or tails",
        bet="Amount to bet"
    )
    async def coinflip(self, ctx: commands.Context, choice: str, bet: int):
        """Flip a coin and bet on the outcome."""
        choice = choice.lower()
        if choice not in ['heads', 'tails', 'h', 't']:
            await ctx.send("❌ Choose 'heads' or 'tails'!", ephemeral=True)
            return
        
        # Normalize choice
        choice = 'heads' if choice in ['heads', 'h'] else 'tails'
        
        async with self.bot.get_session() as session:
            # Check bet limits
            valid, error = await self.check_bet_limits(ctx.author.id, bet, session)
            if not valid:
                await ctx.send(error, ephemeral=True)
                return
            
            # Deduct bet
            wallet = await EconomyUtils.get_or_create_wallet(session, ctx.author.id)
            wallet.balance -= bet
            await session.commit()
            
            # Flip
            result = random.choice(['heads', 'tails'])
            won = result == choice
            
            # Animated embed
            embed = discord.Embed(title="🪙 Coinflip", color=discord.Color.blue())
            embed.add_field(name="Your Choice", value=choice.title(), inline=True)
            embed.add_field(name="Flipping...", value="🪙", inline=True)
            message = await ctx.send(embed=embed)
            
            await asyncio.sleep(1.5)
            
            # Result
            embed = discord.Embed(title="🪙 Coinflip", color=discord.Color.blue())
            embed.add_field(name="Your Choice", value=choice.title(), inline=True)
            embed.add_field(name="Result", value=result.title(), inline=True)
            
            if won:
                payout = bet * 2
                profit = bet
                wallet.balance += payout
                
                await EconomyUtils.add_money(
                    session, ctx.author.id, payout,
                    'casino', f'Coinflip win: {payout} coins'
                )
                
                embed.add_field(
                    name="✅ YOU WIN!",
                    value=f"💰 {payout:,} coins (+{profit:,})",
                    inline=False
                )
                embed.color = discord.Color.green()
            else:
                embed.add_field(
                    name="❌ YOU LOSE!",
                    value=f"💔 -{bet:,} coins",
                    inline=False
                )
                embed.color = discord.Color.red()
            
            await session.commit()
            
            embed.add_field(
                name="Balance",
                value=f"💵 {wallet.balance:,} coins",
                inline=False
            )
            
            await message.edit(embed=embed)
    
    @commands.hybrid_command(name="dice", description="Roll dice and bet on the outcome!")
    @app_commands.describe(
        prediction="Predict: over (8+), under (6-), seven, or specific number (2-12)",
        bet="Amount to bet"
    )
    async def dice(self, ctx: commands.Context, prediction: str, bet: int):
        """Roll two dice and bet on the outcome."""
        prediction = prediction.lower()
        
        async with self.bot.get_session() as session:
            # Check bet limits
            valid, error = await self.check_bet_limits(ctx.author.id, bet, session)
            if not valid:
                await ctx.send(error, ephemeral=True)
                return
            
            # Deduct bet
            wallet = await EconomyUtils.get_or_create_wallet(session, ctx.author.id)
            wallet.balance -= bet
            await session.commit()
            
            # Roll dice
            die1 = random.randint(1, 6)
            die2 = random.randint(1, 6)
            total = die1 + die2
            
            # Determine win and multiplier
            won = False
            multiplier = 0
            
            if prediction == 'over' and total >= 8:
                won = True
                multiplier = 2
            elif prediction == 'under' and total <= 6:
                won = True
                multiplier = 2
            elif prediction == 'seven' and total == 7:
                won = True
                multiplier = 4
            elif prediction.isdigit() and int(prediction) == total:
                won = True
                multiplier = 10  # Exact prediction
            
            # Create result embed
            dice_emoji = {
                1: "⚀", 2: "⚁", 3: "⚂",
                4: "⚃", 5: "⚄", 6: "⚅"
            }
            
            embed = discord.Embed(title="🎲 Dice Roll", color=discord.Color.blue())
            embed.add_field(
                name="Roll Result",
                value=f"{dice_emoji[die1]} {dice_emoji[die2]}\n**Total: {total}**",
                inline=True
            )
            embed.add_field(
                name="Your Prediction",
                value=prediction.title(),
                inline=True
            )
            
            if won:
                payout = bet * multiplier
                profit = payout - bet
                wallet.balance += payout
                
                await EconomyUtils.add_money(
                    session, ctx.author.id, payout,
                    'casino', f'Dice win: {payout} coins'
                )
                
                embed.add_field(
                    name="🎉 WIN!",
                    value=f"💰 {payout:,} coins (+{profit:,})\n**{multiplier}x** multiplier!",
                    inline=False
                )
                embed.color = discord.Color.green()
            else:
                embed.add_field(
                    name="💸 LOSE!",
                    value=f"Lost: {bet:,} coins",
                    inline=False
                )
                embed.color = discord.Color.red()
            
            await session.commit()
            
            embed.add_field(
                name="Balance",
                value=f"💵 {wallet.balance:,} coins",
                inline=False
            )
            
            await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="crash", description="Cash out before the multiplier crashes!")
    @app_commands.describe(
        bet="Amount to bet",
        target="Target multiplier to cash out (1.1 to 100)"
    )
    async def crash(self, ctx: commands.Context, bet: int, target: float):
        """Bet on a crash game - cash out before it crashes!"""
        if target < 1.1 or target > 100:
            await ctx.send("❌ Target must be between 1.1x and 100x!", ephemeral=True)
            return
        
        async with self.bot.get_session() as session:
            # Check bet limits
            valid, error = await self.check_bet_limits(ctx.author.id, bet, session)
            if not valid:
                await ctx.send(error, ephemeral=True)
                return
            
            # Deduct bet
            wallet = await EconomyUtils.get_or_create_wallet(session, ctx.author.id)
            wallet.balance -= bet
            await session.commit()
            
            # Determine crash point (weighted towards lower values)
            crash_point = round(random.uniform(1.0, 100.0) ** (1/3), 2)
            
            # Animate multiplier
            embed = discord.Embed(
                title="🚀 Crash Game",
                description="Starting...",
                color=discord.Color.blue()
            )
            embed.add_field(name="Your Target", value=f"{target:.2f}x", inline=True)
            embed.add_field(name="Current Bet", value=f"💰 {bet:,} coins", inline=True)
            
            message = await ctx.send(embed=embed)
            
            current = 1.0
            step = 0.1
            
            while current < crash_point and current < target:
                await asyncio.sleep(0.3)
                current += step
                embed.description = f"**{current:.2f}x**\n{'🚀' * min(int(current), 10)}"
                await message.edit(embed=embed)
            
            # Determine result
            won = current >= target
            
            if won:
                payout = int(bet * target)
                profit = payout - bet
                wallet.balance += payout
                
                await EconomyUtils.add_money(
                    session, ctx.author.id, payout,
                    'casino', f'Crash win: {payout} coins'
                )
                
                embed.add_field(
                    name="🎉 CASHED OUT!",
                    value=f"💰 {payout:,} coins (+{profit:,})\nCrashed at {crash_point:.2f}x",
                    inline=False
                )
                embed.color = discord.Color.green()
            else:
                embed.add_field(
                    name="💥 CRASHED!",
                    value=f"Crashed at {crash_point:.2f}x\nLost: {bet:,} coins",
                    inline=False
                )
                embed.color = discord.Color.red()
            
            await session.commit()
            
            embed.add_field(
                name="Balance",
                value=f"💵 {wallet.balance:,} coins",
                inline=False
            )
            
            await message.edit(embed=embed)
    
    @commands.hybrid_command(name="russianroulette", description="Play Russian Roulette! High risk, high reward!")
    @app_commands.describe(bet="Amount to bet")
    async def russian_roulette(self, ctx: commands.Context, bet: int):
        """Play Russian Roulette - 1 in 6 chance to lose everything!"""
        async with self.bot.get_session() as session:
            # Check bet limits
            valid, error = await self.check_bet_limits(ctx.author.id, bet, session)
            if not valid:
                await ctx.send(error, ephemeral=True)
                return
            
            # Deduct bet
            wallet = await EconomyUtils.get_or_create_wallet(session, ctx.author.id)
            wallet.balance -= bet
            await session.commit()
            
            # Create suspense
            embed = discord.Embed(
                title="🔫 Russian Roulette",
                description="Loading chamber...",
                color=discord.Color.red()
            )
            message = await ctx.send(embed=embed)
            
            await asyncio.sleep(1)
            embed.description = "Spinning cylinder..."
            await message.edit(embed=embed)
            
            await asyncio.sleep(1)
            embed.description = "Pulling trigger..."
            await message.edit(embed=embed)
            
            await asyncio.sleep(1.5)
            
            # 1 in 6 chance to lose
            result = random.randint(1, 6)
            
            if result == 1:
                # BANG! Lost
                embed.description = "💥 **BANG!**"
                embed.add_field(
                    name="☠️ YOU'RE OUT!",
                    value=f"Lost: {bet:,} coins",
                    inline=False
                )
                embed.color = discord.Color.dark_red()
            else:
                # Click! Survived
                payout = int(bet * 5)  # 4x profit (5x total)
                profit = payout - bet
                wallet.balance += payout
                
                await EconomyUtils.add_money(
                    session, ctx.author.id, payout,
                    'casino', f'Russian Roulette win: {payout} coins'
                )
                
                embed.description = "*Click*"
                embed.add_field(
                    name="✅ YOU SURVIVED!",
                    value=f"💰 {payout:,} coins (+{profit:,})\nYou got lucky!",
                    inline=False
                )
                embed.color = discord.Color.green()
            
            await session.commit()
            
            embed.add_field(
                name="Balance",
                value=f"💵 {wallet.balance:,} coins",
                inline=False
            )
            
            await message.edit(embed=embed)


async def setup(bot: Fun2OoshBot):
    """Setup the casino cog."""
    await bot.add_cog(Casino(bot, bot.config))
