"""
Configuration for the cron job service with proper secrets management.
"""
import os
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import Optional
from pathlib import Path


class Settings(BaseSettings):
    """Cron job configuration settings with secrets management support."""
    
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/entra_tokens",
        description="PostgreSQL database URL"
    )
    
    # Encryption key (shared with main app)
    encryption_key: str = Field(..., description="Fernet encryption key for token decryption")
    
    # Microsoft Graph API
    client_id: str = Field(..., description="Azure AD Application (client) ID")
    client_secret: str = Field(..., description="Azure AD Client Secret")
    tenant_id: str = Field(..., description="Azure AD Tenant ID")
    
    # Zoom API
    zoom_client_id: Optional[str] = Field(None, description="Zoom OAuth Client ID")
    zoom_client_secret: Optional[str] = Field(None, description="Zoom OAuth Client Secret")
    zoom_account_id: Optional[str] = Field(None, description="Zoom Account ID")
    
    # OpenAI for summarization
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key for summary generation")
    openai_model: str = Field(default="gpt-4o-mini", description="OpenAI model to use")
    
    # Processing settings
    lookback_hours: int = Field(default=24, description="Hours to look back for new meetings")
    max_meetings_per_user: int = Field(default=50, description="Max meetings to process per user per run")
    
    # Retry settings
    max_retries: int = Field(default=3, description="Maximum number of retries for failed operations")
    retry_backoff_base: float = Field(default=2.0, description="Base for exponential backoff")
    retry_max_wait: int = Field(default=60, description="Maximum wait time between retries in seconds")
    
    # Rate limiting
    graph_api_rate_limit: int = Field(default=100, description="Microsoft Graph API rate limit per minute")
    zoom_api_rate_limit: int = Field(default=60, description="Zoom API rate limit per second")
    openai_rate_limit: int = Field(default=10, description="OpenAI API rate limit per minute")
    
    # Debug
    debug: bool = Field(default=False, description="Enable debug logging")
    
    # Secrets file path (optional, for file-based secrets)
    secrets_file: Optional[Path] = Field(None, description="Path to secrets file")
    
    @field_validator("encryption_key")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        """Validate encryption key format."""
        if not v or len(v) < 32:
            raise ValueError("Encryption key must be at least 32 characters")
        return v
    
    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL uses asyncpg."""
        if "postgresql+" in v and "asyncpg" not in v:
            raise ValueError("Database URL must use asyncpg driver for async support")
        return v
    
    @property
    def is_zoom_configured(self) -> bool:
        """Check if Zoom API is configured."""
        return all([self.zoom_client_id, self.zoom_client_secret, self.zoom_account_id])
    
    @property
    def is_openai_configured(self) -> bool:
        """Check if OpenAI is configured."""
        return self.openai_api_key is not None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


def load_settings() -> Settings:
    """
    Load settings with support for multiple secret sources.
    Priority: Environment variables > Secrets file > .env file
    """
    # For production, you could add support for:
    # - AWS Secrets Manager
    # - Azure Key Vault  
    # - HashiCorp Vault
    # - Kubernetes Secrets
    
    # Example: Load from AWS Secrets Manager (commented out)
    # if os.getenv("USE_AWS_SECRETS"):
    #     from aws_secrets import get_secret
    #     secrets = get_secret("cron-job-secrets")
    #     for key, value in secrets.items():
    #         os.environ[key.upper()] = value
    
    # Example: Load from Azure Key Vault (commented out)
    # if os.getenv("USE_AZURE_KEYVAULT"):
    #     from azure_keyvault import get_secrets
    #     secrets = get_secrets()
    #     for key, value in secrets.items():
    #         os.environ[key.upper()] = value
    
    return Settings()


# Global settings instance
settings = load_settings()
