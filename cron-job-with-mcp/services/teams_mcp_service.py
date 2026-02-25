"""
Teams operations executed via MCP tools.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import settings
from services.mcp_client import MCPClient


class TeamsMCPService:
    """Teams operations executed via MCP tools."""

    def __init__(self, mcp_client: MCPClient):
        self.mcp = mcp_client

    async def get_online_meetings(self, access_token: str, lookback_hours: int) -> List[Dict[str, Any]]:
        result = await self.mcp.call_tool(
            settings.mcp_teams_list_meetings_tool,
            {
                "access_token": access_token,
                "lookback_hours": lookback_hours,
            },
        )
        return result.get("meetings", result.get("items", []))

    async def get_call_transcript(self, access_token: str, meeting_id: str) -> Optional[str]:
        result = await self.mcp.call_tool(
            settings.mcp_teams_get_transcript_tool,
            {
                "access_token": access_token,
                "meeting_id": meeting_id,
            },
        )
        return result.get("transcript")

    async def post_message_to_chat(self, access_token: str, chat_id: str, message: str) -> bool:
        result = await self.mcp.call_tool(
            settings.mcp_teams_post_chat_tool,
            {
                "access_token": access_token,
                "chat_id": chat_id,
                "message": message,
            },
        )
        return bool(result.get("success", False))
