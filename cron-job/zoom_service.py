"""
Service for interacting with Zoom API to fetch meeting recordings.
"""
import httpx
import base64
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class ZoomService:
    """Service to interact with Zoom API for meeting recordings."""
    
    ZOOM_API_BASE = "https://api.zoom.us/v2"
    ZOOM_OAUTH_URL = "https://zoom.us/oauth/token"
    
    def __init__(self, client_id: str, client_secret: str, account_id: str):
        """Initialize Zoom service with OAuth credentials."""
        self.client_id = client_id
        self.client_secret = client_secret
        self.account_id = account_id
        self.access_token: Optional[str] = None
    
    async def _get_access_token(self) -> str:
        """
        Get Server-to-Server OAuth access token.
        
        Returns:
            Access token string
        """
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.ZOOM_OAUTH_URL}?grant_type=account_credentials&account_id={self.account_id}"
                
                # Create basic auth header
                credentials = f"{self.client_id}:{self.client_secret}"
                encoded_credentials = base64.b64encode(credentials.encode()).decode()
                
                headers = {
                    "Authorization": f"Basic {encoded_credentials}",
                    "Content-Type": "application/x-www-form-urlencoded"
                }
                
                response = await client.post(url, headers=headers)
                response.raise_for_status()
                
                data = response.json()
                self.access_token = data.get("access_token")
                
                logger.info("Successfully obtained Zoom access token")
                return self.access_token
                
        except Exception as e:
            logger.error(f"Error getting Zoom access token: {str(e)}")
            raise
    
    async def _ensure_token(self):
        """Ensure we have a valid access token."""
        if not self.access_token:
            await self._get_access_token()
    
    async def get_recordings(self, user_id: str = "me", lookback_hours: int = 24) -> List[Dict]:
        """
        Get cloud recordings for a user.
        
        Args:
            user_id: Zoom user ID or 'me' for authenticated user
            lookback_hours: Number of hours to look back
            
        Returns:
            List of recording dictionaries
        """
        try:
            await self._ensure_token()
            
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(hours=lookback_hours)
            
            async with httpx.AsyncClient() as client:
                url = f"{self.ZOOM_API_BASE}/users/{user_id}/recordings"
                
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json"
                }
                
                params = {
                    "from": start_date.strftime("%Y-%m-%d"),
                    "to": end_date.strftime("%Y-%m-%d"),
                    "page_size": 100
                }
                
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                meetings = data.get("meetings", [])
                
                logger.info(f"Found {len(meetings)} Zoom recordings")
                return meetings
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching Zoom recordings: {e.response.status_code} - {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"Error fetching Zoom recordings: {str(e)}")
            return []
    
    async def get_meeting_transcript(self, meeting_id: str) -> Optional[str]:
        """
        Download transcript for a meeting.
        
        Args:
            meeting_id: The Zoom meeting ID
            
        Returns:
            Transcript text or None
        """
        try:
            await self._ensure_token()
            
            async with httpx.AsyncClient() as client:
                # First, get the meeting details to find transcript file
                url = f"{self.ZOOM_API_BASE}/meetings/{meeting_id}/recordings"
                
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json"
                }
                
                response = await client.get(url, headers=headers)
                
                if response.status_code == 404:
                    logger.info(f"No recordings found for meeting {meeting_id}")
                    return None
                
                response.raise_for_status()
                data = response.json()
                
                # Find transcript file
                recording_files = data.get("recording_files", [])
                transcript_file = None
                
                for file in recording_files:
                    if file.get("file_type") == "TRANSCRIPT" or file.get("recording_type") == "audio_transcript":
                        transcript_file = file
                        break
                
                if not transcript_file:
                    logger.info(f"No transcript file found for meeting {meeting_id}")
                    return None
                
                # Download transcript
                download_url = transcript_file.get("download_url")
                if not download_url:
                    logger.warning(f"No download URL for transcript in meeting {meeting_id}")
                    return None
                
                # Download the transcript file
                download_response = await client.get(
                    download_url,
                    headers={"Authorization": f"Bearer {self.access_token}"}
                )
                download_response.raise_for_status()
                
                transcript_text = download_response.text
                
                logger.info(f"Downloaded transcript for meeting {meeting_id}")
                return transcript_text
                
        except httpx.HTTPStatusError as e:
            logger.warning(f"Error fetching transcript for {meeting_id}: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Error fetching transcript: {str(e)}")
            return None
    
    async def post_chat_message(self, meeting_id: str, message: str) -> bool:
        """
        Post a message to a Zoom meeting chat.
        Note: This requires the meeting to be in progress or use Zoom Chat API.
        
        Args:
            meeting_id: The meeting ID
            message: Message to post
            
        Returns:
            True if successful, False otherwise
        """
        try:
            await self._ensure_token()
            
            async with httpx.AsyncClient() as client:
                # Note: Posting to meeting chat is limited. 
                # You might need to use Zoom Chat API to send to a channel instead
                url = f"{self.ZOOM_API_BASE}/chat/users/me/messages"
                
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "message": message,
                    # Additional fields needed based on chat type
                }
                
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                
                logger.info(f"Successfully posted message for meeting {meeting_id}")
                return True
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Error posting message: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Error posting message: {str(e)}")
            return False
