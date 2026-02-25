"""
User-related database models.
"""
from sqlalchemy import Column, String, Float
from models.base import Base


class UserToken(Base):
    """User token model shared with the main app."""

    __tablename__ = "user_tokens"

    user_id = Column(String(255), primary_key=True, index=True)
    email = Column(String(255), nullable=True, index=True)
    name = Column(String(255), nullable=True)
    access_token = Column(String(4096), nullable=False)
    refresh_token = Column(String(4096), nullable=True)
    expires_at = Column(Float, nullable=False)
    created_at = Column(String(50), nullable=False)
    updated_at = Column(String(50), nullable=False)
