"""
Configuration management using Pydantic Settings.
All secrets loaded from environment variables.
"""
from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import List
from cryptography.fernet import Fernet


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Microsoft Entra ID Configuration
    client_id: str = Field(..., description="Azure AD Application (client) ID")
    client_secret: str = Field(..., description="Azure AD Client Secret")
    tenant_id: str = Field(..., description="Azure AD Tenant ID")
    redirect_uri: str = Field(
        default="http://localhost:8000/auth/callback",
        description="OAuth2 redirect URI"
    )
    
    # Scopes
    scopes: List[str] = Field(
        default=["https://graph.microsoft.com/.default"],
        description="Microsoft Graph API scopes"
    )
    
    # Database Configuration
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/entra_tokens",
        description="PostgreSQL database URL for async connections"
    )
    
    # Encryption
    encryption_key: str = Field(..., description="Fernet encryption key for token storage")
    
    # Application Security
    secret_key: str = Field(..., description="Secret key for session management")
    
    # Server Configuration
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    debug: bool = Field(default=False, description="Debug mode")
    
    # CORS
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        description="Allowed CORS origins"
    )
    
    # Rate Limiting
    rate_limit_per_minute: int = Field(default=60, description="API rate limit per minute")
    
    # Token Configuration
    token_refresh_threshold_seconds: int = Field(
        default=300,
        description="Refresh token if expires in less than this many seconds"
    )
    
    @validator("encryption_key")
    def validate_encryption_key(cls, v):
        """Validate that encryption key is valid Fernet key."""
        try:
            Fernet(v.encode() if isinstance(v, str) else v)
            return v
        except Exception:
            raise ValueError("Invalid encryption key. Generate using: Fernet.generate_key().decode()")
    
    @property
    def authority(self) -> str:
        """Get Microsoft authority URL."""
        return f"https://login.microsoftonline.com/{self.tenant_id}"
    
    @property
    def cipher(self) -> Fernet:
        """Get Fernet cipher instance."""
        key = self.encryption_key.encode() if isinstance(self.encryption_key, str) else self.encryption_key
        return Fernet(key)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()
