"""
Configuration management using Pydantic settings.
"""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    """Bot configuration settings."""

    discord_token: str = Field(default='demo_token')
    guild_id: Optional[int] = Field(default=None)
    database_url: str = Field(default='sqlite+aiosqlite:///fun2oosh.db')
    log_level: str = Field(default='INFO')
    owner_id: Optional[int] = Field(default=None)
    topgg_token: Optional[str] = Field(default=None)
    topgg_webhook_secret: Optional[str] = Field(default=None)
    redis_url: Optional[str] = Field(default=None)

    # Game settings
    min_bet: int = Field(default=10)
    max_bet: int = Field(default=10000)
    daily_wager_limit: int = Field(default=50000)
    work_reward: int = Field(default=100)
    daily_reward: int = Field(default=500)
    weekly_reward: int = Field(default=2000)
    collect_cooldown: int = Field(default=3600)
    work_cooldown: int = Field(default=1800)
    daily_cooldown: int = Field(default=86400)
    weekly_cooldown: int = Field(default=604800)

    class Config:
        env_file = '.env'
        case_sensitive = False
