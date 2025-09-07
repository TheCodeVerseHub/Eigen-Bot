"""
Bet model for tracking game bets.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Bet(Base):
    """Represents a bet placed in a game."""

    __tablename__ = 'bets'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    game: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., 'blackjack', 'roulette', 'slots'
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    bet_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g., 'red', 'single:5', 'hit'
    multiplier: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Payout multiplier
    outcome: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 'win', 'lose', 'push'
    payout: Mapped[int] = mapped_column(Integer, default=0)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Game-specific data (JSON string for flexibility)
    game_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string of game state

    def __repr__(self) -> str:
        return f"<Bet(id={self.id}, user_id={self.user_id}, game='{self.game}', amount={self.amount}, outcome='{self.outcome}')>"
