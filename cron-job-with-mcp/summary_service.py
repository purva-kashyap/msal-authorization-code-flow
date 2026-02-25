"""
Service for generating meeting summaries using OpenAI Chat Completions API.
"""
from typing import Optional
import httpx


class SummaryService:
    """Generate meeting summaries from transcripts."""

    OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model

    async def generate_summary(self, transcript: str, meeting_title: str = "Meeting") -> Optional[str]:
        """Generate summary from transcript text."""
        if not transcript or not transcript.strip():
            return None

        prompt = (
            "Please provide a concise summary of the following meeting transcript.\\n\\n"
            f"Meeting: {meeting_title}\\n\\n"
            "Include:\\n"
            "1. Key discussion points\\n"
            "2. Decisions made\\n"
            "3. Action items (if any)\\n"
            "4. Important takeaways\\n\\n"
            f"Transcript:\\n{transcript}\\n\\n"
            "Please format the summary in a clear, professional manner suitable for posting in a chat."
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You create concise, professional meeting summaries.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 1000,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(self.OPENAI_API_URL, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except Exception:
            return None

    def format_summary_message(self, meeting_title: str, summary: str, platform: str) -> str:
        emoji = "📊" if platform == "teams" else "🎥"
        return (
            f"{emoji} **Meeting Summary: {meeting_title}**\\n\\n"
            f"{summary}\\n\\n"
            "---\\n"
            "_This summary was automatically generated from the meeting recording._"
        )
