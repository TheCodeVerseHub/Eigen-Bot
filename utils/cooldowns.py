"""Fallback per-user cooldown applied to commands with no cooldown of their own.

Commands that already declare an explicit `@commands.cooldown(...)` /
`@app_commands.checks.cooldown(...)` keep using that instead — this only
gates commands that would otherwise have no rate limit at all.
"""

from __future__ import annotations

import time

from discord import Interaction, app_commands
from discord.ext import commands


class GlobalCooldown:
    """Sliding-window per-user cooldown bucket."""

    def __init__(self, rate: int, per: float) -> None:
        self.rate = rate
        self.per = per
        self._uses: dict[int, list[float]] = {}

    def update_rate_limit(self, user_id: int) -> float | None:
        """Record a use for `user_id`, returning seconds to wait if rate-limited."""
        now = time.monotonic()
        window_start = now - self.per
        uses = [t for t in self._uses.get(user_id, []) if t > window_start]

        if len(uses) >= self.rate:
            self._uses[user_id] = uses
            return self.per - (now - uses[0])

        uses.append(now)
        self._uses[user_id] = uses
        return None


def prefix_command_check(cooldown: GlobalCooldown):
    """Bot-wide `commands.check` used as a fallback for prefix/hybrid commands."""

    async def predicate(ctx: commands.Context) -> bool:
        command = ctx.command
        if command is not None and command._buckets.valid:
            # Command already has its own cooldown bucket; don't double-gate it.
            return True

        retry_after = cooldown.update_rate_limit(ctx.author.id)
        if retry_after is not None:
            raise commands.CommandOnCooldown(
                commands.Cooldown(cooldown.rate, cooldown.per),
                retry_after,
                commands.BucketType.user,
            )
        return True

    return predicate


def app_command_interaction_check(cooldown: GlobalCooldown):
    """Fallback cooldown check for slash-only commands via `CommandTree.interaction_check`."""

    async def predicate(interaction: Interaction) -> bool:
        command = interaction.command
        if command is not None and getattr(command, "checks", None):
            # Command already has its own check(s), e.g. a cooldown.
            return True

        retry_after = cooldown.update_rate_limit(interaction.user.id)
        if retry_after is not None:
            raise app_commands.CommandOnCooldown(
                app_commands.Cooldown(cooldown.rate, cooldown.per), retry_after
            )
        return True

    return predicate
