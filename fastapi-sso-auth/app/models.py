"""
Pydantic models for request/response validation.
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class UserInfo(BaseModel):
    """User information model."""
    user_id: str
    email: Optional[str] = None
    name: Optional[str] = None


class TokenInfo(BaseModel):
    """Token information (masked for display)."""
    user_id: str
    email: Optional[str] = None
    name: Optional[str] = None
    access_token_preview: str = Field(..., description="First/last 20 chars of access token")
    refresh_token_preview: Optional[str] = Field(None, description="First/last 20 chars of refresh token")
    expires_at: float
    expires_in_seconds: int
    created_at: str
    updated_at: str


class TokenResponse(BaseModel):
    """Response after successful token operation."""
    message: str
    user: Optional[UserInfo] = None
    expires_in: Optional[int] = None


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    details: Optional[str] = None


class HealthCheck(BaseModel):
    """Health check response."""
    status: str
    database: str
    total_users: int
    timestamp: str


class UserList(BaseModel):
    """List of users for admin endpoint."""
    total_users: int
    users: list[UserInfo]
