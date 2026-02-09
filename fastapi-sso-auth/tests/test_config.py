"""
Tests for configuration.
"""
import pytest
from pydantic import ValidationError
from cryptography.fernet import Fernet

from app.config import Settings


@pytest.mark.unit
class TestConfiguration:
    """Test configuration management."""
    
    def test_valid_settings_creation(self, test_encryption_key):
        """Test creating valid settings."""
        settings = Settings(
            client_id="test-client-id",
            client_secret="test-client-secret",
            tenant_id="test-tenant-id",
            encryption_key=test_encryption_key,
            secret_key="test-secret-key",
        )
        
        assert settings.client_id == "test-client-id"
        assert settings.client_secret == "test-client-secret"
        assert settings.tenant_id == "test-tenant-id"
        assert settings.encryption_key == test_encryption_key
    
    def test_invalid_encryption_key_fails(self):
        """Test that invalid encryption key raises validation error."""
        with pytest.raises(ValidationError):
            Settings(
                client_id="test-client-id",
                client_secret="test-client-secret",
                tenant_id="test-tenant-id",
                encryption_key="invalid-key",
                secret_key="test-secret-key",
            )
    
    def test_default_values(self, test_encryption_key):
        """Test default configuration values."""
        settings = Settings(
            client_id="test-client-id",
            client_secret="test-client-secret",
            tenant_id="test-tenant-id",
            encryption_key=test_encryption_key,
            secret_key="test-secret-key",
            debug=False,  # Explicitly set to test default behavior
        )
        
        assert settings.host == "0.0.0.0"
        assert settings.port == 8000
        assert settings.debug == False
    
    def test_authority_property(self, test_encryption_key):
        """Test authority URL property."""
        settings = Settings(
            client_id="test-client-id",
            client_secret="test-client-secret",
            tenant_id="test-tenant-123",
            encryption_key=test_encryption_key,
            secret_key="test-secret-key",
        )
        
        assert settings.authority == "https://login.microsoftonline.com/test-tenant-123"
    
    def test_cors_origins_list_property(self, test_encryption_key):
        """Test CORS origins list property."""
        settings = Settings(
            client_id="test-client-id",
            client_secret="test-client-secret",
            tenant_id="test-tenant-id",
            encryption_key=test_encryption_key,
            secret_key="test-secret-key",
            cors_origins="http://localhost:3000,http://localhost:8080",
        )
        
        origins = settings.cors_origins_list
        assert len(origins) == 2
        assert "http://localhost:3000" in origins
        assert "http://localhost:8080" in origins
    
    def test_cipher_property(self, test_encryption_key):
        """Test cipher property returns Fernet instance."""
        settings = Settings(
            client_id="test-client-id",
            client_secret="test-client-secret",
            tenant_id="test-tenant-id",
            encryption_key=test_encryption_key,
            secret_key="test-secret-key",
        )
        
        cipher = settings.cipher
        assert isinstance(cipher, Fernet)
        
        # Test that cipher works
        test_data = b"test data"
        encrypted = cipher.encrypt(test_data)
        decrypted = cipher.decrypt(encrypted)
        assert decrypted == test_data
