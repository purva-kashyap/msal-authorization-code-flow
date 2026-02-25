"""
Configuration for MCP-based cron job service.
"""
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/entra_tokens"
    )
    encryption_key: str = Field(..., description="Fernet encryption key shared with main app")

    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"

    lookback_hours: int = 24
    max_meetings_per_user: int = 50
    debug: bool = False

    mcp_server_url: str = Field(
        default="http://localhost:8001/mcp",
        description="MCP server endpoint that exposes Teams/Zoom tools",
    )
    mcp_auth_token: Optional[str] = Field(
        default=None,
        description="Optional bearer token for MCP server",
    )

    mcp_teams_list_meetings_tool: str = "teams_list_recorded_meetings"
    mcp_teams_get_transcript_tool: str = "teams_get_meeting_transcript"
    mcp_teams_post_chat_tool: str = "teams_post_chat_message"

    mcp_zoom_list_recordings_tool: str = "zoom_list_recordings"
    mcp_zoom_get_transcript_tool: str = "zoom_get_meeting_transcript"
    mcp_zoom_post_chat_tool: str = "zoom_post_chat_message"

    mcp_timeout_seconds: float = Field(
        default=60.0,
        description="HTTP timeout used for MCP tool calls",
    )
    mcp_max_concurrency: int = Field(
        default=50,
        description="Max in-flight MCP requests from this process",
    )
    mcp_max_connections: int = Field(
        default=200,
        description="HTTP connection pool max connections for MCP server",
    )
    mcp_max_keepalive_connections: int = Field(
        default=100,
        description="HTTP keep-alive pool size for MCP server",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()
