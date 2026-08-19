"""Smoke tests to ensure pytest discovers and exercises core utilities."""

from __future__ import annotations

import unittest

from utils.config import Config
from utils.helpers import get_random_quote, sanitize_input


class TestSmoke(unittest.TestCase):
    def test_config_parses_guild_ids_from_csv(self) -> None:
        config = Config(guild_ids="1, 2, 3")

        self.assertEqual(config.guild_ids, [1, 2, 3])

    def test_sanitize_input_trims_and_limits_length(self) -> None:
        text = "  " + ("a" * 1200) + "  "

        result = sanitize_input(text, max_len=1000)

        self.assertEqual(result, "a" * 1000)

    def test_get_random_quote_returns_empty_string_for_empty_input(self) -> None:
        self.assertEqual(get_random_quote([]), "")
