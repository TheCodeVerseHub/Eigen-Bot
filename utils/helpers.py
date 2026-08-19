"""
Helper utilities for the bot.
"""

import random

import discord
from discord import Embed


class EmbedBuilder:
    """Helper class for building Discord embeds."""

    @staticmethod
    def success_embed(title: str, description: str = "") -> Embed:
        """Create a success embed."""
        embed = Embed(title=title, description=description, color=0x00ff00)
        return embed

    @staticmethod
    def error_embed(title: str, description: str = "") -> Embed:
        """Create an error embed."""
        embed = Embed(title=title, description=description, color=0xff0000)
        return embed

    @staticmethod
    def info_embed(title: str, description: str = "") -> Embed:
        """Create an info embed."""
        embed = Embed(title=title, description=description, color=0x07f9dd)
        return embed


# --- Additional helpers used by cogs/community.py ---
def get_random_quote(quotes: list) -> str:
    if not quotes:
        return ""
    return random.choice(quotes)


def get_random_question(questions: list):
    if not questions:
        return None
    return random.choice(questions)


async def fetch_programming_meme() -> str:
    # Minimal implementation: random choice from a small curated list.
    # This avoids repeating the same meme every time without relying on external APIs.
    meme_urls = [
        "https://i.imgur.com/3G9jQ.jpg",
        "https://i.imgur.com/2QZpF0B.jpg",
        "https://i.imgur.com/8p0Q8Jk.jpg",
        "https://i.imgur.com/N9bG8cR.jpg",
        "https://i.imgur.com/BY6L8dP.jpg",
        "https://i.imgur.com/9Y9yCwE.jpg",
        "https://i.imgur.com/7QpB6hO.jpg",
        "https://i.imgur.com/7Z2W9Qn.jpg",
        "https://i.imgur.com/1E7oQpP.jpg",
        "https://i.imgur.com/qk1GzQp.jpg",
    ]
    return random.choice(meme_urls)


def sanitize_input(text: str, max_len: int = 1000) -> str:
    if not text:
        return ""
    cleaned = text.strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len]
    return cleaned

# --- Compatibility helper aliases for other cogs (starboard) ---
def create_success_embed(title: str, description: str = "") -> Embed:
    return EmbedBuilder.success_embed(title, description)

def create_error_embed(title: str, description: str = "") -> Embed:
    return EmbedBuilder.error_embed(title, description)

def create_warning_embed(title: str, description: str = "") -> Embed:
    # Using yellow/orange for warning style
    return Embed(title=title, description=description, color=discord.Color.orange())

def create_info_embed(title: str, description: str = "") -> Embed:
    return EmbedBuilder.info_embed(title, description)
