"""
Tests for API endpoints.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import status


@pytest.mark.unit
class TestHealthEndpoint:
    """Test health check endpoint."""
    
    def test_health_endpoint_returns_ok(self, test_client):
        """Test that health endpoint returns 200."""
        with patch('app.api.get_user_count', return_value=AsyncMock(return_value=0)):
            response = test_client.get("/health")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] in ["healthy", "ok"]


@pytest.mark.unit
class TestHomeEndpoint:
    """Test home page endpoint."""
    
    def test_home_page_returns_html(self, test_client):
        """Test that home page returns HTML."""
        with patch('app.api.get_user_count', return_value=AsyncMock(return_value=5)):
            response = test_client.get("/")
            assert response.status_code == status.HTTP_200_OK
            assert "text/html" in response.headers.get("content-type", "")


@pytest.mark.unit
class TestOnboardEndpoint:
    """Test onboard endpoint."""
    
    def test_onboard_initiates_auth_flow(self, test_client, mock_auth_flow):
        """Test that onboard endpoint initiates OAuth flow."""
        mock_msal_app = Mock()
        mock_msal_app.initiate_auth_code_flow.return_value = mock_auth_flow
        
        with patch('app.api.get_msal_app', return_value=mock_msal_app):
            response = test_client.get("/onboard", follow_redirects=False)
            
            # Should redirect to Microsoft login
            assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
            assert "login.microsoftonline.com" in response.headers.get("location", "")
    
    def test_onboard_handles_msal_error(self, test_client):
        """Test that onboard handles MSAL errors gracefully."""
        mock_msal_app = Mock()
        mock_msal_app.initiate_auth_code_flow.return_value = {
            "error": "invalid_client",
            "error_description": "Client not found"
        }
        
        with patch('app.api.get_msal_app', return_value=mock_msal_app):
            response = test_client.get("/onboard")
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


@pytest.mark.unit
class TestCallbackEndpoint:
    """Test OAuth callback endpoint."""
    
    def test_callback_without_session_fails(self, test_client):
        """Test that callback without session returns error."""
        with patch('app.api.get_msal_app'):
            response = test_client.get("/auth/callback?code=test-code")
            # Could be 400 (bad request) or 503 (service unavailable)
            assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_503_SERVICE_UNAVAILABLE]
    
    @pytest.mark.skip(reason="TestClient doesn't support session manipulation - needs integration test")
    def test_callback_with_valid_flow_succeeds(
        self, test_client, mock_auth_flow, mock_msal_token_response
    ):
        """Test successful OAuth callback."""
        # This test requires a real session which TestClient doesn't support
        # It should be converted to an integration test with a real test server
        pass


@pytest.mark.unit
class TestTokensEndpoint:
    """Test tokens endpoint."""
    
    def test_tokens_without_auth_fails(self, test_client):
        """Test that accessing tokens without authentication fails."""
        response = test_client.get("/tokens")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    @pytest.mark.skip(reason="TestClient doesn't support session manipulation - needs integration test")
    def test_tokens_with_auth_succeeds(self, test_client, mock_user_data):
        """Test accessing tokens with authentication."""
        # This test requires session support which TestClient doesn't provide
        # It should be converted to an integration test
        pass


@pytest.mark.unit
class TestAdminEndpoints:
    """Test admin endpoints."""
    
    def test_admin_users_list(self, test_client):
        """Test admin users list endpoint."""
        mock_users = [
            {
                "user_id": "user-1",
                "email": "user1@example.com",
                "name": "User One",
                "created_at": "2026-01-01T00:00:00",
                "updated_at": "2026-01-01T00:00:00",
            },
            {
                "user_id": "user-2",
                "email": "user2@example.com",
                "name": "User Two",
                "created_at": "2026-01-02T00:00:00",
                "updated_at": "2026-01-02T00:00:00",
            },
        ]
        
        async def mock_get_all_users():
            return mock_users
        
        with patch('app.api.get_all_users', new=mock_get_all_users):
            response = test_client.get("/admin/users")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total_users"] == 2
            assert len(data["users"]) == 2
