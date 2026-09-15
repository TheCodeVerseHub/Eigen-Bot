"""Command cooldown manager to prevent command spam."""

from __future__ import annotations

import time


class CooldownManager:
    """Tracks per-user command execution timestamps to enforce a cooldown."""

    def __init__(self, cooldown_seconds: float = 3.0) -> None:
        self.cooldown_seconds = cooldown_seconds
        self._last_used: dict[int, float] = {}

    def get_retry_after(self, user_id: int, now: float | None = None) -> float | None:
        """Return remaining cooldown seconds if user is on cooldown, else None."""
        if self.cooldown_seconds <= 0:
            return None

        last_time = self._last_used.get(user_id)
        if last_time is None:
            return None

        current_time = now if now is not None else time.monotonic()
        elapsed = current_time - last_time
        if elapsed < self.cooldown_seconds:
            return self.cooldown_seconds - elapsed

        return None

    def trigger(self, user_id: int) -> float | None:
        """Check if user is on cooldown.

        If on cooldown, returns remaining seconds.
        If not on cooldown, records current timestamp and returns None.
        """
        now = time.monotonic()
        retry_after = self.get_retry_after(user_id, now=now)
        if retry_after is not None:
            return retry_after

        self._last_used[user_id] = now

        # Prevent unbounded memory growth by pruning expired entries when large
        if len(self._last_used) > 5000:
            cutoff = now - self.cooldown_seconds
            self._last_used = {uid: ts for uid, ts in self._last_used.items() if ts > cutoff}

        return None

    def reset(self, user_id: int) -> None:
        """Clear cooldown for a specific user."""
        self._last_used.pop(user_id, None)

    def clear(self) -> None:
        """Clear all active cooldowns."""
        self._last_used.clear()
