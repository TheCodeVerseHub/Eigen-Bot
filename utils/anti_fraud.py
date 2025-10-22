"""
Anti-fraud utilities for detecting suspicious activity.
"""

import time
from collections import defaultdict
from typing import Dict, List

from discord import Member


class AntiFraud:
    """Anti-fraud detection system."""

    def __init__(self):
        self.bet_history: Dict[int, List[tuple]] = defaultdict(list)  # user_id -> [(timestamp, amount), ...]
        self.transfer_history: Dict[int, List[tuple]] = defaultdict(list)

    def record_bet(self, user_id: int, amount: int):
        """Record a bet for fraud detection."""
        self.bet_history[user_id].append((time.time(), amount))
        # Keep only last 100 bets
        if len(self.bet_history[user_id]) > 100:
            self.bet_history[user_id].pop(0)

    def record_transfer(self, user_id: int, amount: int):
        """Record a transfer for fraud detection."""
        self.transfer_history[user_id].append((time.time(), amount))
        # Keep only last 50 transfers
        if len(self.transfer_history[user_id]) > 50:
            self.transfer_history[user_id].pop(0)

    def check_bet_velocity(self, user_id: int, time_window: int = 300) -> tuple[bool, str]:
        """Check for suspicious bet velocity (bets per time window)."""
        now = time.time()
        recent_bets = [t for t, _ in self.bet_history[user_id] if now - t < time_window]

        if len(recent_bets) > 20:  # More than 20 bets in 5 minutes
            return True, "Suspicious bet velocity detected."

        return False, ""

    def check_large_bets(self, user_id: int, amount: int, threshold: int = 10000) -> tuple[bool, str]:
        """Check for large bet amounts."""
        if amount > threshold:
            return True, f"Large bet of {amount} coins flagged for review."

        return False, ""

    def check_transfer_patterns(self, user_id: int) -> tuple[bool, str]:
        """Check for suspicious transfer patterns."""
        now = time.time()
        recent_transfers = [t for t, _ in self.transfer_history[user_id] if now - t < 3600]  # Last hour

        if len(recent_transfers) > 10:  # More than 10 transfers in an hour
            return True, "Suspicious transfer activity detected."

        return False, ""

    def is_suspicious(self, user_id: int, amount: int, action: str) -> tuple[bool, str]:
        """Overall fraud check."""
        if action == 'bet':
            self.record_bet(user_id, amount)
            velocity_check = self.check_bet_velocity(user_id)
            if velocity_check[0]:
                return velocity_check

            large_check = self.check_large_bets(user_id, amount)
            if large_check[0]:
                return large_check

        elif action == 'transfer':
            self.record_transfer(user_id, amount)
            transfer_check = self.check_transfer_patterns(user_id)
            if transfer_check[0]:
                return transfer_check

        return False, ""


# Global anti-fraud instance
anti_fraud = AntiFraud()
