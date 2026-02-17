"""
Custom exceptions for better error handling.
"""


class CronJobException(Exception):
    """Base exception for cron job errors."""
    pass


class DatabaseError(CronJobException):
    """Database operation errors."""
    pass


class TokenError(CronJobException):
    """Token-related errors."""
    pass


class TokenExpiredError(TokenError):
    """Access token has expired."""
    pass


class TokenDecryptionError(TokenError):
    """Failed to decrypt token."""
    pass


class APIError(CronJobException):
    """Base class for API errors."""
    def __init__(self, message: str, status_code: int = None, platform: str = None):
        self.status_code = status_code
        self.platform = platform
        super().__init__(message)


class RateLimitError(APIError):
    """API rate limit exceeded."""
    def __init__(self, message: str, retry_after: int = None, platform: str = None):
        self.retry_after = retry_after
        super().__init__(message, status_code=429, platform=platform)


class TeamsAPIError(APIError):
    """Microsoft Teams/Graph API errors."""
    def __init__(self, message: str, status_code: int = None):
        super().__init__(message, status_code=status_code, platform="teams")


class ZoomAPIError(APIError):
    """Zoom API errors."""
    def __init__(self, message: str, status_code: int = None):
        super().__init__(message, status_code=status_code, platform="zoom")


class TranscriptNotFoundError(CronJobException):
    """Transcript not available for meeting."""
    pass


class SummaryGenerationError(CronJobException):
    """Failed to generate meeting summary."""
    pass


class ConfigurationError(CronJobException):
    """Configuration or environment variable errors."""
    pass
