"""
Tests for token service.
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import select

from app.database import UserToken
from app.services.token_service import (
    save_user_tokens,
    get_user_tokens,
    update_tokens,
    delete_user_tokens,
    get_user_count,
)
from app.services.encryption import encrypt_token, decrypt_token


@pytest.mark.unit
class TestTokenService:
    """Test token service database operations."""
    
    @pytest.mark.asyncio
    async def test_save_new_user_tokens(self, test_db_session, mock_user_data):
        """Test saving tokens for a new user."""
        # Mock get_db_session to use test session
        from app.database import get_db_session
        from unittest.mock import AsyncMock, patch
        from contextlib import asynccontextmanager
        
        @asynccontextmanager
        async def mock_get_db():
            yield test_db_session
        
        with patch('app.services.token_service.get_db_session', mock_get_db):
            await save_user_tokens(
                user_id=mock_user_data["user_id"],
                email=mock_user_data["email"],
                name=mock_user_data["name"],
                access_token=mock_user_data["access_token"],
                refresh_token=mock_user_data["refresh_token"],
                expires_at=mock_user_data["expires_at"],
            )
            
            # Verify user was saved
            result = await test_db_session.execute(
                select(UserToken).where(UserToken.user_id == mock_user_data["user_id"])
            )
            user = result.scalar_one_or_none()
            
            assert user is not None
            assert user.user_id == mock_user_data["user_id"]
            assert user.email == mock_user_data["email"]
            assert user.name == mock_user_data["name"]
            # Tokens should be encrypted
            assert user.access_token != mock_user_data["access_token"]
            assert user.refresh_token != mock_user_data["refresh_token"]
    
    @pytest.mark.asyncio
    async def test_update_existing_user_tokens(self, test_db_session, mock_user_data):
        """Test updating tokens for an existing user."""
        from unittest.mock import patch
        from contextlib import asynccontextmanager
        
        @asynccontextmanager
        async def mock_get_db():
            yield test_db_session
        
        with patch('app.services.token_service.get_db_session', mock_get_db):
            # Save initial tokens
            await save_user_tokens(
                user_id=mock_user_data["user_id"],
                email=mock_user_data["email"],
                name=mock_user_data["name"],
                access_token=mock_user_data["access_token"],
                refresh_token=mock_user_data["refresh_token"],
                expires_at=mock_user_data["expires_at"],
            )
            
            # Update with new tokens
            new_access_token = "new-access-token-xyz"
            new_refresh_token = "new-refresh-token-xyz"
            
            await save_user_tokens(
                user_id=mock_user_data["user_id"],
                email=mock_user_data["email"],
                name="Updated Name",
                access_token=new_access_token,
                refresh_token=new_refresh_token,
                expires_at=mock_user_data["expires_at"],
            )
            
            # Verify update
            result = await test_db_session.execute(
                select(UserToken).where(UserToken.user_id == mock_user_data["user_id"])
            )
            user = result.scalar_one_or_none()
            
            assert user is not None
            assert user.name == "Updated Name"
            # Should have new encrypted tokens
            decrypted_access = decrypt_token(user.access_token)
            assert decrypted_access == new_access_token
    
    @pytest.mark.asyncio
    async def test_get_user_tokens(self, test_db_session, mock_user_data):
        """Test retrieving user tokens."""
        from unittest.mock import patch
        from contextlib import asynccontextmanager
        
        @asynccontextmanager
        async def mock_get_db():
            yield test_db_session
        
        with patch('app.services.token_service.get_db_session', mock_get_db):
            # Save tokens
            await save_user_tokens(
                user_id=mock_user_data["user_id"],
                email=mock_user_data["email"],
                name=mock_user_data["name"],
                access_token=mock_user_data["access_token"],
                refresh_token=mock_user_data["refresh_token"],
                expires_at=mock_user_data["expires_at"],
            )
            
            # Retrieve tokens
            user_data = await get_user_tokens(mock_user_data["user_id"])
            
            assert user_data is not None
            assert user_data["user_id"] == mock_user_data["user_id"]
            assert user_data["email"] == mock_user_data["email"]
            assert user_data["name"] == mock_user_data["name"]
            # Tokens should be decrypted
            assert user_data["access_token"] == mock_user_data["access_token"]
            assert user_data["refresh_token"] == mock_user_data["refresh_token"]
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_user_returns_none(self, test_db_session):
        """Test retrieving tokens for a user that doesn't exist."""
        from unittest.mock import patch
        from contextlib import asynccontextmanager
        
        @asynccontextmanager
        async def mock_get_db():
            yield test_db_session
        
        with patch('app.services.token_service.get_db_session', mock_get_db):
            user_data = await get_user_tokens("nonexistent-user-id")
            assert user_data is None
    
    @pytest.mark.asyncio
    async def test_delete_user_tokens(self, test_db_session, mock_user_data):
        """Test deleting user tokens."""
        from unittest.mock import patch
        from contextlib import asynccontextmanager
        
        @asynccontextmanager
        async def mock_get_db():
            yield test_db_session
        
        with patch('app.services.token_service.get_db_session', mock_get_db):
            # Save tokens
            await save_user_tokens(
                user_id=mock_user_data["user_id"],
                email=mock_user_data["email"],
                name=mock_user_data["name"],
                access_token=mock_user_data["access_token"],
                refresh_token=mock_user_data["refresh_token"],
                expires_at=mock_user_data["expires_at"],
            )
            
            # Delete tokens
            deleted = await delete_user_tokens(mock_user_data["user_id"])
            assert deleted is True
            
            # Verify deletion
            user_data = await get_user_tokens(mock_user_data["user_id"])
            assert user_data is None
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_user_returns_false(self, test_db_session):
        """Test deleting tokens for a user that doesn't exist."""
        from unittest.mock import patch
        from contextlib import asynccontextmanager
        
        @asynccontextmanager
        async def mock_get_db():
            yield test_db_session
        
        with patch('app.services.token_service.get_db_session', mock_get_db):
            deleted = await delete_user_tokens("nonexistent-user-id")
            assert deleted is False
