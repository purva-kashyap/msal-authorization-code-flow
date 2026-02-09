"""
Tests for Pydantic models.
"""
import pytest
from pydantic import ValidationError

from app.models import UserInfo, TokenInfo, TokenResponse, HealthCheck, UserList


@pytest.mark.unit
class TestModels:
    """Test Pydantic models."""
    
    def test_user_info_valid(self):
        """Test creating valid UserInfo."""
        user = UserInfo(
            user_id="user-123",
            email="test@example.com",
            name="Test User"
        )
        
        assert user.user_id == "user-123"
        assert user.email == "test@example.com"
        assert user.name == "Test User"
    
    def test_user_info_optional_fields(self):
        """Test UserInfo with optional fields."""
        user = UserInfo(user_id="user-123")
        
        assert user.user_id == "user-123"
        assert user.email is None
        assert user.name is None
    
    def test_token_info_valid(self):
        """Test creating valid TokenInfo."""
        from datetime import datetime
        
        token_info = TokenInfo(
            user_id="user-123",
            email="test@example.com",
            name="Test User",
            access_token_preview="preview123",
            expires_at=datetime.now().timestamp() + 3600,  # Unix timestamp
            expires_in_seconds=3600,
            created_at="2026-02-09T11:00:00",
            updated_at="2026-02-09T11:00:00"
        )
        
        assert token_info.user_id == "user-123"
        assert token_info.expires_in_seconds == 3600
        assert isinstance(token_info.expires_at, float)
    
    def test_token_info_missing_required_field_fails(self):
        """Test that TokenInfo requires all mandatory fields."""
        with pytest.raises(ValidationError):
            TokenInfo(user_id="user-123")
    
    def test_token_response_valid(self):
        """Test creating valid TokenResponse."""
        response = TokenResponse(
            message="Success",
            user=UserInfo(user_id="user-123"),
            expires_in=3600
        )
        
        assert response.message == "Success"
        assert response.user.user_id == "user-123"
        assert response.expires_in == 3600
    
    def test_health_check_valid(self):
        """Test creating valid HealthCheck."""
        health = HealthCheck(
            status="healthy",
            database="connected",
            total_users=10,
            timestamp="2026-02-09T12:00:00"
        )
        
        assert health.status == "healthy"
        assert health.database == "connected"
        assert health.total_users == 10
    
    def test_user_list_valid(self):
        """Test creating valid UserList."""
        users = [
            UserInfo(user_id="user-1", email="user1@example.com"),
            UserInfo(user_id="user-2", email="user2@example.com"),
        ]
        
        user_list = UserList(total_users=2, users=users)
        
        assert user_list.total_users == 2
        assert len(user_list.users) == 2
    
    def test_user_list_empty(self):
        """Test creating empty UserList."""
        user_list = UserList(total_users=0, users=[])
        
        assert user_list.total_users == 0
        assert len(user_list.users) == 0
