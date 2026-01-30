"""
Token management service for database operations.
"""
from datetime import datetime
from sqlalchemy import select, func
from typing import Optional, Dict, List

from app.database import UserToken, get_db_session
from app.services.encryption import encrypt_token, decrypt_token


async def save_user_tokens(
    user_id: str,
    email: str,
    name: str,
    access_token: str,
    refresh_token: Optional[str],
    expires_at: float
) -> None:
    """
    Save or update user tokens in database.
    
    Args:
        user_id: Unique user identifier
        email: User email
        name: User display name
        access_token: OAuth access token
        refresh_token: OAuth refresh token (optional)
        expires_at: Token expiration timestamp
    """
    async with get_db_session() as session:
        now = datetime.now().isoformat()
        
        # Encrypt tokens
        encrypted_access = encrypt_token(access_token)
        encrypted_refresh = encrypt_token(refresh_token) if refresh_token else None
        
        # Check if user exists
        result = await session.execute(
            select(UserToken).where(UserToken.user_id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            # Update existing user
            user.email = email
            user.name = name
            user.access_token = encrypted_access
            user.refresh_token = encrypted_refresh
            user.expires_at = expires_at
            user.updated_at = now
        else:
            # Create new user
            user = UserToken(
                user_id=user_id,
                email=email,
                name=name,
                access_token=encrypted_access,
                refresh_token=encrypted_refresh,
                expires_at=expires_at,
                created_at=now,
                updated_at=now
            )
            session.add(user)
    
    print(f"✓ Tokens saved for user: {email}")


async def get_user_tokens(user_id: str) -> Optional[Dict]:
    """
    Retrieve user tokens from database.
    
    Args:
        user_id: Unique user identifier
        
    Returns:
        Dictionary with user data and decrypted tokens, or None if not found
    """
    async with get_db_session() as session:
        result = await session.execute(
            select(UserToken).where(UserToken.user_id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return None
        
        return {
            "user_id": user.user_id,
            "email": user.email,
            "name": user.name,
            "access_token": decrypt_token(user.access_token),
            "refresh_token": decrypt_token(user.refresh_token) if user.refresh_token else None,
            "expires_at": user.expires_at,
            "created_at": user.created_at,
            "updated_at": user.updated_at
        }


async def update_tokens(
    user_id: str,
    access_token: str,
    expires_at: float,
    refresh_token: Optional[str] = None
) -> None:
    """
    Update only the tokens for a user.
    
    Args:
        user_id: Unique user identifier
        access_token: New access token
        expires_at: New expiration timestamp
        refresh_token: New refresh token (optional)
    """
    async with get_db_session() as session:
        result = await session.execute(
            select(UserToken).where(UserToken.user_id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        encrypted_access = encrypt_token(access_token)
        now = datetime.now().isoformat()
        
        user.access_token = encrypted_access
        user.expires_at = expires_at
        user.updated_at = now
        
        if refresh_token:
            user.refresh_token = encrypt_token(refresh_token)


async def get_all_users() -> List[Dict]:
    """
    Get list of all users (for admin purposes).
    
    Returns:
        List of user information dictionaries
    """
    try:
        async with get_db_session() as session:
            result = await session.execute(
                select(
                    UserToken.user_id,
                    UserToken.email,
                    UserToken.name,
                    UserToken.created_at,
                    UserToken.updated_at
                ).order_by(UserToken.updated_at.desc())
            )
            users = result.all()
            
            return [
                {
                    "user_id": user.user_id,
                    "email": user.email,
                    "name": user.name,
                    "created_at": user.created_at,
                    "updated_at": user.updated_at
                }
                for user in users
            ]
    except Exception:
        # Return empty list if database is not available
        return []


async def delete_user_tokens(user_id: str) -> bool:
    """
    Delete user tokens from database.
    
    Args:
        user_id: Unique user identifier
        
    Returns:
        True if deleted, False if user not found
    """
    async with get_db_session() as session:
        result = await session.execute(
            select(UserToken).where(UserToken.user_id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            await session.delete(user)
            return True
        return False


async def get_user_count() -> int:
    """
    Get total number of registered users.
    
    Returns:
        Total user count
    """
    try:
        async with get_db_session() as session:
            result = await session.execute(select(func.count(UserToken.user_id)))
            return result.scalar()
    except Exception:
        # Return 0 if database is not available
        return 0
