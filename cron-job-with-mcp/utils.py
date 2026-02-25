"""
Utility functions for MCP-based cron job service.
"""
from cryptography.fernet import Fernet
from exceptions import TokenDecryptionError


class TokenDecryptor:
    """Utility class for decrypting user tokens."""

    def __init__(self, encryption_key: str):
        try:
            self.fernet = Fernet(encryption_key.encode())
        except Exception as exc:
            raise TokenDecryptionError(f"Invalid encryption key: {exc}") from exc

    def decrypt_token(self, encrypted_token: str) -> str:
        try:
            return self.fernet.decrypt(encrypted_token.encode()).decode()
        except Exception as exc:
            raise TokenDecryptionError(f"Failed to decrypt token: {exc}") from exc


def format_duration(seconds: float) -> str:
    """Format duration seconds to short human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours}h {minutes}m"
