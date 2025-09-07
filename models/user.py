"""
User model for storing Discord user information.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class User(Base):
    """Represents a Discord user in the database."""

    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)  # Discord user ID
    username: Mapped[str] = mapped_column(String(32), nullable=False)
    discriminator: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)  # For legacy usernames
    avatar_hash: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Responsible gaming
    age_verified: Mapped[bool] = mapped_column(default=False)
    banned: Mapped[bool] = mapped_column(default=False)
    ban_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Activity tracking
    last_active: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    total_wagered: Mapped[int] = mapped_column(default=0)
    total_won: Mapped[int] = mapped_column(default=0)
    total_lost: Mapped[int] = mapped_column(default=0)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}')>"
