"""API route handlers for auth endpoints."""

import logging
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from api.context import get_current_app
from api.database import get_session
from api.database.identity import (
    db_count_user_identities,
    db_get_identity_by_external_id,
    db_get_or_create_provider_identity,
    db_unlink_identity_from_user,
)
from api.database.user import db_get_user_by_email
from api.models import User
from api.oauth import get_oauth_client
from api.utils import set_session_cookie

from .dependencies import (
    get_current_user,
    require_github_enabled,
    require_gitlab_enabled,
    require_google_enabled,
    require_provider_enabled,
)
from .enums import OAuthProvider
from .jwt import create_access_token
from .schemas import (
    DisconnectProviderResponse,
    LogoutResponse,
    UpdateProfileRequest,
    UpdateProfileResponse,
    UserProfile,
)
from .utils import handle_oauth_user_creation

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


# =============================================================================
# OAuth Login Endpoints
# =============================================================================


@router.get(
    "/google",
    operation_id="login_google",
    name="google_login",
    summary="Login with Google",
    description="Initiates Google OAuth flow for user authentication (identity only).",
    response_class=RedirectResponse,
    status_code=302,
    dependencies=[Depends(require_google_enabled)],
)
async def google_login(request: Request) -> RedirectResponse:
    """Initiate Google OAuth login."""
    redirect_uri = request.url_for("oauth_callback", provider=OAuthProvider.GOOGLE.value)
    google_client = get_oauth_client(OAuthProvider.GOOGLE)
    return await google_client.authorize_redirect(request, redirect_uri)


@router.get(
    "/github",
    operation_id="login_github",
    name="github_login",
    summary="Login with GitHub",
    description="Initiates GitHub OAuth flow for user authentication (identity only, no repo access).",
    response_class=RedirectResponse,
    status_code=302,
    dependencies=[Depends(require_github_enabled)],
)
async def github_login(request: Request) -> RedirectResponse:
    """Initiate GitHub OAuth login (identity only)."""
    redirect_uri = request.url_for("oauth_callback", provider=OAuthProvider.GITHUB.value)
    github_client = get_oauth_client(OAuthProvider.GITHUB)
    return await github_client.authorize_redirect(request, redirect_uri)


@router.get(
    "/gitlab",
    operation_id="login_gitlab",
    name="gitlab_login",
    summary="Login with GitLab",
    description="Initiates GitLab OAuth flow for user authentication (identity only, no repo access).",
    response_class=RedirectResponse,
    status_code=302,
    dependencies=[Depends(require_gitlab_enabled)],
)
async def gitlab_login(request: Request) -> RedirectResponse:
    """Initiate GitLab OAuth login (identity only)."""
    redirect_uri = request.url_for("oauth_callback", provider=OAuthProvider.GITLAB.value)
    gitlab_client = get_oauth_client(OAuthProvider.GITLAB)
    return await gitlab_client.authorize_redirect(request, redirect_uri)


# =============================================================================
# OAuth Callback
# =============================================================================


async def _exchange_oauth_token(provider: OAuthProvider, request: Request) -> dict:
    """Exchange OAuth authorization code for access token.

    For GitLab, also fetches userinfo and attaches it to the token dict.

    Returns:
        Token dict (with 'userinfo' key populated for GitLab).
    """
    app = get_current_app()
    oauth_client = get_oauth_client(provider)
    token = await oauth_client.authorize_access_token(request)

    if provider == OAuthProvider.GITLAB:
        gitlab_plugin = app.gitlab
        if not gitlab_plugin:
            raise HTTPException(status_code=500, detail="GitLab plugin not available")

        access_token = token.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="No access token in GitLab response")

        try:
            userinfo = await gitlab_plugin.verify_token(access_token)
            token["userinfo"] = userinfo
        except Exception as e:
            logger.error(f"Failed to fetch GitLab userinfo: {e}", exc_info=True)
            raise HTTPException(
                status_code=500, detail="Failed to fetch user information from GitLab"
            ) from e

    return token


async def _handle_link_callback(
    provider: OAuthProvider, link_mode: str, link_user_id: str, token: dict, frontend_url: str
) -> RedirectResponse:
    """Handle link-mode OAuth callback: link a new provider identity to existing user."""
    logger.info(f"Link mode: linking {link_mode} to user {link_user_id}")

    app = get_current_app()
    userinfo = token.get("userinfo", {})

    # For GitHub, fetch userinfo if empty
    if provider == OAuthProvider.GITHUB and not userinfo:
        oauth_client = get_oauth_client(provider)
        response = await oauth_client.get("user", token=token)
        userinfo = response.json()

    external_id = str(userinfo.get("id") or userinfo.get("sub") or "")
    username = userinfo.get("login") or userinfo.get("username")
    avatar_url = userinfo.get("avatar_url") or userinfo.get("picture")

    if not external_id:
        return RedirectResponse(
            url=f"{frontend_url}/settings?error=no_external_id",
            status_code=302,
        )

    with app.database.session() as db:
        existing_identity = db_get_identity_by_external_id(db, provider.value, external_id)
        if (
            existing_identity
            and existing_identity.user_id
            and str(existing_identity.user_id) != link_user_id
        ):
            return RedirectResponse(
                url=f"{frontend_url}/settings?error=account_in_use",
                status_code=302,
            )

        db_get_or_create_provider_identity(
            db=db,
            provider=provider.value,
            external_id=external_id,
            username=username,
            avatar_url=avatar_url,
            user_id=UUID(link_user_id),
        )

    return RedirectResponse(
        url=f"{frontend_url}/settings?linked={link_mode}",
        status_code=302,
    )


async def _handle_login_callback(provider: OAuthProvider, token: dict) -> RedirectResponse:
    """Handle login-mode OAuth callback: create/update user and set session cookie."""
    app = get_current_app()
    frontend_url = app.web.config.frontend_url

    user = await handle_oauth_user_creation(provider, token)
    jwt_token = create_access_token(user.id)

    response = RedirectResponse(url=f"{frontend_url}/", status_code=302)
    set_session_cookie(
        response, jwt_token, app.web.config.session, is_production=app._backend_config.is_production
    )
    return response


@router.get(
    "/callback/{provider}",
    operation_id="oauth_callback",
    name="oauth_callback",
    summary="Handle OAuth callback",
    description="Handles OAuth callback from any provider, creates/updates user, and sets session cookie.",
    response_class=RedirectResponse,
    status_code=302,
)
async def oauth_callback(
    provider: OAuthProvider,
    request: Request,
) -> RedirectResponse:
    """Handle OAuth callback from any provider.

    Routes to the correct handler based on session mode (link or login).
    """
    await require_provider_enabled(provider)

    app = get_current_app()
    frontend_url = app.web.config.frontend_url
    token = await _exchange_oauth_token(provider, request)

    link_mode = request.session.pop("link_mode", None)
    link_user_id = request.session.pop("link_user_id", None)
    if link_mode and link_user_id:
        return await _handle_link_callback(provider, link_mode, link_user_id, token, frontend_url)

    return await _handle_login_callback(provider, token)


# =============================================================================
# User Profile Endpoints
# =============================================================================


@router.get(
    "/me",
    operation_id="get_me",
    name="get_current_user",
    summary="Get current user profile",
    description="Returns the profile of the currently logged-in user.",
    response_model=UserProfile,
)
async def get_me(current_user: User = Depends(get_current_user)) -> UserProfile:
    """Get current authenticated user profile."""
    return UserProfile.from_user(current_user)


@router.patch(
    "/me",
    operation_id="update_profile",
    name="update_profile",
    summary="Update current user profile",
    description="Updates the profile of the currently logged-in user.",
    response_model=UpdateProfileResponse,
)
async def update_profile(
    request_body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> UpdateProfileResponse:
    """Update current user's profile.

    Allows updating email. Display name is derived from identities.
    """
    # Re-attach detached user to this session (auth dep uses its own session)
    current_user = db.merge(current_user)

    if request_body.email is not None:
        # Validate email format using RFC 5322 simplified pattern
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if request_body.email and not re.match(email_pattern, request_body.email):
            raise HTTPException(status_code=400, detail="Invalid email format")

        # Check if email is already taken by another user
        if request_body.email:
            existing = db_get_user_by_email(db, request_body.email)
            if existing and existing.id != current_user.id:
                raise HTTPException(status_code=400, detail="Email already in use")

        current_user.email = request_body.email if request_body.email else None

    if request_body.onboarding_step is not None:
        current_user.onboarding_step = request_body.onboarding_step

    db.commit()
    db.refresh(current_user)

    return UpdateProfileResponse(profile=UserProfile.from_user(current_user))


@router.post(
    "/logout",
    operation_id="logout",
    name="logout",
    summary="Logout user",
    description="Destroys the user's session by clearing the session cookie.",
    response_model=LogoutResponse,
)
async def logout() -> Response:
    """Logout current user by clearing session cookie."""
    app = get_current_app()
    if not app.web:
        raise RuntimeError("Web plugin not enabled")

    logout_data = LogoutResponse(message="Logged out successfully")
    response = Response(
        content=logout_data.model_dump_json(),
        media_type="application/json",
        status_code=200,
    )

    set_session_cookie(
        response,
        "",
        app.web.config.session,
        is_production=app._backend_config.is_production,
        max_age_seconds=0,
    )
    return response


# =============================================================================
# Provider Linking Endpoints
# =============================================================================


@router.delete(
    "/providers/{provider}",
    operation_id="disconnect_provider",
    name="disconnect_provider",
    summary="Disconnect a provider account",
    description="Unlinks a connected provider (GitHub, GitLab, Google) from the user's account.",
    response_model=DisconnectProviderResponse,
)
async def disconnect_provider(
    provider: OAuthProvider,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> DisconnectProviderResponse:
    """Disconnect a provider from the user's account.

    Validates that user has at least 2 connected accounts before allowing disconnect.
    """
    await require_provider_enabled(provider)

    identity_count = db_count_user_identities(db, current_user.id)

    if identity_count <= 1:
        raise HTTPException(
            status_code=400,
            detail="Cannot disconnect: You must have at least one connected account",
        )

    identity = current_user.get_identity(provider.value)
    if not identity:
        raise HTTPException(
            status_code=404,
            detail=f"Provider {provider.value} is not connected to your account",
        )

    success = db_unlink_identity_from_user(db, current_user.id, provider.value)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to disconnect provider")

    current_user = db.merge(current_user)
    db.refresh(current_user)

    return DisconnectProviderResponse(
        message=f"{provider.value.capitalize()} account disconnected",
        profile=UserProfile.from_user(current_user),
    )


@router.get(
    "/link/{provider}",
    operation_id="link_provider",
    name="link_provider",
    summary="Link a new provider account",
    description="Initiates OAuth flow to link an additional provider to the current user's account.",
    response_class=RedirectResponse,
    status_code=302,
)
async def link_provider(
    provider: OAuthProvider,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> RedirectResponse:
    """Initiate OAuth flow to link a new provider to current user.

    Sets link mode in session to handle callback appropriately.
    """
    await require_provider_enabled(provider)

    app = get_current_app()
    frontend_url = app.web.config.frontend_url

    identity = current_user.get_identity(provider.value)
    if identity:
        return RedirectResponse(
            url=f"{frontend_url}/settings?error=already_linked",
            status_code=302,
        )

    request.session["link_mode"] = provider.value
    request.session["link_user_id"] = str(current_user.id)

    redirect_uri = request.url_for("oauth_callback", provider=provider.value)
    oauth_client = get_oauth_client(provider)
    return await oauth_client.authorize_redirect(request, redirect_uri)
