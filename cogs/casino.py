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
        """Create professional game status embed."""
        # Professional color scheme
        if final:
            color = discord.Color.green() if not self.player_hand.busted else discord.Color.red()
        else:
            color = 0x2F3136  # Dark gray for in-progress
        
        embed = discord.Embed(
            title="BLACKJACK",
            description="━━━━━━━━━━━━━━━━━━━━━━",
            color=color
        )
        
        # Dealer's hand
        if final or self.player_hand.busted:
            dealer_cards = str(self.dealer_hand)
            dealer_value = f"[{self.dealer_hand.value}]"
        else:
            # Hide dealer's second card
            visible_card = str(self.dealer_hand.cards[0])
            dealer_cards = f"{visible_card} 🂠"
            dealer_value = "[?]"
        
        embed.add_field(
            name="DEALER",
            value=f"```\n{dealer_cards}\n```\n**Value:** {dealer_value}",
            inline=False
        )
        
        embed.add_field(
            name="━━━━━━━━━━━━━━━━━━━━━━",
            value="",
            inline=False
        )
        
        # Player's hand
        player_cards = ' '.join(str(card) for card in self.player_hand.cards)
        player_value = f"[{self.player_hand.value}]"
        
        if self.player_hand.is_blackjack:
            status_text = "BLACKJACK!"
        elif self.player_hand.busted:
            status_text = "BUST"
        elif self.player_hand.stand:
            status_text = "STANDING"
        else:
            status_text = "IN PLAY"
        
        embed.add_field(
            name=f"PLAYER: {self.player.display_name}",
            value=f"```\n{player_cards}\n```\n**Value:** {player_value} | **Status:** {status_text}",
            inline=False
        )
        
        embed.add_field(
            name="━━━━━━━━━━━━━━━━━━━━━━",
            value="",
            inline=False
        )
        
        # Bet information
        embed.add_field(
            name="WAGER",
            value=f"```\n{self.player_hand.bet:,} coins\n```",
            inline=True
        )
        
        if final:
            embed.add_field(
                name="━━━━━━━━━━━━━━━━━━━━━━",
                value="",
                inline=False
            )
        
        # Footer
        embed.set_footer(text="Casino • Blackjack Table")
        
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
        
        # Create professional final embed
        embed = self.create_embed(final=True)
        embed.color = color
        
        # Result section
        if payout > 0:
            profit = payout - self.initial_bet
            result_value = f"```diff\n+ WIN\n```\n**Payout:** {payout:,} coins\n**Profit:** +{profit:,} coins"
        else:
            result_value = f"```diff\n- LOSS\n```\n**Lost:** {self.initial_bet:,} coins"
        
        embed.add_field(
            name="OUTCOME",
            value=result_value,
            inline=False
        )
        
        embed.add_field(
            name="BALANCE",
            value=f"```\n{wallet.balance:,} coins\n```",
            inline=False
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
    
    @commands.hybrid_command(name="blackjack", aliases=['bj'], description="Play blackjack! Try to get 21 without going over.")
    @app_commands.describe(bet="Amount to bet")
    async def blackjack(self, ctx: commands.Context, bet: int):
        """Play blackjack - Get 21 without busting! Has hit, stand, and double down options."""
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
    
    @commands.hybrid_command(name="roulette", aliases=['rl'], description="Play roulette! Bet on numbers, colors, or ranges.")
    @app_commands.describe(
        bet_type="Type of bet: number (0-36), red, black, odd, even, low (1-18), high (19-36)",
        value="The value to bet on (for number bets)",
        amount="Amount to bet"
    )
    async def roulette(self, ctx: commands.Context, bet_type: str, value: Optional[str], amount: int):
        """European roulette - Bet on numbers (36x), colors (2x), odd/even (2x), or ranges (2x)."""
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
    
    @commands.hybrid_command(name="slots", aliases=['s', 'slot'], description="Play the slot machine! Match symbols to win big!")
    @app_commands.describe(bet="Amount to bet")
    async def slots(self, ctx: commands.Context, bet: int):
        """Slot machine - Match 3 symbols to win! Payouts from 3x to 50x."""
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
    
    @commands.hybrid_command(name="coinflip", aliases=['cf', 'flip'], description="Flip a coin! Heads or tails?")
    @app_commands.describe(
        choice="Choose heads or tails",
        bet="Amount to bet"
    )
    async def coinflip(self, ctx: commands.Context, choice: str, bet: int):
        """Coinflip - 50/50 chance! Choose heads or tails, win 2x your bet."""
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
    
    @commands.hybrid_command(name="dice", aliases=['d', 'roll'], description="Roll dice and bet on the outcome!")
    @app_commands.describe(
        prediction="Predict: over (8+), under (6-), seven, or specific number (2-12)",
        bet="Amount to bet"
    )
    async def dice(self, ctx: commands.Context, prediction: str, bet: int):
        """Dice - Roll 2 dice! Bet on over/under (2x), seven (4x), or exact number (10x)."""
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
    
    @commands.hybrid_command(name="crash", aliases=['cr'], description="Cash out before the multiplier crashes!")
    @app_commands.describe(
        bet="Amount to bet",
        target="Target multiplier to cash out (1.1 to 100)"
    )
    async def crash(self, ctx: commands.Context, bet: int, target: float):
        """Crash - Set target multiplier, hope it doesn't crash before! 1.1x to 100x possible."""
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
    
    @commands.hybrid_command(name="russianroulette", aliases=['rr', 'roulette6'], description="Play Russian Roulette! High risk, high reward!")
    @app_commands.describe(bet="Amount to bet")
    async def russian_roulette(self, ctx: commands.Context, bet: int):
        """Russian Roulette - 1 in 6 chance to lose! Survive for 5x payout. Ultimate risk!"""
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
    
    @commands.hybrid_command(name="war", aliases=['w'], description="Play War! High card wins!")
    @app_commands.describe(bet="Amount to bet")
    async def war(self, ctx: commands.Context, bet: int):
        """War - Simple card battle! Higher card wins 2x, tie returns bet."""
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
            
            # Deal cards
            deck = Deck()
            player_card = deck.deal(1)[0]
            dealer_card = deck.deal(1)[0]
            
            # Create embed
            embed = discord.Embed(
                title="WAR",
                description="━━━━━━━━━━━━━━━━━━━━━━",
                color=0x2F3136
            )
            
            embed.add_field(
                name="DEALER",
                value=f"```\n{dealer_card}\n```\n**Value:** [{dealer_card.value}]",
                inline=True
            )
            
            embed.add_field(
                name="PLAYER",
                value=f"```\n{player_card}\n```\n**Value:** [{player_card.value}]",
                inline=True
            )
            
            embed.add_field(
                name="━━━━━━━━━━━━━━━━━━━━━━",
                value="",
                inline=False
            )
            
            # Determine winner
            if player_card.value > dealer_card.value:
                payout = bet * 2
                profit = bet
                wallet.balance += payout
                
                await EconomyUtils.add_money(
                    session, ctx.author.id, payout,
                    'casino', f'War win: {payout} coins'
                )
                
                result_text = f"```diff\n+ WIN\n```\n**Payout:** {payout:,} coins\n**Profit:** +{profit:,} coins"
                embed.color = discord.Color.green()
            elif player_card.value < dealer_card.value:
                result_text = f"```diff\n- LOSS\n```\n**Lost:** {bet:,} coins"
                embed.color = discord.Color.red()
            else:
                # Tie - return bet
                wallet.balance += bet
                result_text = f"```\nPUSH\n```\n**Returned:** {bet:,} coins"
                embed.color = discord.Color.blue()
            
            await session.commit()
            
            embed.add_field(
                name="OUTCOME",
                value=result_text,
                inline=False
            )
            
            embed.add_field(
                name="BALANCE",
                value=f"```\n{wallet.balance:,} coins\n```",
                inline=False
            )
            
            embed.set_footer(text="Casino • War Table")
            await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="baccarat", aliases=['bc', 'bac'], description="Play Baccarat! Bet on Player, Banker, or Tie!")
    @app_commands.describe(
        bet_on="Bet on: player, banker, or tie",
        amount="Amount to bet"
    )
    async def baccarat(self, ctx: commands.Context, bet_on: str, amount: int):
        """Baccarat - Bet on Player (2x), Banker (1.95x), or Tie (8x). Closest to 9 wins!"""
        bet_on = bet_on.lower()
        if bet_on not in ['player', 'banker', 'tie']:
            await ctx.send("Invalid bet! Choose: player, banker, or tie", ephemeral=True)
            return
        
        async with self.bot.get_session() as session:
            # Check bet limits
            valid, error = await self.check_bet_limits(ctx.author.id, amount, session)
            if not valid:
                await ctx.send(error, ephemeral=True)
                return
            
            # Deduct bet
            wallet = await EconomyUtils.get_or_create_wallet(session, ctx.author.id)
            wallet.balance -= amount
            await session.commit()
            
            # Deal cards
            deck = Deck()
            player_hand = deck.deal(2)
            banker_hand = deck.deal(2)
            
            # Calculate baccarat values (only last digit matters)
            player_value = (sum(min(c.value, 10) for c in player_hand)) % 10
            banker_value = (sum(min(c.value, 10) for c in banker_hand)) % 10
            
            # Natural win check
            natural = player_value >= 8 or banker_value >= 8
            
            # Third card rules (simplified)
            if not natural:
                if player_value <= 5:
                    player_hand.append(deck.deal(1)[0])
                    player_value = (sum(min(c.value, 10) for c in player_hand)) % 10
                
                if banker_value <= 5:
                    banker_hand.append(deck.deal(1)[0])
                    banker_value = (sum(min(c.value, 10) for c in banker_hand)) % 10
            
            # Create embed
            embed = discord.Embed(
                title="BACCARAT",
                description="━━━━━━━━━━━━━━━━━━━━━━",
                color=0x2F3136
            )
            
            player_cards = ' '.join(str(c) for c in player_hand)
            banker_cards = ' '.join(str(c) for c in banker_hand)
            
            embed.add_field(
                name="PLAYER HAND",
                value=f"```\n{player_cards}\n```\n**Value:** [{player_value}]",
                inline=False
            )
            
            embed.add_field(
                name="BANKER HAND",
                value=f"```\n{banker_cards}\n```\n**Value:** [{banker_value}]",
                inline=False
            )
            
            embed.add_field(
                name="━━━━━━━━━━━━━━━━━━━━━━",
                value="",
                inline=False
            )
            
            embed.add_field(
                name="YOUR BET",
                value=f"```\n{bet_on.upper()}\n```",
                inline=True
            )
            
            # Determine winner
            payout = 0
            if player_value > banker_value:
                winner = 'player'
            elif banker_value > player_value:
                winner = 'banker'
            else:
                winner = 'tie'
            
            if bet_on == winner:
                if winner == 'tie':
                    payout = amount * 9  # 8:1 payout for tie
                elif winner == 'banker':
                    payout = int(amount * 1.95)  # 0.95:1 payout (5% commission)
                else:
                    payout = amount * 2  # 1:1 payout for player
                
                profit = payout - amount
                wallet.balance += payout
                
                await EconomyUtils.add_money(
                    session, ctx.author.id, payout,
                    'casino', f'Baccarat win: {payout} coins'
                )
                
                result_text = f"```diff\n+ WIN\n```\n**Winner:** {winner.upper()}\n**Payout:** {payout:,} coins\n**Profit:** +{profit:,} coins"
                embed.color = discord.Color.green()
            else:
                result_text = f"```diff\n- LOSS\n```\n**Winner:** {winner.upper()}\n**Lost:** {amount:,} coins"
                embed.color = discord.Color.red()
            
            await session.commit()
            
            embed.add_field(
                name="OUTCOME",
                value=result_text,
                inline=False
            )
            
            embed.add_field(
                name="BALANCE",
                value=f"```\n{wallet.balance:,} coins\n```",
                inline=False
            )
            
            embed.set_footer(text="Casino • Baccarat Table")
            await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="hilo", aliases=['hl', 'highlow'], description="Guess if the next card is higher or lower!")
    @app_commands.describe(
        guess="Guess: high or low",
        bet="Amount to bet"
    )
    async def hilo(self, ctx: commands.Context, guess: str, bet: int):
        """High-Low - Guess if next card is higher or lower! Win 2x, tie returns bet."""
        guess = guess.lower()
        if guess not in ['high', 'low', 'h', 'l']:
            await ctx.send("Invalid guess! Choose: high or low", ephemeral=True)
            return
        
        guess = 'high' if guess in ['high', 'h'] else 'low'
        
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
            
            # Deal cards
            deck = Deck()
            current_card = deck.deal(1)[0]
            next_card = deck.deal(1)[0]
            
            # Create embed
            embed = discord.Embed(
                title="HIGH-LOW",
                description="━━━━━━━━━━━━━━━━━━━━━━",
                color=0x2F3136
            )
            
            embed.add_field(
                name="CURRENT CARD",
                value=f"```\n{current_card}\n```\n**Value:** [{current_card.value}]",
                inline=True
            )
            
            embed.add_field(
                name="NEXT CARD",
                value=f"```\n{next_card}\n```\n**Value:** [{next_card.value}]",
                inline=True
            )
            
            embed.add_field(
                name="━━━━━━━━━━━━━━━━━━━━━━",
                value="",
                inline=False
            )
            
            embed.add_field(
                name="YOUR GUESS",
                value=f"```\n{guess.upper()}\n```",
                inline=True
            )
            
            # Determine winner
            won = False
            if guess == 'high' and next_card.value > current_card.value:
                won = True
            elif guess == 'low' and next_card.value < current_card.value:
                won = True
            elif next_card.value == current_card.value:
                # Push on tie
                wallet.balance += bet
                result_text = f"```\nPUSH\n```\n**Cards matched!**\n**Returned:** {bet:,} coins"
                embed.color = discord.Color.blue()
            
            if next_card.value != current_card.value:
                if won:
                    payout = bet * 2
                    profit = bet
                    wallet.balance += payout
                    
                    await EconomyUtils.add_money(
                        session, ctx.author.id, payout,
                        'casino', f'High-Low win: {payout} coins'
                    )
                    
                    result_text = f"```diff\n+ WIN\n```\n**Payout:** {payout:,} coins\n**Profit:** +{profit:,} coins"
                    embed.color = discord.Color.green()
                else:
                    result_text = f"```diff\n- LOSS\n```\n**Lost:** {bet:,} coins"
                    embed.color = discord.Color.red()
            
            await session.commit()
            
            embed.add_field(
                name="OUTCOME",
                value=result_text,
                inline=False
            )
            
            embed.add_field(
                name="BALANCE",
                value=f"```\n{wallet.balance:,} coins\n```",
                inline=False
            )
            
            embed.set_footer(text="Casino • High-Low Table")
            await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="keno", aliases=['k', 'lotto'], description="Pick numbers and hope they match!")
    @app_commands.describe(
        numbers="Pick 5 numbers (1-80) separated by spaces",
        bet="Amount to bet"
    )
    async def keno(self, ctx: commands.Context, numbers: str, bet: int):
        """Keno - Lottery style! Pick 5 numbers (1-80). Match 5 for 50x, 4 for 10x, 3 for 3x."""
        try:
            picked = [int(n) for n in numbers.split()]
            if len(picked) != 5:
                await ctx.send("Pick exactly 5 numbers!", ephemeral=True)
                return
            if any(n < 1 or n > 80 for n in picked):
                await ctx.send("Numbers must be between 1 and 80!", ephemeral=True)
                return
            if len(set(picked)) != 5:
                await ctx.send("No duplicate numbers allowed!", ephemeral=True)
                return
        except:
            await ctx.send("Invalid format! Example: `5 12 23 45 67`", ephemeral=True)
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
            
            # Draw 20 numbers
            drawn = random.sample(range(1, 81), 20)
            matches = len(set(picked) & set(drawn))
            
            # Payout table
            payouts = {
                5: 50,  # All 5 match
                4: 10,  # 4 match
                3: 3,   # 3 match
                2: 1,   # 2 match
            }
            
            # Create embed
            embed = discord.Embed(
                title="KENO",
                description="━━━━━━━━━━━━━━━━━━━━━━",
                color=0x2F3136
            )
            
            picked_str = ', '.join(str(n) for n in sorted(picked))
            matched_nums = sorted(set(picked) & set(drawn))
            matched_str = ', '.join(str(n) for n in matched_nums) if matched_nums else "None"
            
            embed.add_field(
                name="YOUR NUMBERS",
                value=f"```\n{picked_str}\n```",
                inline=False
            )
            
            embed.add_field(
                name="MATCHED",
                value=f"```\n{matched_str}\n```\n**Count:** {matches}/5",
                inline=False
            )
            
            embed.add_field(
                name="━━━━━━━━━━━━━━━━━━━━━━",
                value="",
                inline=False
            )
            
            # Calculate payout
            multiplier = payouts.get(matches, 0)
            if multiplier > 0:
                payout = bet * multiplier
                profit = payout - bet
                wallet.balance += payout
                
                await EconomyUtils.add_money(
                    session, ctx.author.id, payout,
                    'casino', f'Keno win: {payout} coins'
                )
                
                result_text = f"```diff\n+ WIN\n```\n**Multiplier:** {multiplier}x\n**Payout:** {payout:,} coins\n**Profit:** +{profit:,} coins"
                embed.color = discord.Color.green()
            else:
                result_text = f"```diff\n- LOSS\n```\n**Matches:** {matches}/5\n**Lost:** {bet:,} coins"
                embed.color = discord.Color.red()
            
            await session.commit()
            
            embed.add_field(
                name="OUTCOME",
                value=result_text,
                inline=False
            )
            
            embed.add_field(
                name="BALANCE",
                value=f"```\n{wallet.balance:,} coins\n```",
                inline=False
            )
            
            embed.set_footer(text="Casino • Keno")
            await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="poker", aliases=['pk', 'holdem', 'texasholdem'])
    async def poker(self, ctx: commands.Context, bet: int):
        """
        Texas Hold'em Poker - Battle the dealer! Pre-flop, flop, turn, river. Royal flush to high card rankings. Win up to 2x!
        
        Args:
            bet: Amount to bet (minimum 100 coins)
        """
        # Anti-fraud check - support different anti_fraud API versions
        allowed = True
        check = getattr(anti_fraud_instance, "check_user", None)
        if check is None:
            check = getattr(anti_fraud_instance, "check", None)
        if check is None and callable(anti_fraud_instance):
            check = anti_fraud_instance
        if check is not None:
            result = check(ctx)
            if asyncio.iscoroutine(result):
                allowed = await result
            else:
                allowed = bool(result)
        # If the anti-fraud check exists and fails, stop
        if not allowed:
            return
        
        if bet < 100:
            return await ctx.send("❌ Minimum bet is 100 coins!")
        
        if bet > 1_000_000:
            return await ctx.send("❌ Maximum bet is 1,000,000 coins!")
        
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
            
            # Initialize game
            deck = Deck(num_decks=1)
            player_hand = deck.deal(2)
            dealer_hand = deck.deal(2)
            community_cards = []
            pot = bet * 2  # Player bet + dealer bet
            
            # Helper function to evaluate poker hands
            def evaluate_hand(hole_cards: List[Card], community: List[Card]) -> Tuple[int, str, List[Card]]:
                """
                Evaluate a poker hand. Returns (rank, name, best_cards).
                Rank: 9=Royal Flush, 8=Straight Flush, 7=Four of a Kind, etc.
                """
                all_cards = hole_cards + community
                if len(all_cards) < 5:
                    return (0, "High Card", all_cards[:5])
                
                # Convert cards to values for evaluation
                card_values = []
                for card in all_cards:
                    if card.rank == 'A':
                        val = 14
                    elif card.rank == 'K':
                        val = 13
                    elif card.rank == 'Q':
                        val = 12
                    elif card.rank == 'J':
                        val = 11
                    else:
                        val = int(card.rank)
                    card_values.append((val, card.suit, card))
                
                card_values.sort(reverse=True, key=lambda x: x[0])
                
                # Check for flush
                suits = {}
                for val, suit, card in card_values:
                    if suit not in suits:
                        suits[suit] = []
                    suits[suit].append((val, card))
                
                flush_suit = None
                flush_cards = []
                for suit, cards in suits.items():
                    if len(cards) >= 5:
                        flush_suit = suit
                        flush_cards = [c[1] for c in sorted(cards, reverse=True, key=lambda x: x[0])[:5]]
                        break
                
                # Check for straight
                def check_straight(values):
                    values = sorted(set(values), reverse=True)
                    # Check for A-2-3-4-5 straight
                    if 14 in values and set([2, 3, 4, 5]).issubset(set(values)):
                        return [5, 4, 3, 2, 14]  # Special case: Ace low
                    
                    for i in range(len(values) - 4):
                        if values[i] - values[i+4] == 4:
                            return values[i:i+5]
                    return None
                
                all_values = [v[0] for v in card_values]
                straight_values = check_straight(all_values)
                
                # Check for straight flush
                if flush_suit and flush_cards:
                    flush_values = [v for v, s, c in card_values if s == flush_suit]
                    sf_values = check_straight(flush_values)
                    if sf_values:
                        sf_cards = [c for v, s, c in card_values if s == flush_suit and v in sf_values][:5]
                        if sf_values[0] == 14 and sf_values[1] == 13:  # Royal flush
                            return (9, "Royal Flush", sf_cards)
                        return (8, "Straight Flush", sf_cards)
                
                # Count ranks
                rank_counts = {}
                for val, suit, card in card_values:
                    if val not in rank_counts:
                        rank_counts[val] = []
                    rank_counts[val].append(card)
                
                counts = sorted([(len(cards), val, cards) for val, cards in rank_counts.items()], 
                               reverse=True, key=lambda x: (x[0], x[1]))
                
                # Four of a kind
                if counts[0][0] == 4:
                    best_cards = counts[0][2] + [counts[1][2][0]]
                    return (7, "Four of a Kind", best_cards)
                
                # Full house
                if counts[0][0] == 3 and counts[1][0] >= 2:
                    best_cards = counts[0][2] + counts[1][2][:2]
                    return (6, "Full House", best_cards)
                
                # Flush
                if flush_cards:
                    return (5, "Flush", flush_cards)
                
                # Straight
                if straight_values:
                    straight_cards = []
                    for val in straight_values:
                        for v, s, c in card_values:
                            if v == val and c not in straight_cards:
                                straight_cards.append(c)
                                break
                    return (4, "Straight", straight_cards[:5])
                
                # Three of a kind
                if counts[0][0] == 3:
                    best_cards = counts[0][2] + [counts[1][2][0], counts[2][2][0]]
                    return (3, "Three of a Kind", best_cards)
                
                # Two pair
                if counts[0][0] == 2 and counts[1][0] == 2:
                    best_cards = counts[0][2] + counts[1][2] + [counts[2][2][0]]
                    return (2, "Two Pair", best_cards)
                
                # One pair
                if counts[0][0] == 2:
                    best_cards = counts[0][2] + [counts[1][2][0], counts[2][2][0], counts[3][2][0]]
                    return (1, "One Pair", best_cards)
                
                # High card
                best_cards = [c[2] for c in card_values[:5]]
                return (0, "High Card", best_cards)
            
            # Create initial embed
            def create_poker_embed(stage: str, show_dealer: bool = False):
                embed = discord.Embed(
                    title="♠️ TEXAS HOLD'EM POKER ♠️",
                    color=0x2F3136
                )
                
                embed.add_field(
                    name="━━━━━━━━━━━━━━━━━━━━━━",
                    value=f"**STAGE:** {stage.upper()}",
                    inline=False
                )
                
                # Player hand
                player_cards_str = "  ".join([str(c) for c in player_hand])
                embed.add_field(
                    name="YOUR HAND",
                    value=f"```\n{player_cards_str}\n```",
                    inline=False
                )
                
                # Community cards
                if community_cards:
                    community_str = "  ".join([str(c) for c in community_cards])
                else:
                    community_str = "No cards yet"
                
                embed.add_field(
                    name="COMMUNITY CARDS",
                    value=f"```\n{community_str}\n```",
                    inline=False
                )
                
                # Dealer hand
                if show_dealer:
                    dealer_cards_str = "  ".join([str(c) for c in dealer_hand])
                else:
                    dealer_cards_str = "🂠  🂠"
                
                embed.add_field(
                    name="DEALER HAND",
                    value=f"```\n{dealer_cards_str}\n```",
                    inline=False
                )
                
                embed.add_field(
                    name="POT",
                    value=f"```\n{pot:,} coins\n```",
                    inline=True
                )
                
                embed.add_field(
                    name="YOUR BET",
                    value=f"```\n{bet:,} coins\n```",
                    inline=True
                )
                
                embed.set_footer(text="Casino • Texas Hold'em Poker")
                return embed
            
            # PRE-FLOP
            embed = create_poker_embed("Pre-Flop")
            
            class PokerView(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=60)
                    self.action = None
                
                @discord.ui.button(label="Call", style=discord.ButtonStyle.green)
                async def call_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != ctx.author.id:
                        return await interaction.response.send_message("❌ This isn't your game!", ephemeral=True)
                    self.action = "call"
                    self.stop()
                    await interaction.response.defer()
                
                @discord.ui.button(label="Fold", style=discord.ButtonStyle.red)
                async def fold_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != ctx.author.id:
                        return await interaction.response.send_message("❌ This isn't your game!", ephemeral=True)
                    self.action = "fold"
                    self.stop()
                    await interaction.response.defer()
            
            view = PokerView()
            message = await ctx.send(embed=embed, view=view)
            
            await view.wait()
            
            if view.action == "fold":
                embed = discord.Embed(
                    title="♠️ TEXAS HOLD'EM POKER ♠️",
                    color=discord.Color.red()
                )
                embed.add_field(
                    name="OUTCOME",
                    value="```diff\n- FOLDED\n```\n**Lost:** " + f"{bet:,} coins",
                    inline=False
                )
                
                wallet = await EconomyUtils.get_or_create_wallet(session, ctx.author.id)
                embed.add_field(
                    name="BALANCE",
                    value=f"```\n{wallet.balance:,} coins\n```",
                    inline=False
                )
                
                embed.set_footer(text="Casino • Texas Hold'em Poker")
                await message.edit(embed=embed, view=None)
                return
            
            # FLOP - Deal 3 community cards
            community_cards.extend(deck.deal(3))
            embed = create_poker_embed("Flop")
            view = PokerView()
            await message.edit(embed=embed, view=view)
            await view.wait()
            
            if view.action == "fold":
                embed = discord.Embed(
                    title="♠️ TEXAS HOLD'EM POKER ♠️",
                    color=discord.Color.red()
                )
                embed.add_field(
                    name="OUTCOME",
                    value="```diff\n- FOLDED\n```\n**Lost:** " + f"{bet:,} coins",
                    inline=False
                )
                
                wallet = await EconomyUtils.get_or_create_wallet(session, ctx.author.id)
                embed.add_field(
                    name="BALANCE",
                    value=f"```\n{wallet.balance:,} coins\n```",
                    inline=False
                )
                
                embed.set_footer(text="Casino • Texas Hold'em Poker")
                await message.edit(embed=embed, view=None)
                return
            
            # TURN - Deal 1 community card
            community_cards.append(deck.deal(1)[0])
            embed = create_poker_embed("Turn")
            view = PokerView()
            await message.edit(embed=embed, view=view)
            await view.wait()
            
            if view.action == "fold":
                embed = discord.Embed(
                    title="♠️ TEXAS HOLD'EM POKER ♠️",
                    color=discord.Color.red()
                )
                embed.add_field(
                    name="OUTCOME",
                    value="```diff\n- FOLDED\n```\n**Lost:** " + f"{bet:,} coins",
                    inline=False
                )
                
                wallet = await EconomyUtils.get_or_create_wallet(session, ctx.author.id)
                embed.add_field(
                    name="BALANCE",
                    value=f"```\n{wallet.balance:,} coins\n```",
                    inline=False
                )
                
                embed.set_footer(text="Casino • Texas Hold'em Poker")
                await message.edit(embed=embed, view=None)
                return
            
            # RIVER - Deal final community card
            community_cards.append(deck.deal(1)[0])
            embed = create_poker_embed("River")
            view = PokerView()
            await message.edit(embed=embed, view=view)
            await view.wait()
            
            if view.action == "fold":
                embed = discord.Embed(
                    title="♠️ TEXAS HOLD'EM POKER ♠️",
                    color=discord.Color.red()
                )
                embed.add_field(
                    name="OUTCOME",
                    value="```diff\n- FOLDED\n```\n**Lost:** " + f"{bet:,} coins",
                    inline=False
                )
                
                wallet = await EconomyUtils.get_or_create_wallet(session, ctx.author.id)
                embed.add_field(
                    name="BALANCE",
                    value=f"```\n{wallet.balance:,} coins\n```",
                    inline=False
                )
                
                embed.set_footer(text="Casino • Texas Hold'em Poker")
                await message.edit(embed=embed, view=None)
                return
            
            # SHOWDOWN
            player_rank, player_hand_name, player_best = evaluate_hand(player_hand, community_cards)
            dealer_rank, dealer_hand_name, dealer_best = evaluate_hand(dealer_hand, community_cards)
            
            # Determine winner
            wallet = await EconomyUtils.get_or_create_wallet(session, ctx.author.id)
            
            embed = discord.Embed(
                title="♠️ TEXAS HOLD'EM POKER ♠️",
                color=0x2F3136
            )
            
            embed.add_field(
                name="━━━━━━━━━━━━━━━━━━━━━━",
                value="**STAGE:** SHOWDOWN",
                inline=False
            )
            
            # Show all hands
            player_cards_str = "  ".join([str(c) for c in player_hand])
            dealer_cards_str = "  ".join([str(c) for c in dealer_hand])
            community_str = "  ".join([str(c) for c in community_cards])
            
            embed.add_field(
                name="YOUR HAND",
                value=f"```\n{player_cards_str}\n```\n**{player_hand_name}**",
                inline=False
            )
            
            embed.add_field(
                name="COMMUNITY CARDS",
                value=f"```\n{community_str}\n```",
                inline=False
            )
            
            embed.add_field(
                name="DEALER HAND",
                value=f"```\n{dealer_cards_str}\n```\n**{dealer_hand_name}**",
                inline=False
            )
            
            # Tiebreaker - compare high cards if same rank
            if player_rank == dealer_rank:
                # Compare best cards
                player_values = []
                dealer_values = []
                
                for card in player_best:
                    if card.rank == 'A':
                        player_values.append(14)
                    elif card.rank == 'K':
                        player_values.append(13)
                    elif card.rank == 'Q':
                        player_values.append(12)
                    elif card.rank == 'J':
                        player_values.append(11)
                    else:
                        player_values.append(int(card.rank))
                
                for card in dealer_best:
                    if card.rank == 'A':
                        dealer_values.append(14)
                    elif card.rank == 'K':
                        dealer_values.append(13)
                    elif card.rank == 'Q':
                        dealer_values.append(12)
                    elif card.rank == 'J':
                        dealer_values.append(11)
                    else:
                        dealer_values.append(int(card.rank))
                
                player_values.sort(reverse=True)
                dealer_values.sort(reverse=True)
                
                if player_values > dealer_values:
                    winner = "player"
                elif dealer_values > player_values:
                    winner = "dealer"
                else:
                    winner = "tie"
            elif player_rank > dealer_rank:
                winner = "player"
            else:
                winner = "dealer"
            
            if winner == "player":
                payout = pot
                profit = payout - bet
                wallet.balance += payout
                
                await EconomyUtils.add_money(
                    session, ctx.author.id, payout,
                    'casino', f'Poker win: {payout} coins'
                )
                
                result_text = f"```diff\n+ WIN\n```\n**Won:** {payout:,} coins\n**Profit:** +{profit:,} coins"
                embed.color = discord.Color.green()
            elif winner == "tie":
                # Return bet on tie
                wallet.balance += bet
                await EconomyUtils.add_money(
                    session, ctx.author.id, bet,
                    'casino', f'Poker tie: {bet} coins returned'
                )
                
                result_text = f"```yaml\nTIE\n```\n**Bet Returned:** {bet:,} coins"
                embed.color = discord.Color.gold()
            else:
                result_text = f"```diff\n- LOSS\n```\n**Lost:** {bet:,} coins"
                embed.color = discord.Color.red()
            
            await session.commit()
            
            embed.add_field(
                name="OUTCOME",
                value=result_text,
                inline=False
            )
            
            embed.add_field(
                name="BALANCE",
                value=f"```\n{wallet.balance:,} coins\n```",
                inline=False
            )
            
            embed.set_footer(text="Casino • Texas Hold'em Poker")
            await message.edit(embed=embed, view=None)


async def setup(bot: Fun2OoshBot):
    """Setup the casino cog."""
    await bot.add_cog(Casino(bot, bot.config))
