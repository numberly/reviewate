"""FastAPI dependencies for user authentication."""

import logging

from fastapi import Cookie, HTTPException
from sqlalchemy.orm import selectinload

from api.context import get_current_app
from api.models import User

from .enums import OAuthProvider
from .jwt import verify_access_token

logger = logging.getLogger(__name__)


async def get_current_user(
    session_token: str | None = Cookie(None, alias="reviewate_session"),
) -> User:
    """Dependency to get the current authenticated user from JWT cookie.

    Uses a short-lived DB session to avoid holding connections during
    long-running requests (SSE streams, external API calls).

    Args:
        session_token: JWT token from cookie

    Returns:
        Current authenticated user with identities eagerly loaded

    Raises:
        HTTPException: If not authenticated or user not found
    """
    if not session_token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = verify_access_token(session_token)

    app = get_current_app()
    with app.database.session() as db:
        user = (
            db.query(User).options(selectinload(User.identities)).filter(User.id == user_id).first()
        )
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

    return user


async def get_current_user_optional(
    session_token: str | None = Cookie(None, alias="reviewate_session"),
) -> User | None:
    """Optional dependency to get current user (returns None if not authenticated).

    Uses a short-lived DB session to avoid holding connections during
    long-running requests.

    Args:
        session_token: JWT token from cookie

    Returns:
        Current user or None if not authenticated
    """
    if not session_token:
        return None

    try:
        user_id = verify_access_token(session_token)

        app = get_current_app()
        with app.database.session() as db:
            user = (
                db.query(User)
                .options(selectinload(User.identities))
                .filter(User.id == user_id)
                .first()
            )
            return user
    except HTTPException:
        return None


async def require_provider_enabled(provider: OAuthProvider) -> None:
    """Dependency that raises 503 if the given provider is not enabled.

    Args:
        provider: OAuth provider to check

    Raises:
        HTTPException: 503 if the provider plugin is not available
    """
    app = get_current_app()
    providers = {
        OAuthProvider.GITHUB: app.github,
        OAuthProvider.GITLAB: app.gitlab,
        OAuthProvider.GOOGLE: app.google,
    }
    if not providers.get(provider):
        raise HTTPException(
            status_code=503,
            detail=f"{provider.value.capitalize()} integration is not available",
        )


async def require_github_enabled() -> None:
    """Dependency that raises 503 if GitHub plugin is not enabled.

    Use this dependency on routes that require GitHub integration.

    Raises:
        HTTPException: 503 if GitHub plugin is not available
    """
    app = get_current_app()
    if not app.github:
        raise HTTPException(
            status_code=503,
            detail="GitHub integration is not available",
        )


async def require_gitlab_enabled() -> None:
    """Dependency that raises 503 if GitLab plugin is not enabled.

    Use this dependency on routes that require GitLab integration.

    Raises:
        HTTPException: 503 if GitLab plugin is not available
    """
    app = get_current_app()
    if not app.gitlab:
        raise HTTPException(
            status_code=503,
            detail="GitLab integration is not available",
        )


async def require_google_enabled() -> None:
    """Dependency that raises 503 if Google plugin is not enabled.

    Use this dependency on routes that require Google integration.

    Raises:
        HTTPException: 503 if Google plugin is not available
    """
    app = get_current_app()
    if not app.google:
        raise HTTPException(
            status_code=503,
            detail="Google integration is not available",
        )
