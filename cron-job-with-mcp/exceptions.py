"""
Custom exceptions for MCP-based cron job.
"""


class MCPCronJobError(Exception):
    """Base exception for MCP cron job."""


class MCPToolError(MCPCronJobError):
    """Raised when MCP tool invocation fails."""


class TokenDecryptionError(MCPCronJobError):
    """Raised when token decryption fails."""
