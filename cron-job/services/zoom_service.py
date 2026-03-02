"""
Zoom API service for meeting recordings and transcripts.

Uses Zoom Server-to-Server OAuth (account-level credentials).

Handles:
- Obtaining S2S access tokens
- Listing cloud recordings within a date range
- Downloading meeting transcripts
- Rate-limit back-off (429 / Retry-After)
"""
from __future__ import annotations

import base64
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

from config import settings
from exceptions import RateLimitError, ZoomAPIError
from rate_limiters import rate_limiters
from utils import async_retry

logger = logging.getLogger(__name__)


class ZoomService:
    """Zoom API client (Server-to-Server OAuth)."""

    API_BASE = "https://api.zoom.us/v2"
    OAUTH_URL = "https://zoom.us/oauth/token"
    DEFAULT_TIMEOUT = 30.0
    DOWNLOAD_TIMEOUT = 120.0

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        account_id: str,
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self._account_id = account_id
        self._access_token: Optional[str] = None
        self._client = httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------
    async def _get_access_token(self) -> str:
        """Obtain a Server-to-Server OAuth access token."""
        creds = f"{self._client_id}:{self._client_secret}"
        encoded = base64.b64encode(creds.encode()).decode()

        resp = await self._client.post(
            self.OAUTH_URL,
            params={
                "grant_type": "account_credentials",
                "account_id": self._account_id,
            },
            headers={
                "Authorization": f"Basic {encoded}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        logger.info("zoom_token_acquired")
        return self._access_token

    async def _ensure_token(self) -> None:
        if not self._access_token:
            await self._get_access_token()

    @property
    def _auth_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------
    def _handle_error(self, exc: httpx.HTTPStatusError, operation: str) -> None:
        status = exc.response.status_code
        if status == 401:
            # Token might be expired — clear it so next call re-acquires
            self._access_token = None
            raise ZoomAPIError(f"Zoom auth failed during {operation}", status_code=401)
        if status == 429:
            retry_after = int(exc.response.headers.get("Retry-After", 60))
            raise RateLimitError(
                f"Zoom rate limit during {operation}",
                retry_after=retry_after,
                platform="zoom",
            )
        body = (exc.response.text or "")[:500]
        raise ZoomAPIError(f"Zoom {operation} failed ({status}): {body}", status_code=status)

    # ------------------------------------------------------------------
    # Recordings
    # ------------------------------------------------------------------
    @async_retry(retry_on=(ZoomAPIError, ConnectionError, TimeoutError))
    async def get_recordings(
        self,
        user_id: str = "me",
        since: Optional[datetime] = None,
        lookback_hours: int = 24,
    ) -> List[Dict[str, Any]]:
        """
        List cloud recordings for a user.

        Args:
            user_id: Zoom user ID or email. ``"me"`` for S2S defaults to the
                     account-level scope.
            since: Start of date range. Falls back to ``lookback_hours``.
            lookback_hours: Fallback look-back window.
        """
        await self._ensure_token()
        await rate_limiters.acquire_zoom_recording_limit()

        end_date = datetime.now(timezone.utc)
        start_date = since or (end_date - timedelta(hours=lookback_hours))

        try:
            resp = await self._client.get(
                f"{self.API_BASE}/users/{user_id}/recordings",
                headers=self._auth_headers,
                params={
                    "from": start_date.strftime("%Y-%m-%d"),
                    "to": end_date.strftime("%Y-%m-%d"),
                    "page_size": 100,
                },
            )
            resp.raise_for_status()
            meetings = resp.json().get("meetings", [])
            logger.info("zoom_recordings_fetched count=%d", len(meetings))
            return meetings
        except httpx.HTTPStatusError as exc:
            self._handle_error(exc, "get_recordings")
            return []

    # ------------------------------------------------------------------
    # Transcripts
    # ------------------------------------------------------------------
    @async_retry(retry_on=(ZoomAPIError, ConnectionError, TimeoutError))
    async def get_meeting_transcript(self, meeting_id: str) -> Optional[str]:
        """Download the transcript file for a Zoom recording."""
        await self._ensure_token()
        await rate_limiters.acquire_zoom_recording_limit()

        try:
            # Get meeting recordings to find the transcript file
            resp = await self._client.get(
                f"{self.API_BASE}/meetings/{meeting_id}/recordings",
                headers=self._auth_headers,
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()

            recording_files = resp.json().get("recording_files", [])
            transcript_file = next(
                (
                    f
                    for f in recording_files
                    if f.get("file_type") == "TRANSCRIPT"
                    or f.get("recording_type") == "audio_transcript"
                ),
                None,
            )
            if not transcript_file:
                logger.info("zoom_no_transcript meeting=%s", meeting_id)
                return None

            download_url = transcript_file.get("download_url")
            if not download_url:
                return None

            await rate_limiters.acquire_zoom_recording_limit()
            dl_resp = await self._client.get(
                download_url,
                headers={"Authorization": f"Bearer {self._access_token}"},
                timeout=self.DOWNLOAD_TIMEOUT,
            )
            dl_resp.raise_for_status()
            logger.info("zoom_transcript_downloaded meeting=%s size=%d", meeting_id, len(dl_resp.text))
            return dl_resp.text

        except httpx.HTTPStatusError as exc:
            self._handle_error(exc, "get_meeting_transcript")
            return None
