"""
Token management using MSAL for Microsoft Graph API.

Handles:
- Generating new access tokens from refresh tokens via MSAL
- Automatic token refresh on 401 errors
- Encrypting/decrypting tokens for DB storage
- Persisting refreshed tokens back to the database
"""
from __future__ import annotations

import logging
import time
from typing import Optional, Tuple

import msal
from cryptography.fernet import Fernet
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from exceptions import TokenExpiredError, TokenDecryptionError

logger = logging.getLogger(__name__)


class TokenManager:
    """Manages MSAL-based token acquisition, refresh, encryption and DB persistence."""

    GRAPH_SCOPES = ["https://graph.microsoft.com/.default"]

    def __init__(self):
        self._fernet = Fernet(settings.encryption_key.encode())
        self._msal_app = msal.ConfidentialClientApplication(
            client_id=settings.client_id,
            client_credential=settings.client_secret,
            authority=f"https://login.microsoftonline.com/{settings.tenant_id}",
        )

    # ------------------------------------------------------------------
    # Encryption helpers
    # ------------------------------------------------------------------
    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string using Fernet."""
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a Fernet-encrypted string."""
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except Exception as exc:
            raise TokenDecryptionError(f"Failed to decrypt token: {exc}") from exc

    # ------------------------------------------------------------------
    # MSAL token operations
    # ------------------------------------------------------------------
    def acquire_token_by_refresh_token(self, refresh_token: str) -> dict:
        """
        Use MSAL to exchange a refresh token for a new access + refresh token pair.

        Returns the raw MSAL result dict which contains:
            access_token, refresh_token, expires_in, id_token, …

        Raises:
            TokenExpiredError: if the refresh token is invalid / expired.
        """
        result = self._msal_app.acquire_token_by_refresh_token(
            refresh_token,
            scopes=self.GRAPH_SCOPES,
        )
        if "error" in result:
            error_desc = result.get("error_description", result.get("error"))
            logger.error("msal_token_refresh_failed: %s", error_desc)
            raise TokenExpiredError(f"Token refresh failed: {error_desc}")

        logger.info("msal_token_refreshed successfully")
        return result

    def refresh_tokens(self, encrypted_refresh_token: str) -> Tuple[str, str, float]:
        """
        High-level helper: decrypt refresh token → MSAL refresh → return new tokens.

        Returns:
            (new_access_token, new_encrypted_refresh_token, expires_at)
        """
        refresh_token = self.decrypt(encrypted_refresh_token)
        result = self.acquire_token_by_refresh_token(refresh_token)

        new_access_token: str = result["access_token"]
        new_refresh_token: str = result.get("refresh_token", refresh_token)
        expires_in: int = result.get("expires_in", 3600)
        expires_at = time.time() + expires_in

        encrypted_new_refresh = self.encrypt(new_refresh_token)
        return new_access_token, encrypted_new_refresh, expires_at

    # ------------------------------------------------------------------
    # DB persistence
    # ------------------------------------------------------------------
    async def persist_tokens(
        self,
        session: AsyncSession,
        user_id: str,
        access_token: str,
        encrypted_refresh_token: str,
        expires_at: float,
    ) -> None:
        """Save the refreshed tokens back to the user_tokens table."""
        from models import UserToken
        from datetime import datetime

        encrypted_access = self.encrypt(access_token)
        await session.execute(
            update(UserToken)
            .where(UserToken.user_id == user_id)
            .values(
                access_token=encrypted_access,
                refresh_token=encrypted_refresh_token,
                expires_at=expires_at,
                updated_at=datetime.utcnow().isoformat(),
            )
        )
        logger.info("tokens_persisted for user %s", user_id)

    # ------------------------------------------------------------------
    # Token validity check
    # ------------------------------------------------------------------
    @staticmethod
    def is_token_expired(expires_at: float, buffer_seconds: int = 300) -> bool:
        """Return True if the token expires within *buffer_seconds*."""
        return time.time() >= (expires_at - buffer_seconds)
