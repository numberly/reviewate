"""Error types for Reviewate backend."""

from typing import Any


class ReviewateError(Exception):
    """Base error class for all Reviewate backend errors.

    This error provides structured error information with optional details.
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        """Initialize ReviewateError.

        Args:
            message: Error message
            details: Optional dictionary with additional context
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        """String representation."""
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class QueueError(ReviewateError):
    """Errors related to queue operations."""

    pass


class ConfigurationError(ReviewateError):
    """Errors related to configuration."""

    pass
