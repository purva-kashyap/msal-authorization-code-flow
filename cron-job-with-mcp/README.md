# Cron Job with MCP Tools

This folder contains an MCP-based version of your cron job implementation.

## What changed from `cron-job`
- Keeps the same processing flow and DB models.
- Replaces direct Graph and Zoom API HTTP calls with MCP tool calls.
- Uses separated service modules:
	- `services/mcp_client.py`
	- `services/teams_mcp_service.py`
	- `services/zoom_mcp_service.py`

## MCP tool expectations
The MCP server should expose tools compatible with the names in `config.py`:
- Teams list meetings: `teams_list_recorded_meetings`
- Teams get transcript: `teams_get_meeting_transcript`
- Teams post chat: `teams_post_chat_message`
- Zoom list recordings: `zoom_list_recordings`
- Zoom get transcript: `zoom_get_meeting_transcript`
- Zoom post chat: `zoom_post_chat_message`

You can override tool names using env vars:
- `MCP_TEAMS_LIST_MEETINGS_TOOL`
- `MCP_TEAMS_GET_TRANSCRIPT_TOOL`
- `MCP_TEAMS_POST_CHAT_TOOL`
- `MCP_ZOOM_LIST_RECORDINGS_TOOL`
- `MCP_ZOOM_GET_TRANSCRIPT_TOOL`
- `MCP_ZOOM_POST_CHAT_TOOL`

## Required environment variables

```bash
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/entra_tokens
ENCRYPTION_KEY=your-fernet-key
MCP_SERVER_URL=http://localhost:8001/mcp
MCP_AUTH_TOKEN=
MCP_TIMEOUT_SECONDS=60
MCP_MAX_CONCURRENCY=50
MCP_MAX_CONNECTIONS=200
MCP_MAX_KEEPALIVE_CONNECTIONS=100

# Optional
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
LOOKBACK_HOURS=24
MAX_MEETINGS_PER_USER=50
DEBUG=false
```

## Run

```bash
pip install -r requirements.txt
python init_db.py
python cron_job.py
```

## High-scale notes (1000+ users)

- Current implementation reuses one `httpx.AsyncClient` with connection pooling for MCP calls.
- In-flight MCP requests are throttled with `MCP_MAX_CONCURRENCY`.
- Tune `MCP_MAX_CONCURRENCY` and `MCP_MAX_CONNECTIONS` based on MCP server capacity and DB load.
- If throughput is still low, next step is parallel user processing with bounded worker pools.
