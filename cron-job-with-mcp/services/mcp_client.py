"""
FastMCP-based MCP client.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from fastmcp import Client

from config import settings
from exceptions import MCPToolError

logger = logging.getLogger(__name__)


class MCPClient:
    """MCP client using FastMCP's Client with SSE transport."""

    def __init__(self, server_url: str):
        self.server_url = server_url
        self._client = Client(server_url)
        self._connected = False

    async def connect(self) -> None:
        """Open the connection to the MCP server."""
        if not self._connected:
            await self._client.__aenter__()
            self._connected = True
            logger.info("Connected to MCP server at %s", self.server_url)

    async def aclose(self) -> None:
        """Close the connection to the MCP server."""
        if self._connected:
            await self._client.__aexit__(None, None, None)
            self._connected = False
            logger.info("Disconnected from MCP server")

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a single MCP tool via FastMCP client."""
        if not self._connected:
            await self.connect()

        try:
            result = await self._client.call_tool(tool_name, arguments)
        except Exception as exc:
            raise MCPToolError(f"MCP tool '{tool_name}' error: {exc}") from exc

        # FastMCP call_tool returns a list of content objects.
        # Parse the first TextContent item as JSON, or return raw text.
        for content in result:
            if hasattr(content, "text"):
                try:
                    parsed = json.loads(content.text)
                    if isinstance(parsed, dict):
                        return parsed
                    return {"data": parsed}
                except (json.JSONDecodeError, TypeError):
                    return {"data": content.text}

        return {"data": result}
