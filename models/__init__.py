"""
Database models for fun2oosh bot.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from .base import Base
from .bet import Bet
from .transaction import Transaction
from .user import User
from .wallet import Wallet


# Type aliases for convenience
Session = AsyncSession

__all__ = ['Base', 'User', 'Wallet', 'Transaction', 'Bet', 'Session']