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
        description="MCP server endpoint (SSE URL for FastMCP)",
    )

    mcp_teams_list_meetings_tool: str = "teams_list_recorded_meetings"
    mcp_teams_get_transcript_tool: str = "teams_get_meeting_transcript"
    mcp_teams_post_chat_tool: str = "teams_post_chat_message"

    mcp_zoom_list_recordings_tool: str = "zoom_list_recordings"
    mcp_zoom_get_transcript_tool: str = "zoom_get_meeting_transcript"
    mcp_zoom_post_chat_tool: str = "zoom_post_chat_message"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()
