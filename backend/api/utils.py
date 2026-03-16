"""Utility functions for API handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException, Response

if TYPE_CHECKING:
    from api.plugins.web.config import SessionConfig


def parse_uuid(value: str, field_name: str = "ID") -> UUID:
    """Parse a string to UUID with proper error handling.

    Args:
        value: String value to parse
        field_name: Name of the field for error message

    Returns:
        UUID object

    Raises:
        HTTPException: 400 if the value is not a valid UUID
    """
    try:
        return UUID(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name} format",
        ) from exc


def set_session_cookie(
    response: Response,
    token: str,
    session_config: SessionConfig,
    *,
    is_production: bool = False,
    max_age_seconds: int | None = None,
) -> None:
    """Set session cookie on response with consistent configuration.

    Args:
        response: FastAPI Response object
        token: JWT token value (empty string to clear cookie)
        session_config: Session configuration from web plugin
        is_production: Whether the app is running in production
        max_age_seconds: Optional max age in seconds (defaults to config value)
    """
    if max_age_seconds is None:
        max_age_seconds = 86400 * session_config.max_age_days

    response.set_cookie(
        key=session_config.cookie_name,
        value=token,
        domain=session_config.cookie_domain,
        path="/",
        httponly=session_config.cookie_httponly,
        secure=is_production,
        samesite=session_config.cookie_samesite,
        max_age=max_age_seconds,
    )
