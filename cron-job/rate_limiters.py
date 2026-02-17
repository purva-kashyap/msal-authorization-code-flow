"""
Rate limiting configuration for API calls.
"""
from aiolimiter import AsyncLimiter
from typing import Dict


class RateLimiters:
    """Centralized rate limiters for different APIs."""
    
    def __init__(self):
        """Initialize rate limiters for different services."""
        # Microsoft Graph API: 120 requests per 60 seconds (conservative)
        # Actual limits are higher but we stay conservative
        self.graph_limiter = AsyncLimiter(max_rate=100, time_period=60)
        
        # Zoom API: varies by endpoint, using conservative limits
        # Cloud Recording: 10 requests per second
        self.zoom_recording_limiter = AsyncLimiter(max_rate=8, time_period=1)
        
        # Zoom general: 80 requests per second (account-level)
        self.zoom_general_limiter = AsyncLimiter(max_rate=60, time_period=1)
        
        # OpenAI: 3 requests per minute for free tier, adjust based on your tier
        # For GPT-4: Adjust based on your token limits
        self.openai_limiter = AsyncLimiter(max_rate=10, time_period=60)
    
    async def acquire_graph_limit(self):
        """Acquire rate limit slot for Microsoft Graph API."""
        async with self.graph_limiter:
            pass
    
    async def acquire_zoom_recording_limit(self):
        """Acquire rate limit slot for Zoom recording API."""
        async with self.zoom_recording_limiter:
            pass
    
    async def acquire_zoom_general_limit(self):
        """Acquire rate limit slot for Zoom general API."""
        async with self.zoom_general_limiter:
            pass
    
    async def acquire_openai_limit(self):
        """Acquire rate limit slot for OpenAI API."""
        async with self.openai_limiter:
            pass


# Global rate limiters instance
rate_limiters = RateLimiters()
