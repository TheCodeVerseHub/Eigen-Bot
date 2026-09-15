"""Tests for the command cooldown system."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from utils.config import Config
from utils.cooldown import CooldownManager


class TestCooldownManager(unittest.TestCase):
    def test_first_invocation_is_allowed(self) -> None:
        manager = CooldownManager(cooldown_seconds=3.0)
        self.assertIsNone(manager.trigger(12345))

    def test_subsequent_invocation_within_cooldown_is_blocked(self) -> None:
        manager = CooldownManager(cooldown_seconds=3.0)

        with patch("time.monotonic", side_effect=[100.0, 101.0, 101.0]):
            manager.trigger(12345)
            retry_after = manager.get_retry_after(12345)
            self.assertIsNotNone(retry_after)
            self.assertAlmostEqual(retry_after, 2.0, places=2)  # type: ignore[arg-type]

            retry = manager.trigger(12345)
            self.assertIsNotNone(retry)
            self.assertAlmostEqual(retry, 2.0, places=2)  # type: ignore[arg-type]

    def test_invocation_after_cooldown_window_is_allowed(self) -> None:
        manager = CooldownManager(cooldown_seconds=3.0)

        with patch("time.monotonic", side_effect=[100.0, 103.5]):
            manager.trigger(12345)
            self.assertIsNone(manager.trigger(12345))

    def test_different_users_have_independent_cooldowns(self) -> None:
        manager = CooldownManager(cooldown_seconds=3.0)

        with patch("time.monotonic", side_effect=[100.0, 100.5, 101.0]):
            self.assertIsNone(manager.trigger(111))
            self.assertIsNone(manager.trigger(222))
            self.assertIsNotNone(manager.trigger(111))

    def test_zero_or_negative_cooldown_disables_rate_limiting(self) -> None:
        zero_manager = CooldownManager(cooldown_seconds=0.0)
        neg_manager = CooldownManager(cooldown_seconds=-1.0)

        self.assertIsNone(zero_manager.trigger(123))
        self.assertIsNone(zero_manager.trigger(123))
        self.assertIsNone(neg_manager.trigger(123))
        self.assertIsNone(neg_manager.trigger(123))

    def test_reset_and_clear(self) -> None:
        manager = CooldownManager(cooldown_seconds=5.0)
        manager.trigger(100)
        manager.trigger(200)

        manager.reset(100)
        self.assertIsNone(manager.get_retry_after(100))
        self.assertIsNotNone(manager.get_retry_after(200))

        manager.clear()
        self.assertIsNone(manager.get_retry_after(200))

    def test_pruning_expired_entries_when_cache_large(self) -> None:
        manager = CooldownManager(cooldown_seconds=2.0)
        # Pre-populate map with 5001 old entries
        manager._last_used = {i: 10.0 for i in range(5001)}

        with patch("time.monotonic", return_value=50.0):
            # Triggering a new user should prune the old entries older than 50.0 - 2.0
            manager.trigger(999999)

        # Only the new user should remain
        self.assertEqual(len(manager._last_used), 1)
        self.assertIn(999999, manager._last_used)


class TestCooldownConfig(unittest.TestCase):
    def test_default_cooldown_config(self) -> None:
        config = Config()
        self.assertEqual(config.command_cooldown_seconds, 3.0)

    def test_custom_cooldown_config(self) -> None:
        config = Config(command_cooldown_seconds=5.5)
        self.assertEqual(config.command_cooldown_seconds, 5.5)
