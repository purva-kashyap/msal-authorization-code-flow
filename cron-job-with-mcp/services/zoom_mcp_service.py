"""
Zoom operations executed via MCP tools.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import settings
from services.mcp_client import MCPClient


class ZoomMCPService:
    """Zoom operations executed via MCP tools."""

    def __init__(self, mcp_client: MCPClient):
        self.mcp = mcp_client

    async def get_recordings(self, user_email: str, lookback_hours: int) -> List[Dict[str, Any]]:
        result = await self.mcp.call_tool(
            settings.mcp_zoom_list_recordings_tool,
            {
                "user_email": user_email,
                "lookback_hours": lookback_hours,
            },
        )
        return result.get("recordings", result.get("meetings", []))

    async def get_meeting_transcript(self, meeting_id: str) -> Optional[str]:
        result = await self.mcp.call_tool(
            settings.mcp_zoom_get_transcript_tool,
            {
                "meeting_id": meeting_id,
            },
        )
        return result.get("transcript")

    async def post_chat_message(self, meeting_id: str, message: str) -> bool:
        result = await self.mcp.call_tool(
            settings.mcp_zoom_post_chat_tool,
            {
                "meeting_id": meeting_id,
                "message": message,
            },
        )
        return bool(result.get("success", False))
