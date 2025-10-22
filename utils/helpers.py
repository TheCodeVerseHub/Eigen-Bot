"""
Helper utilities for the bot.
"""

import random
from typing import Any, List, Optional

import discord
from discord import Embed

from utils.config import Config


class EmbedBuilder:
    """Helper class for building Discord embeds."""

    @staticmethod
    def success_embed(title: str, description: str = "") -> Embed:
        """Create a success embed."""
        embed = Embed(title=title, description=description, color=discord.Color.green())
        return embed

    @staticmethod
    def error_embed(title: str, description: str = "") -> Embed:
        """Create an error embed."""
        embed = Embed(title=title, description=description, color=discord.Color.red())
        return embed

    @staticmethod
    def info_embed(title: str, description: str = "") -> Embed:
        """Create an info embed."""
        embed = Embed(title=title, description=description, color=discord.Color.blue())
        return embed

    @staticmethod
    def wallet_embed(user: discord.User | discord.Member, balance: int, bank: int) -> Embed:
        """Create a wallet display embed."""
        # Handle None values
        if balance is None:
            balance = 0
        if bank is None:
            bank = 0
            
        embed = Embed(title=f"{user.display_name}'s Wallet", color=discord.Color.gold())
        embed.add_field(name="💰 Wallet", value=f"{balance:,} coins", inline=True)
        embed.add_field(name="🏦 Bank", value=f"{bank:,} coins", inline=True)
        embed.add_field(name="💵 Total", value=f"{balance + bank:,} coins", inline=True)
        embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
        return embed

    @staticmethod
    def leaderboard_embed(leaderboard: List[tuple], title: str = "Leaderboard") -> Embed:
        """Create a leaderboard embed."""
        embed = Embed(title=title, color=discord.Color.purple())
        description = ""
        for i, (user_id, total) in enumerate(leaderboard[:10], 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
            description += f"{medal} <@{user_id}> - {total:,} coins\n"
        embed.description = description
        return embed


class RNG:
    """Random number generator utilities."""

    @staticmethod
    def fair_roll(min_val: int, max_val: int) -> int:
        """Generate a fair random number."""
        return random.randint(min_val, max_val)

    @staticmethod
    def weighted_choice(choices: List[tuple]) -> Any:
        """Choose from weighted options. choices = [(item, weight), ...]"""
        total = sum(weight for _, weight in choices)
        r = random.uniform(0, total)
        cumulative = 0
        for item, weight in choices:
            cumulative += weight
            if r <= cumulative:
                return item
        return choices[-1][0]  # Fallback


def format_coins(amount: int) -> str:
    """Format coin amount with commas."""
    if amount is None:
        amount = 0
    return f"{amount:,} coins"


def responsible_gaming_notice() -> str:
    """Return responsible gaming notice."""
    return (
        "🎲 **Responsible Gaming Notice**\n"
        "Gambling can be addictive. Please play responsibly.\n"
        "If you need help, contact a professional or visit gamblinghelponline.org.au\n"
        "This bot is for entertainment purposes only."
    )


def validate_age(user: discord.User) -> bool:
    """Basic age validation (placeholder - implement proper age verification)."""
    # In a real implementation, you'd check user age or require verification
    return True  # Placeholder

# --- Compatibility helper aliases for other cogs (starboard) ---
def create_success_embed(title: str, description: str = "") -> Embed:
    return EmbedBuilder.success_embed(title, description)

def create_error_embed(title: str, description: str = "") -> Embed:
    return EmbedBuilder.error_embed(title, description)

def create_warning_embed(title: str, description: str = "") -> Embed:
    # Using yellow/orange for warning style
    return Embed(title=title, description=description, color=discord.Color.orange())
