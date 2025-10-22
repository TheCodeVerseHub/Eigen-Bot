"""
Cooldown management utilities.
"""

import time
from typing import Dict, Optional

from discord import Member
from discord.ext import commands


class CooldownManager:
    """Manages cooldowns for commands."""

    def __init__(self):
        self.cooldowns: Dict[str, Dict[int, float]] = {}

    def is_on_cooldown(self, command: str, user_id: int, cooldown_seconds: int) -> bool:
        """Check if a user is on cooldown for a command."""
        if command not in self.cooldowns:
            return False

        user_cooldowns = self.cooldowns[command]
        if user_id not in user_cooldowns:
            return False

        last_used = user_cooldowns[user_id]
        if time.time() - last_used < cooldown_seconds:
            return True

        return False

    def set_cooldown(self, command: str, user_id: int):
        """Set cooldown for a user on a command."""
        if command not in self.cooldowns:
            self.cooldowns[command] = {}

        self.cooldowns[command][user_id] = time.time()

    def get_remaining_time(self, command: str, user_id: int, cooldown_seconds: int) -> float:
        """Get remaining cooldown time in seconds."""
        if not self.is_on_cooldown(command, user_id, cooldown_seconds):
            return 0.0

        last_used = self.cooldowns[command][user_id]
        return cooldown_seconds - (time.time() - last_used)

    def clear_cooldown(self, command: str, user_id: int):
        """Clear cooldown for a user on a command."""
        if command in self.cooldowns and user_id in self.cooldowns[command]:
            del self.cooldowns[command][user_id]


# Global cooldown manager instance
cooldown_manager = CooldownManager()


def check_cooldown(command: str, cooldown_seconds: int):
    """Decorator to check cooldown for a command."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # For method, args[0] is self, args[1] is ctx
            ctx = args[1]
            if cooldown_manager.is_on_cooldown(command, ctx.author.id, cooldown_seconds):
                remaining = cooldown_manager.get_remaining_time(command, ctx.author.id, cooldown_seconds)
                await ctx.send(f"This command is on cooldown. Try again in {remaining:.1f} seconds.")
                return

            cooldown_manager.set_cooldown(command, ctx.author.id)
            return await func(*args, **kwargs)
        return wrapper
    return decorator
