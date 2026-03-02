"""
Rate limiting configuration for API calls.
Limits are driven by config so they can be tuned per environment.
"""
from aiolimiter import AsyncLimiter

from config import settings


class RateLimiters:
    """Centralized rate limiters for different APIs."""

    def __init__(self):
        # Microsoft Graph API — tenant limit is 10 000 req / 10 min.
        # We default to a conservative per-process cap.
        self.graph_limiter = AsyncLimiter(
            max_rate=settings.graph_api_rate_limit, time_period=60
        )

        # Zoom Cloud Recording API — 10 req/s per account (conservative)
        self.zoom_recording_limiter = AsyncLimiter(
            max_rate=settings.zoom_recording_rate_limit, time_period=1
        )

        # Zoom general endpoints — 80 req/s account level
        self.zoom_general_limiter = AsyncLimiter(
            max_rate=settings.zoom_general_rate_limit, time_period=1
        )

        # OpenAI — varies by tier; default conservative
        self.openai_limiter = AsyncLimiter(
            max_rate=settings.openai_rate_limit, time_period=60
        )

    async def acquire_graph_limit(self):
        async with self.graph_limiter:
            pass

    async def acquire_zoom_recording_limit(self):
        async with self.zoom_recording_limiter:
            pass

    async def acquire_zoom_general_limit(self):
        async with self.zoom_general_limiter:
            pass

    async def acquire_openai_limit(self):
        async with self.openai_limiter:
            pass


# Global instance
rate_limiters = RateLimiters()
