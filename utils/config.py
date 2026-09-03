"""Configuration management using Pydantic settings."""

from __future__ import annotations

import os
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Bot configuration settings."""

    discord_token: str = Field(default='demo_token')
    # Backwards compatible single guild id
    guild_id: int | None = Field(default=None)
    # Preferred: comma-separated list (or JSON list) of guild ids for fast per-guild slash-command sync
    guild_ids: list[int] = Field(default_factory=list)
    log_level: str = Field(default='INFO')
    # Fallback per-user cooldown (seconds) for commands with no cooldown of their own.
    default_command_cooldown_seconds: float = Field(default=3.0)
    owner_id: int | None = Field(default=None)
    topgg_token: str | None = Field(default=None)
    topgg_webhook_secret: str | None = Field(default=None)
    redis_url: str | None = Field(default=None)

    # CodeBuddy settings
    question_channel_id: int | None = Field(default=None)

    model_config = SettingsConfigDict(
        env_file='.env',
        case_sensitive=False,
        extra='ignore'  # Ignore extra fields from .env
    )

    @field_validator('guild_id', mode='before')
    @classmethod
    def _parse_guild_id(cls, v: Any) -> int | None:
        """Parse legacy single guild id.

        Some deployments mistakenly set `GUILD_ID` as a CSV / JSON list.
        To stay backwards compatible and avoid startup failures, we accept:
        - int
        - numeric string
        - CSV: "1,2,3" (uses the first value)
        - JSON list: "[1,2]" (uses the first value)
        """
        if v is None:
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return None
            if s.startswith('[') and s.endswith(']'):
                try:
                    import json

                    parsed = json.loads(s)
                    if isinstance(parsed, list) and parsed:
                        return int(parsed[0])
                except Exception:
                    # Fall back to CSV/int parsing
                    pass
            if ',' in s:
                first = s.split(',', 1)[0].strip()
                return int(first) if first else None
            return int(s)
        return int(v)

    @field_validator('guild_ids', mode='before')
    @classmethod
    def _parse_guild_ids(cls, v: Any) -> list[int]:
        """Parse guild ids from env.

        Supports:
        - unset / empty -> []
        - JSON list: "[1,2]"
        - CSV: "1,2,3"
        """
        if v is None:
            # If GUILD_IDS isn't set, allow legacy GUILD_ID to behave like a list.
            legacy = os.getenv('GUILD_ID')
            if legacy and str(legacy).strip():
                v = legacy
            else:
                return []
        if isinstance(v, list):
            return [int(x) for x in v if str(x).strip()]
        if isinstance(v, (int, str)):
            s = str(v).strip()
            if not s:
                return []
            # JSON list
            if s.startswith('[') and s.endswith(']'):
                try:
                    import json

                    parsed = json.loads(s)
                    if isinstance(parsed, list):
                        return [int(x) for x in parsed]
                except Exception:
                    # Fall back to CSV parsing
                    pass
            # CSV
            parts = [p.strip() for p in s.split(',')]
            return [int(p) for p in parts if p]
        raise TypeError('guild_ids must be a list, int, or string')

    @model_validator(mode='after')
    def _coerce_single_guild_to_list(self) -> Config:
        # If only legacy GUILD_ID is set, treat it as a single-item list.
        if not self.guild_ids and self.guild_id:
            self.guild_ids = [int(self.guild_id)]
        return self
