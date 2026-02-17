"""
Service for interacting with Microsoft Graph API to fetch Teams meeting recordings.
Includes retry logic, rate limiting, and comprehensive error handling.
"""
import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from logging_config import get_logger
from exceptions import TeamsAPIError, RateLimitError, TokenExpiredError, TranscriptNotFoundError
from utils import async_retry, safe_dict_get
from rate_limiters import rate_limiters
from monitoring import (
    api_requests_total,
    api_request_duration,
    transcript_downloads_total,
    record_error
)
import time

logger = get_logger(__name__)


class TeamsService:
    """Service to interact with Microsoft Graph API for Teams meetings."""
    
    GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"
    REQUEST_TIMEOUT = 30.0
    
    def __init__(self, access_token: str):
        """Initialize Teams service with access token."""
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        logger.debug("teams_service_initialized")
    
    def _handle_http_error(self, error: httpx.HTTPStatusError, operation: str) -> None:
        """
        Handle HTTP errors and raise appropriate exceptions.
        
        Args:
            error: HTTP status error
            operation: Operation that failed
            
        Raises:
            Appropriate exception based on status code
        """
        status_code = error.response.status_code
        
        api_requests_total.labels(
            platform="teams",
            endpoint=operation,
            status=f"error_{status_code}"
        ).inc()
        
        if status_code == 401:
            record_error("TokenExpiredError", "teams_service")
            raise TokenExpiredError(f"Access token expired for {operation}")
        elif status_code == 429:
            retry_after = int(error.response.headers.get("Retry-After", 60))
            record_error("RateLimitError", "teams_service")
            raise RateLimitError(
                f"Rate limit exceeded for {operation}",
                retry_after=retry_after,
                platform="teams"
            )
        elif status_code == 404:
            # 404 is often expected (no recordings, etc.)
            logger.debug(f"teams_api_404", operation=operation)
            raise TeamsAPIError(f"Resource not found: {operation}", status_code=404)
        else:
            record_error("TeamsAPIError", "teams_service")
            error_text = error.response.text[:500] if error.response.text else "No details"
            raise TeamsAPIError(
                f"API error in {operation}: {status_code} - {error_text}",
                status_code=status_code
            )
    
    @async_retry()
    async def get_online_meetings(self, lookback_hours: int = 24) -> List[Dict]:
        """
        Fetch online meetings from the last N hours with retry logic and rate limiting.
        
        Args:
            lookback_hours: Number of hours to look back
            
        Returns:
            List of meeting dictionaries
        """
        operation = "get_online_meetings"
        start_time_op = time.time()
        
        try:
            # Apply rate limiting
            await rate_limiters.acquire_graph_limit()
            
            # Calculate time range
            start_time = datetime.utcnow() - timedelta(hours=lookback_hours)
            start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            
            async with httpx.AsyncClient(timeout=self.REQUEST_TIMEOUT) as client:
                # Get user's calendar events
                url = f"{self.GRAPH_API_ENDPOINT}/me/events"
                params = {
                    "$filter": f"start/dateTime ge '{start_time_str}' and isOnlineMeeting eq true",
                    "$select": "id,subject,start,end,onlineMeeting,organizer",
                    "$top": 100,
                    "$orderby": "start/dateTime desc"
                }
                
                response = await client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                meetings = safe_dict_get(data, "value", default=[])
                
                # Record metrics
                api_requests_total.labels(
                    platform="teams",
                    endpoint=operation,
                    status="success"
                ).inc()
                
                api_request_duration.labels(
                    platform="teams",
                    endpoint=operation
                ).observe(time.time() - start_time_op)
                
                logger.info("teams_meetings_fetched", count=len(meetings), lookback_hours=lookback_hours)
                return meetings
                
        except httpx.HTTPStatusError as e:
            self._handle_http_error(e, operation)
            return []  # Unreachable but for type safety
        except httpx.TimeoutException as e:
            record_error("TimeoutError", "teams_service")
            logger.error("teams_api_timeout", operation=operation, error=str(e))
            raise TeamsAPIError(f"Timeout in {operation}")
        except Exception as e:
            record_error(type(e).__name__, "teams_service")
            logger.error("teams_api_error", operation=operation, error=str(e), error_type=type(e).__name__)
            raise TeamsAPIError(f"Unexpected error in {operation}: {str(e)}")
    
    @async_retry()
    async def get_call_recordings(self, meeting_id: str) -> List[Dict]:
        """
        Get recordings for a specific meeting with retry logic and rate limiting.
        
        Args:
            meeting_id: The meeting/event ID
            
        Returns:
            List of recording dictionaries
        """
        operation = "get_call_recordings"
        start_time = time.time()
        
        try:
            # Apply rate limiting
            await rate_limiters.acquire_graph_limit()
            
            async with httpx.AsyncClient(timeout=self.REQUEST_TIMEOUT) as client:
                # Note: This is a simplified version. Recordings might be in OneDrive/SharePoint
                url = f"{self.GRAPH_API_ENDPOINT}/me/onlineMeetings/{meeting_id}/recordings"
                
                response = await client.get(url, headers=self.headers)
                
                if response.status_code == 404:
                    logger.debug("teams_no_recordings", meeting_id=meeting_id)
                    return []
                
                response.raise_for_status()
                data = response.json()
                recordings = safe_dict_get(data, "value", default=[])
                
                # Record metrics
                api_requests_total.labels(
                    platform="teams",
                    endpoint=operation,
                    status="success"
                ).inc()
                
                api_request_duration.labels(
                    platform="teams",
                    endpoint=operation
                ).observe(time.time() - start_time)
                
                logger.info("teams_recordings_fetched", meeting_id=meeting_id, count=len(recordings))
                return recordings
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return []  # No recordings is not an error
            self._handle_http_error(e, operation)
            return []
        except Exception as e:
            record_error(type(e).__name__, "teams_service")
            logger.error("teams_recordings_error", meeting_id=meeting_id, error=str(e))
            raise TeamsAPIError(f"Error fetching recordings: {str(e)}")
    
    @async_retry()
    async def get_call_transcript(self, recording_id: str) -> Optional[str]:
        """
        Download transcript for a recording with retry logic and rate limiting.
        
        Args:
            recording_id: The recording ID
            
        Returns:
            Transcript text or None
            
        Raises:
            TranscriptNotFoundError: If transcript doesn't exist
        """
        operation = "get_call_transcript"
        start_time = time.time()
        
        try:
            # Apply rate limiting
            await rate_limiters.acquire_graph_limit()
            
            async with httpx.AsyncClient(timeout=60.0) as client:  # Longer timeout for downloads
                url = f"{self.GRAPH_API_ENDPOINT}/me/onlineMeetings/recordings/{recording_id}/content"
                
                response = await client.get(url, headers=self.headers)
                
                if response.status_code == 404:
                    transcript_downloads_total.labels(platform="teams", status="not_found").inc()
                    raise TranscriptNotFoundError(f"No transcript for recording {recording_id}")
                
                response.raise_for_status()
                transcript_text = response.text
                
                # Record metrics
                transcript_downloads_total.labels(platform="teams", status="success").inc()
                
                api_request_duration.labels(
                    platform="teams",
                    endpoint=operation
                ).observe(time.time() - start_time)
                
                logger.info("teams_transcript_downloaded", recording_id=recording_id, size=len(transcript_text))
                return transcript_text
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                transcript_downloads_total.labels(platform="teams", status="not_found").inc()
                raise TranscriptNotFoundError(f"No transcript for recording {recording_id}")
            transcript_downloads_total.labels(platform="teams", status="error").inc()
            self._handle_http_error(e, operation)
            return None
        except Exception as e:
            transcript_downloads_total.labels(platform="teams", status="error").inc()
            record_error(type(e).__name__, "teams_service")
            logger.error("teams_transcript_error", recording_id=recording_id, error=str(e))
            raise TeamsAPIError(f"Error downloading transcript: {str(e)}")
    
    @async_retry()
    async def post_message_to_chat(self, chat_id: str, message: str) -> bool:
        """
        Post a message to a Teams chat with retry logic and rate limiting.
        
        Args:
            chat_id: The chat ID
            message: Message to post
            
        Returns:
            True if successful, False otherwise
        """
        operation = "post_message_to_chat"
        start_time = time.time()
        
        try:
            # Apply rate limiting
            await rate_limiters.acquire_graph_limit()
            
            async with httpx.AsyncClient(timeout=self.REQUEST_TIMEOUT) as client:
                url = f"{self.GRAPH_API_ENDPOINT}/chats/{chat_id}/messages"
                
                payload = {
                    "body": {
                        "content": message,
                        "contentType": "text"
                    }
                }
                
                response = await client.post(url, headers=self.headers, json=payload)
                response.raise_for_status()
                
                # Record metrics
                api_requests_total.labels(
                    platform="teams",
                    endpoint=operation,
                    status="success"
                ).inc()
                
                api_request_duration.labels(
                    platform="teams",
                    endpoint=operation
                ).observe(time.time() - start_time)
                
                logger.info("teams_message_posted", chat_id=chat_id)
                return True
                
        except httpx.HTTPStatusError as e:
            self._handle_http_error(e, operation)
            return False
        except Exception as e:
            record_error(type(e).__name__, "teams_service")
            logger.error("teams_post_message_error", chat_id=chat_id, error=str(e))
            return False
