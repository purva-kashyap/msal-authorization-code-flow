"""
Utility functions for the cron job service.
"""
from cryptography.fernet import Fernet
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)
from functools import wraps
import asyncio
from typing import Callable, TypeVar, Any
from logging_config import get_logger
from exceptions import TokenDecryptionError, RateLimitError, APIError
from config import settings

logger = get_logger(__name__)

T = TypeVar('T')


class TokenDecryptor:
    """Utility class for decrypting tokens."""
    
    def __init__(self, encryption_key: str):
        """Initialize with encryption key."""
        try:
            self.fernet = Fernet(encryption_key.encode())
        except Exception as e:
            logger.error("failed_to_initialize_decryptor", error=str(e))
            raise TokenDecryptionError(f"Invalid encryption key: {str(e)}")
    
    def decrypt_token(self, encrypted_token: str) -> str:
        """
        Decrypt an encrypted token.
        
        Args:
            encrypted_token: Encrypted token string
            
        Returns:
            Decrypted token string
            
        Raises:
            TokenDecryptionError: If decryption fails
        """
        try:
            decrypted = self.fernet.decrypt(encrypted_token.encode()).decode()
            return decrypted
        except Exception as e:
            logger.error("token_decryption_failed", error=str(e))
            raise TokenDecryptionError(f"Failed to decrypt token: {str(e)}")


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string like "2m 30s"
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def async_retry(
    max_attempts: int = None,
    backoff_base: float = None,
    max_wait: int = None,
    retry_on: tuple = None
):
    """
    Decorator for retrying async functions with exponential backoff.
    
    Args:
        max_attempts: Maximum retry attempts (default from config)
        backoff_base: Base for exponential backoff (default from config)
        max_wait: Maximum wait time in seconds (default from config)
        retry_on: Tuple of exception types to retry on
    
    Returns:
        Decorated function with retry logic
    """
    max_attempts = max_attempts or settings.max_retries
    backoff_base = backoff_base or settings.retry_backoff_base
    max_wait = max_wait or settings.retry_max_wait
    
    # Default exceptions to retry on
    if retry_on is None:
        retry_on = (APIError, ConnectionError, TimeoutError, asyncio.TimeoutError)
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=1, max=max_wait, exp_base=backoff_base),
            retry=retry_if_exception_type(retry_on),
            before_sleep=before_sleep_log(logger, "WARNING"),
            after=after_log(logger, "INFO")
        )
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


async def handle_rate_limit_error(error: RateLimitError) -> None:
    """
    Handle rate limit errors by waiting.
    
    Args:
        error: The rate limit error
    """
    wait_time = error.retry_after if error.retry_after else 60
    logger.warning(
        "rate_limit_hit",
        platform=error.platform,
        wait_time=wait_time
    )
    await asyncio.sleep(wait_time)


def safe_dict_get(d: dict, *keys: str, default: Any = None) -> Any:
    """
    Safely get nested dictionary values.
    
    Args:
        d: Dictionary to search
        *keys: Keys to traverse
        default: Default value if key not found
        
    Returns:
        Value or default
    """
    for key in keys:
        try:
            d = d[key]
        except (KeyError, TypeError, AttributeError):
            return default
    return d
