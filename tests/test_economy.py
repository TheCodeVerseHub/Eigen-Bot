"""
Tests for economy functionality.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from models import Wallet
from utils.economy_utils import EconomyUtils


class TestEconomyUtils:
    """Test economy utilities."""

    @pytest.mark.asyncio
    async def test_get_wallet(self, session: AsyncSession):
        """Test getting a wallet."""
        wallet = await EconomyUtils.get_wallet(session, 123)
        assert wallet is None

    @pytest.mark.asyncio
    async def test_create_wallet(self, session: AsyncSession):
        """Test creating a wallet."""
        wallet = await EconomyUtils.create_wallet(session, 123)
        assert wallet.user_id == 123
        assert wallet.balance == 0
        assert wallet.bank == 0
