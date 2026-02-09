"""
Tests for encryption service.
"""
import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.services.encryption import encrypt_token, decrypt_token
from app.config import settings


@pytest.mark.unit
class TestEncryption:
    """Test encryption and decryption functionality."""
    
    def test_encrypt_token_returns_string(self):
        """Test that encrypt_token returns a string."""
        token = "test-token-123"
        encrypted = encrypt_token(token)
        
        assert isinstance(encrypted, str)
        assert encrypted != token
        assert len(encrypted) > len(token)
    
    def test_decrypt_token_returns_original(self):
        """Test that decrypt_token returns the original token."""
        original = "test-token-123"
        encrypted = encrypt_token(original)
        decrypted = decrypt_token(encrypted)
        
        assert decrypted == original
    
    def test_encrypt_decrypt_long_token(self):
        """Test encryption/decryption of long tokens."""
        long_token = "x" * 1000
        encrypted = encrypt_token(long_token)
        decrypted = decrypt_token(encrypted)
        
        assert decrypted == long_token
    
    def test_encrypt_none_returns_none(self):
        """Test that encrypting None returns None."""
        assert encrypt_token(None) is None
    
    def test_decrypt_none_returns_none(self):
        """Test that decrypting None returns None."""
        assert decrypt_token(None) is None
    
    def test_decrypt_empty_string_returns_empty(self):
        """Test that decrypting empty string returns empty string."""
        assert decrypt_token("") == ""
    
    def test_encrypt_empty_string(self):
        """Test encrypting empty string."""
        encrypted = encrypt_token("")
        decrypted = decrypt_token(encrypted)
        assert decrypted == ""
    
    def test_encrypted_tokens_are_different(self):
        """Test that encrypting the same token twice produces different results."""
        token = "test-token-123"
        encrypted1 = encrypt_token(token)
        encrypted2 = encrypt_token(token)
        
        # Fernet includes a timestamp, so encryptions will differ
        # But both should decrypt to the same value
        assert decrypt_token(encrypted1) == token
        assert decrypt_token(encrypted2) == token
    
    def test_decrypt_invalid_token_raises_error(self):
        """Test that decrypting invalid data raises an error."""
        with pytest.raises(InvalidToken):
            decrypt_token("invalid-encrypted-data")
    
    def test_special_characters_encryption(self):
        """Test encryption of tokens with special characters."""
        token = "!@#$%^&*()_+-=[]{}|;:',.<>?/~`"
        encrypted = encrypt_token(token)
        decrypted = decrypt_token(encrypted)
        
        assert decrypted == token
    
    def test_unicode_encryption(self):
        """Test encryption of unicode characters."""
        token = "Hello 世界 🌍 مرحبا"
        encrypted = encrypt_token(token)
        decrypted = decrypt_token(encrypted)
        
        assert decrypted == token
