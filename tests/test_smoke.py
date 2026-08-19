"""Smoke tests to ensure pytest discovers and exercises core utilities."""

from utils.config import Config
from utils.helpers import get_random_quote, sanitize_input


def test_config_parses_guild_ids_from_csv() -> None:
    config = Config(discord_token="demo", guild_ids="1, 2, 3")

    assert config.guild_ids == [1, 2, 3]


def test_sanitize_input_trims_and_limits_length() -> None:
    text = "  " + ("a" * 1200) + "  "

    result = sanitize_input(text, max_len=1000)

    assert result == "a" * 1000


def test_get_random_quote_returns_empty_string_for_empty_input() -> None:
    assert get_random_quote([]) == ""
