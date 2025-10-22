"""
Transaction model for tracking all economy transactions.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Transaction(Base):
    """Represents a transaction in the economy."""

    __tablename__ = 'transactions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., 'work', 'bet', 'transfer', 'deposit'
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # For transfers
    recipient_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # For bets/games
    game: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    bet_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Link to Bet model if needed

    def __repr__(self) -> str:
        return f"<Transaction(id={self.id}, user_id={self.user_id}, type='{self.type}', amount={self.amount})>"
