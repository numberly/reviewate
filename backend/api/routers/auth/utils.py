"""Auth services for OAuth user management."""

import logging

from api.context import get_current_app
from api.database.user import db_create_or_update_user
from api.models.users import User
from api.plugins.faststream import get_faststream_broker
from api.plugins.faststream.config import STREAM_MAXLEN
from api.security import get_encryptor

from .enums import OAuthProvider
from .schemas import SyncUserMembershipsMessage

logger = logging.getLogger(__name__)


def _pick_github_email(userinfo: dict, emails: list[dict]) -> str | None:
    """Pick the best email from GitHub userinfo and /user/emails response.

    Priority: primary verified > any verified (excluding noreply) > noreply fallback.
    """
    # Try primary verified email first
    for entry in emails:
        if entry.get("primary") and entry.get("verified"):
            return entry.get("email")

    # Fall back to any verified non-noreply email
    for entry in emails:
        addr = entry.get("email", "")
        if entry.get("verified") and not addr.endswith("@users.noreply.github.com"):
            return addr

    # Fall back to userinfo email
    if userinfo.get("email"):
        return userinfo["email"]

    # Last resort: noreply address
    login = userinfo.get("login")
    return f"{login}@users.noreply.github.com" if login else None


async def _extract_github_user(token: dict) -> tuple[dict, str | None]:
    """Extract userinfo and email for a GitHub user.

    Uses the GitHub plugin to fetch user info and emails via the API
    when the OAuth token doesn't include them.

    Returns:
        (userinfo dict, email string or None)
    """
    app = get_current_app()
    github = app.github
    access_token = token.get("access_token")
    userinfo = token.get("userinfo", {})

    if not userinfo and github and access_token:
        userinfo = await github.fetch_user_info(access_token)

    # Fetch emails via GitHub API (userinfo email is often null for private emails)
    emails: list[dict] = []
    if github and access_token:
        try:
            emails = await github.fetch_user_emails(access_token)
        except Exception as e:
            logger.warning(f"Failed to fetch GitHub emails: {e}")

    email = _pick_github_email(userinfo, emails)
    return userinfo, email


def _extract_generic_user(token: dict) -> tuple[dict, str | None]:
    """Extract userinfo and email for Google/GitLab users."""
    userinfo = token.get("userinfo", {})
    email = userinfo.get("email")
    return userinfo, email


async def handle_oauth_user_creation(provider: OAuthProvider, token: dict) -> User:
    """Handle OAuth user creation/update after successful authentication.

    Extracts user identity from the OAuth token, creates or updates the user
    and provider identity in the database, and queues a membership sync job.

    Args:
        provider: OAuth provider
        token: OAuth token data (with userinfo populated by callback)

    Returns:
        User instance
    """
    if provider == OAuthProvider.GITHUB:
        userinfo, email = await _extract_github_user(token)
    else:
        userinfo, email = _extract_generic_user(token)

    # Get external ID based on provider
    external_id = userinfo.get("sub") if provider == OAuthProvider.GOOGLE else userinfo.get("id")
    if not external_id:
        raise ValueError(f"No user ID found in {provider.value} OAuth response")

    avatar_url = userinfo.get("avatar_url") or userinfo.get("picture")

    if not email:
        raise ValueError(f"No email found in {provider.value} OAuth response")

    username = (
        userinfo.get("login")
        or userinfo.get("username")
        or userinfo.get("preferred_username")
        or userinfo.get("name")
    )
    if not username:
        raise ValueError(f"No username found in {provider.value} OAuth response")

    # Create or update user (this also creates/updates the ProviderIdentity)
    app = get_current_app()
    with app.database.session() as db:
        user, _ = db_create_or_update_user(
            db=db,
            provider=provider,
            external_id=str(external_id),
            email=email,
            username=username,
            avatar_url=avatar_url,
        )

    # Queue membership sync for GitHub and GitLab (not Google — no org concept)
    if provider in (OAuthProvider.GITHUB, OAuthProvider.GITLAB):
        oauth_access_token = token.get("access_token")
        if oauth_access_token:
            try:
                encryptor = get_encryptor()
                encrypted_token = encryptor.encrypt(oauth_access_token)

                broker = get_faststream_broker()
                message = SyncUserMembershipsMessage(
                    user_id=str(user.id),
                    provider=provider.value,
                    access_token_encrypted=encrypted_token,
                    external_user_id=str(external_id),
                    username=username,
                )
                await broker.publish(
                    message,
                    stream="reviewate.events.auth.sync_memberships",
                    maxlen=STREAM_MAXLEN,
                )
                logger.info(f"Queued membership sync for user {user.id} ({provider.value})")
            except Exception as e:
                # Don't fail login if sync queuing fails
                logger.error(f"Failed to queue membership sync: {e}", exc_info=True)

    return user
