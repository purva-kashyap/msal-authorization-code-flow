"""
Encryption utilities for token storage.
"""
from app.config import settings


def encrypt_token(token: str) -> str | None:
    """
    Encrypt a token for secure storage.
    
    Args:
        token: Plain text token
        
    Returns:
        Encrypted token as string
    """
    if token is None:
        return None
    if token == "":
        return ""
    return settings.cipher.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str | None:
    """
    Decrypt a token from storage.
    
    Args:
        encrypted_token: Encrypted token string
        
    Returns:
        Decrypted plain text token
    """
    if encrypted_token is None:
        return None
    if encrypted_token == "":
        return ""
    return settings.cipher.decrypt(encrypted_token.encode()).decode()
