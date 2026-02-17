"""
Service for generating meeting summaries using AI.
"""
import httpx
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class SummaryService:
    """Service to generate meeting summaries from transcripts."""
    
    OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        """Initialize summary service with OpenAI API key."""
        self.api_key = api_key
        self.model = model
    
    def _create_summary_prompt(self, transcript: str, meeting_title: str = "Meeting") -> str:
        """
        Create a prompt for summarizing the meeting.
        
        Args:
            transcript: The meeting transcript
            meeting_title: The meeting title
            
        Returns:
            Formatted prompt string
        """
        return f"""Please provide a concise summary of the following meeting transcript.

Meeting: {meeting_title}

Include:
1. Key discussion points
2. Decisions made
3. Action items (if any)
4. Important takeaways

Transcript:
{transcript}

Please format the summary in a clear, professional manner suitable for posting in a chat."""
    
    async def generate_summary(self, transcript: str, meeting_title: str = "Meeting") -> Optional[str]:
        """
        Generate a summary from a meeting transcript using OpenAI.
        
        Args:
            transcript: The meeting transcript text
            meeting_title: The meeting title
            
        Returns:
            Summary text or None if generation fails
        """
        try:
            if not transcript or not transcript.strip():
                logger.warning("Empty transcript provided")
                return None
            
            prompt = self._create_summary_prompt(transcript, meeting_title)
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a helpful assistant that creates concise, professional meeting summaries."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1000
                }
                
                response = await client.post(
                    self.OPENAI_API_URL,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                summary = data["choices"][0]["message"]["content"]
                
                logger.info(f"Successfully generated summary for '{meeting_title}'")
                return summary
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error generating summary: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return None
    
    def format_summary_message(self, meeting_title: str, summary: str, platform: str) -> str:
        """
        Format the summary for posting to chat.
        
        Args:
            meeting_title: The meeting title
            summary: The generated summary
            platform: 'teams' or 'zoom'
            
        Returns:
            Formatted message string
        """
        emoji = "📊" if platform == "teams" else "🎥"
        
        message = f"""{emoji} **Meeting Summary: {meeting_title}**

{summary}

---
_This summary was automatically generated from the meeting recording._
"""
        return message
