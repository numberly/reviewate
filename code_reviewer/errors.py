"""Error types for the code reviewer."""

from enum import StrEnum


class ErrorType(StrEnum):
    """Standardized error types emitted by the code reviewer."""

    AUTHENTICATION_FAILED = "authentication_failed"
    NOT_FOUND = "not_found"
    VALIDATION_ERROR = "validation_error"
    INTERRUPTED = "interrupted"
    TIMEOUT = "timeout"
    CONTAINER_ERROR = "container_error"
    INTERNAL_ERROR = "internal_error"


class ReviewateError(Exception):
    """Base error class for all Reviewate errors."""

    pass


_EXCEPTION_MAP: dict[type, ErrorType] = {}


def error_type_for_exception(exc: Exception) -> ErrorType:
    """Map an exception to a standardized ErrorType."""
    for exc_class, error_type in _EXCEPTION_MAP.items():
        if isinstance(exc, exc_class):
            return error_type
    return ErrorType.INTERNAL_ERROR
