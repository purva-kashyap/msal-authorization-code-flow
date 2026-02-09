"""
Pytest configuration and fixtures.
"""
import pytest
import os
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from cryptography.fernet import Fernet

from app.database import Base, get_db_session
from app.config import Settings


# ============================================
# TEST CONFIGURATION
# ============================================

@pytest.fixture(scope="session")
def test_encryption_key():
    """Generate a test encryption key."""
    return Fernet.generate_key().decode()


@pytest.fixture(scope="session")
def test_settings(test_encryption_key):
    """Create test settings."""
    return Settings(
        client_id="test-client-id",
        client_secret="test-client-secret",
        tenant_id="test-tenant-id",
        redirect_uri="http://localhost:8000/auth/callback",
        database_url="postgresql+asyncpg://test:test@localhost:5432/test_db",
        encryption_key=test_encryption_key,
        secret_key="test-secret-key-for-sessions",
        debug=True,
    )


# ============================================
# DATABASE FIXTURES
# ============================================

@pytest.fixture(scope="function")
async def test_engine():
    """Create a test database engine using in-memory SQLite."""
    # Use SQLite for testing (in-memory)
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    await engine.dispose()


@pytest.fixture(scope="function")
async def test_db_session(test_engine):
    """Create a test database session."""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture(scope="function")
async def override_get_db_session(test_db_session):
    """Override the get_db_session dependency."""
    async def _get_db():
        yield test_db_session
    return _get_db


# ============================================
# TEST CLIENT FIXTURES
# ============================================

@pytest.fixture(scope="function")
def test_client(test_settings, monkeypatch):
    """Create a test client."""
    # Set test environment variables
    monkeypatch.setenv("CLIENT_ID", test_settings.client_id)
    monkeypatch.setenv("CLIENT_SECRET", test_settings.client_secret)
    monkeypatch.setenv("TENANT_ID", test_settings.tenant_id)
    monkeypatch.setenv("ENCRYPTION_KEY", test_settings.encryption_key)
    monkeypatch.setenv("SECRET_KEY", test_settings.secret_key)
    monkeypatch.setenv("DEBUG", "True")
    
    # Import app after setting env vars
    from main import app
    
    client = TestClient(app)
    return client


# ============================================
# MOCK DATA FIXTURES
# ============================================

@pytest.fixture
def mock_user_data():
    """Mock user data for testing."""
    return {
        "user_id": "test-user-123",
        "email": "test@example.com",
        "name": "Test User",
        "access_token": "mock-access-token-" + "x" * 100,
        "refresh_token": "mock-refresh-token-" + "y" * 100,
        "expires_at": (datetime.now() + timedelta(hours=1)).timestamp(),
    }


@pytest.fixture
def mock_msal_token_response():
    """Mock MSAL token response."""
    return {
        "access_token": "mock-access-token-" + "x" * 100,
        "refresh_token": "mock-refresh-token-" + "y" * 100,
        "expires_in": 3600,
        "id_token_claims": {
            "oid": "test-user-123",
            "preferred_username": "test@example.com",
            "email": "test@example.com",
            "name": "Test User",
        },
    }


@pytest.fixture
def mock_auth_flow():
    """Mock MSAL auth flow."""
    return {
        "auth_uri": "https://login.microsoftonline.com/authorize?client_id=test",
        "state": "test-state-123",
        "code_verifier": "test-verifier",
    }


# ============================================
# HELPER FIXTURES
# ============================================

@pytest.fixture
def expires_at_future():
    """Get a future expiration timestamp."""
    return (datetime.now() + timedelta(hours=1)).timestamp()


@pytest.fixture
def expires_at_past():
    """Get a past expiration timestamp."""
    return (datetime.now() - timedelta(hours=1)).timestamp()
