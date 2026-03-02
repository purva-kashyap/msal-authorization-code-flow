"""
LLM service for generating meeting summaries.

Handles:
- Building prompts from transcripts
- Calling OpenAI chat completions
- Rate limiting for the LLM API
- Formatting summary messages for posting
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from config import settings
from exceptions import SummaryGenerationError
from rate_limiters import rate_limiters
from utils import async_retry

logger = logging.getLogger(__name__)


class LLMService:
    """Generate meeting summaries using an OpenAI-compatible LLM API."""

    OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
    TIMEOUT = 90.0

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self._api_key = api_key
        self._model = model
        self._client = httpx.AsyncClient(timeout=self.TIMEOUT)

    async def close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Prompt
    # ------------------------------------------------------------------
    @staticmethod
    def _build_prompt(transcript: str, meeting_title: str) -> str:
        return (
            f"Please provide a concise summary of the following meeting transcript.\n\n"
            f"Meeting: {meeting_title}\n\n"
            f"Include:\n"
            f"1. Key discussion points\n"
            f"2. Decisions made\n"
            f"3. Action items (with owners if mentioned)\n"
            f"4. Important takeaways\n\n"
            f"Transcript:\n{transcript}\n\n"
            f"Format the summary in a clear, professional manner suitable for "
            f"posting in a Teams chat."
        )

    # ------------------------------------------------------------------
    # Summary generation
    # ------------------------------------------------------------------
    @async_retry(retry_on=(SummaryGenerationError, ConnectionError, TimeoutError))
    async def generate_summary(
        self,
        transcript: str,
        meeting_title: str = "Meeting",
    ) -> Optional[str]:
        """
        Generate a meeting summary from a transcript.

        Returns the summary text, or ``None`` on failure.
        """
        if not transcript or not transcript.strip():
            logger.warning("llm_empty_transcript")
            return None

        # Truncate very long transcripts to stay within token budgets
        max_chars = settings.max_transcript_chars
        if len(transcript) > max_chars:
            logger.info(
                "llm_transcript_truncated original=%d max=%d",
                len(transcript),
                max_chars,
            )
            transcript = transcript[:max_chars] + "\n\n[… transcript truncated]"

        await rate_limiters.acquire_openai_limit()

        prompt = self._build_prompt(transcript, meeting_title)

        try:
            resp = await self._client.post(
                self.OPENAI_API_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a helpful assistant that creates concise, "
                                "professional meeting summaries."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1500,
                },
            )
            resp.raise_for_status()
            summary = resp.json()["choices"][0]["message"]["content"]
            logger.info("llm_summary_generated title=%s", meeting_title)
            return summary

        except httpx.HTTPStatusError as exc:
            logger.error("llm_http_error status=%d body=%s", exc.response.status_code, exc.response.text[:300])
            return None
        except Exception as exc:
            logger.error("llm_error: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------
    @staticmethod
    def format_summary_message(
        meeting_title: str,
        summary: str,
        platform: str = "teams",
    ) -> str:
        """Format the summary for posting into a Teams or Zoom chat."""
        icon = "📊" if platform == "teams" else "🎥"
        return (
            f"{icon} <b>Meeting Summary: {meeting_title}</b>\n\n"
            f"{summary}\n\n"
            f"<i>This summary was automatically generated from the meeting recording.</i>"
        )
