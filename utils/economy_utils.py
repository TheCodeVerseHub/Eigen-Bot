"""
Utility functions for economy operations.
"""

import asyncio
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Transaction, Wallet
from utils.config import Config


class EconomyUtils:
    """Utility class for economy-related operations."""

    @staticmethod
    async def get_wallet(session: AsyncSession, user_id: int) -> Optional[Wallet]:
        """Get a user's wallet."""
        stmt = select(Wallet).where(Wallet.user_id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create_wallet(session: AsyncSession, user_id: int) -> Wallet:
        """Create a new wallet for a user."""
        wallet = Wallet(user_id=user_id)
        session.add(wallet)
        # Flush so that defaults declared in the model are applied and available on the instance
        try:
            await session.flush()
        except Exception:
            # If flush fails for any reason, ignore here; calling code/tests can handle commit
            pass
        return wallet

    @staticmethod
    async def get_or_create_wallet(session: AsyncSession, user_id: int) -> Wallet:
        """Get or create a wallet for a user."""
        wallet = await EconomyUtils.get_wallet(session, user_id)
        if wallet is None:
            wallet = await EconomyUtils.create_wallet(session, user_id)
            # Flush to ensure defaults are applied
            await session.flush()
            # Ensure default values are set
            if wallet.balance is None:
                wallet.balance = 0
            if wallet.bank is None:
                wallet.bank = 0
        return wallet

    @staticmethod
    async def transfer_money(
        session: AsyncSession,
        from_user_id: int,
        to_user_id: int,
        amount: int,
        description: str = ""
    ) -> bool:
        """Transfer money between users atomically."""
        if amount <= 0:
            return False

        # Use a transaction for atomicity
        async with session.begin():
            # Get sender wallet
            sender_wallet = await EconomyUtils.get_wallet(session, from_user_id)
            if sender_wallet is None or sender_wallet.balance < amount:
                return False

            # Get or create receiver wallet
            receiver_wallet = await EconomyUtils.get_or_create_wallet(session, to_user_id)

            # Update balances
            sender_wallet.balance -= amount
            receiver_wallet.balance += amount

            # Record transactions
            sender_tx = Transaction(
                user_id=from_user_id,
                type='transfer_out',
                amount=-amount,
                description=description,
                recipient_id=to_user_id
            )
            receiver_tx = Transaction(
                user_id=to_user_id,
                type='transfer_in',
                amount=amount,
                description=description,
                recipient_id=from_user_id
            )

            session.add(sender_tx)
            session.add(receiver_tx)

        return True

    @staticmethod
    async def add_money(
        session: AsyncSession,
        user_id: int,
        amount: int,
        type_: str,
        description: str = "",
        game: Optional[str] = None
    ) -> bool:
        """Add money to a user's wallet."""
        if amount < 0:
            return False

        wallet = await EconomyUtils.get_or_create_wallet(session, user_id)
        wallet.balance += amount

        tx = Transaction(
            user_id=user_id,
            type=type_,
            amount=amount,
            description=description,
            game=game
        )
        session.add(tx)

        return True

    @staticmethod
    async def subtract_money(
        session: AsyncSession,
        user_id: int,
        amount: int,
        type_: str,
        description: str = "",
        game: Optional[str] = None
    ) -> bool:
        """Subtract money from a user's wallet."""
        if amount < 0:
            return False

        wallet = await EconomyUtils.get_wallet(session, user_id)
        if wallet is None or wallet.balance < amount:
            return False

        wallet.balance -= amount

        tx = Transaction(
            user_id=user_id,
            type=type_,
            amount=-amount,
            description=description,
            game=game
        )
        session.add(tx)

        return True

    @staticmethod
    def validate_bet_amount(config: Config, amount: int, user_daily_wagered: int) -> tuple[bool, str]:
        """Validate a bet amount against limits."""
        if amount < config.min_bet:
            return False, f"Minimum bet is {config.min_bet} coins."
        if amount > config.max_bet:
            return False, f"Maximum bet is {config.max_bet} coins."
        if user_daily_wagered + amount > config.daily_wager_limit:
            return False, f"Daily wager limit exceeded. You can wager {config.daily_wager_limit - user_daily_wagered} more coins today."
        return True, ""
