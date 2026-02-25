"""
JSON-RPC MCP client.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

import httpx

from config import settings
from exceptions import MCPToolError


class MCPClient:
    """Reusable JSON-RPC client for MCP tool calls with pooling and throttling."""

    def __init__(self, server_url: str, auth_token: Optional[str] = None):
        self.server_url = server_url
        self.auth_token = auth_token
        self._request_id = 0
        self._id_lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(settings.mcp_max_concurrency)
        self._client = httpx.AsyncClient(
            timeout=settings.mcp_timeout_seconds,
            limits=httpx.Limits(
                max_connections=settings.mcp_max_connections,
                max_keepalive_connections=settings.mcp_max_keepalive_connections,
            ),
        )

    async def aclose(self) -> None:
        """Close underlying HTTP client."""
        await self._client.aclose()

    async def _next_request_id(self) -> int:
        async with self._id_lock:
            self._request_id += 1
            return self._request_id

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a single MCP tool via JSON-RPC."""
        request_id = await self._next_request_id()
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }

        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        async with self._semaphore:
            try:
                response = await self._client.post(self.server_url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPError as exc:
                raise MCPToolError(f"MCP tool '{tool_name}' HTTP error: {exc}") from exc

        if "error" in data:
            raise MCPToolError(f"MCP tool '{tool_name}' failed: {data['error']}")

        result = data.get("result", data)
        if isinstance(result, dict):
            return result
        return {"data": result}
