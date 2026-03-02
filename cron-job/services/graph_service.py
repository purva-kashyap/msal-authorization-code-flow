"""
Microsoft Graph API service for Teams meeting operations.

Handles:
- Listing recorded online meetings within a date range
- Downloading meeting transcripts
- Posting summary messages to meeting chats
- Automatic token refresh on 401 and rate-limit (429) back-off
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

from config import settings
from exceptions import (
    RateLimitError,
    TeamsAPIError,
    TokenExpiredError,
    TranscriptNotFoundError,
)
from rate_limiters import rate_limiters
from utils import async_retry

logger = logging.getLogger(__name__)

# Sentinel used by callers to know they should refresh the token
_TOKEN_EXPIRED_SENTINEL = object()


class GraphService:
    """
    Microsoft Graph API client.

    One instance per *user* per run — holds the current access token and
    exposes all Graph calls needed by the cron job.

    Rate Limiting Strategy
    ----------------------
    * **Pre-request throttle** via ``aiolimiter`` (``rate_limiters.graph``).
      Stays well under the tenant-level 10 000 req / 10 min budget by
      defaulting to ~100 req / 60 s.
    * **Reactive 429 handling**: if Graph returns 429 we read ``Retry-After``,
      sleep, and raise ``RateLimitError`` so the retry decorator can re-try.
    * **401 handling**: raises ``TokenExpiredError`` so the caller can
      transparently refresh the access token and retry the operation.
    """

    BASE_URL = "https://graph.microsoft.com/v1.0"
    DEFAULT_TIMEOUT = 30.0
    DOWNLOAD_TIMEOUT = 120.0  # longer timeout for transcript downloads

    def __init__(self, access_token: str):
        self._access_token = access_token
        self._client = httpx.AsyncClient(
            timeout=self.DEFAULT_TIMEOUT,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def close(self) -> None:
        await self._client.aclose()

    def update_token(self, new_access_token: str) -> None:
        """Hot-swap the access token after a refresh."""
        self._access_token = new_access_token
        self._client.headers["Authorization"] = f"Bearer {new_access_token}"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    async def _acquire_rate_limit(self) -> None:
        """Wait for a Graph rate-limit slot."""
        await rate_limiters.acquire_graph_limit()

    def _handle_error(self, error: httpx.HTTPStatusError, operation: str) -> None:
        """Translate HTTP errors into domain exceptions."""
        status = error.response.status_code
        if status == 401:
            raise TokenExpiredError(f"Access token expired during {operation}")
        if status == 429:
            retry_after = int(error.response.headers.get("Retry-After", 60))
            raise RateLimitError(
                f"Rate limit hit during {operation}, retry after {retry_after}s",
                retry_after=retry_after,
                platform="teams",
            )
        body = (error.response.text or "")[:500]
        raise TeamsAPIError(f"Graph {operation} failed ({status}): {body}", status_code=status)

    async def _paginate(
        self, url: str, params: Dict[str, Any], max_pages: int = 10
    ) -> List[Dict[str, Any]]:
        """Follow @odata.nextLink to collect all pages (up to *max_pages*)."""
        all_items: List[Dict[str, Any]] = []
        next_url: Optional[str] = url
        page = 0

        while next_url and page < max_pages:
            await self._acquire_rate_limit()
            try:
                if page == 0:
                    resp = await self._client.get(next_url, params=params)
                else:
                    # nextLink already contains query params
                    resp = await self._client.get(next_url)
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                self._handle_error(exc, "paginate")
                break

            data = resp.json()
            all_items.extend(data.get("value", []))
            next_url = data.get("@odata.nextLink")
            page += 1

        return all_items

    # ------------------------------------------------------------------
    # Meetings
    # ------------------------------------------------------------------
    async def get_online_meetings(
        self,
        since: Optional[datetime] = None,
        lookback_hours: int = 24,
    ) -> List[Dict[str, Any]]:
        """
        Fetch online meetings (calendar events that are online meetings).

        Automatically follows ``@odata.nextLink`` for pagination.

        Args:
            since: Fetch meetings from this timestamp. If ``None``, falls back
                   to ``lookback_hours`` from now.
            lookback_hours: Fallback look-back window.

        Returns:
            List of event dicts from the Graph ``/me/events`` response.
        """
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        start_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")

        url = f"{self.BASE_URL}/me/events"
        params = {
            "$filter": f"start/dateTime ge '{start_str}' and isOnlineMeeting eq true",
            "$select": "id,subject,start,end,onlineMeeting,organizer",
            "$top": 100,
            "$orderby": "start/dateTime desc",
        }

        meetings = await self._paginate(url, params, max_pages=10)
        logger.info("graph_meetings_fetched count=%d since=%s", len(meetings), start_str)
        return meetings

    # ------------------------------------------------------------------
    # Recordings & Transcripts
    # ------------------------------------------------------------------
    @async_retry(retry_on=(TeamsAPIError, ConnectionError, TimeoutError))
    async def get_call_recordings(self, meeting_id: str) -> List[Dict[str, Any]]:
        """Return recording metadata for an onlineMeeting."""
        await self._acquire_rate_limit()
        try:
            url = f"{self.BASE_URL}/me/onlineMeetings/{meeting_id}/recordings"
            resp = await self._client.get(url)
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            return resp.json().get("value", [])
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return []
            self._handle_error(exc, "get_call_recordings")
            return []

    @async_retry(retry_on=(TeamsAPIError, ConnectionError, TimeoutError))
    async def get_transcript(self, meeting_id: str, transcript_id: str) -> Optional[str]:
        """
        Download a transcript's content for a given online meeting.

        Uses ``/me/onlineMeetings/{meetingId}/transcripts/{transcriptId}/content``
        with ``$format=text/vtt`` to get plain-text captions.
        """
        await self._acquire_rate_limit()
        try:
            url = (
                f"{self.BASE_URL}/me/onlineMeetings/{meeting_id}"
                f"/transcripts/{transcript_id}/content"
            )
            params = {"$format": "text/vtt"}
            resp = await self._client.get(url, params=params, timeout=self.DOWNLOAD_TIMEOUT)
            if resp.status_code == 404:
                raise TranscriptNotFoundError(f"Transcript {transcript_id} not found")
            resp.raise_for_status()
            logger.info("graph_transcript_downloaded meeting=%s size=%d", meeting_id, len(resp.text))
            return resp.text
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise TranscriptNotFoundError(f"Transcript {transcript_id} not found")
            self._handle_error(exc, "get_transcript")
            return None

    @async_retry(retry_on=(TeamsAPIError, ConnectionError, TimeoutError))
    async def list_transcripts(self, meeting_id: str) -> List[Dict[str, Any]]:
        """List available transcripts for an online meeting."""
        await self._acquire_rate_limit()
        try:
            url = f"{self.BASE_URL}/me/onlineMeetings/{meeting_id}/transcripts"
            resp = await self._client.get(url)
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            return resp.json().get("value", [])
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return []
            self._handle_error(exc, "list_transcripts")
            return []

    # ------------------------------------------------------------------
    # Chat messaging
    # ------------------------------------------------------------------
    @async_retry(retry_on=(TeamsAPIError, ConnectionError, TimeoutError))
    async def post_message_to_chat(self, chat_id: str, message: str) -> bool:
        """Post an HTML/text message to a Teams chat."""
        await self._acquire_rate_limit()
        try:
            url = f"{self.BASE_URL}/chats/{chat_id}/messages"
            payload = {
                "body": {
                    "content": message,
                    "contentType": "html",
                }
            }
            resp = await self._client.post(url, json=payload)
            resp.raise_for_status()
            logger.info("graph_message_posted chat=%s", chat_id)
            return True
        except httpx.HTTPStatusError as exc:
            self._handle_error(exc, "post_message_to_chat")
            return False
