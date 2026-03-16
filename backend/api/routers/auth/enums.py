"""Enums and constants for authentication."""

from enum import StrEnum


class OAuthProvider(StrEnum):
    """OAuth provider types."""

    GOOGLE = "google"
    GITHUB = "github"
    GITLAB = "gitlab"


class OAuthScope(StrEnum):
    """OAuth scopes for different providers."""

    # Google scopes
    GOOGLE_OPENID = "openid"
    GOOGLE_EMAIL = "email"
    GOOGLE_PROFILE = "profile"

    # GitHub scopes
    GITHUB_READ_USER = "read:user"
    GITHUB_USER_EMAIL = "user:email"
    GITHUB_READ_ORG = "read:org"  # Required to read user's organizations

    # GitLab scopes
    GITLAB_READ_USER = "read_user"
    GITLAB_READ_API = "read_api"  # Required to read user's groups


# Default OAuth scopes per provider (includes identity + organization access)
DEFAULT_OAUTH_SCOPES: dict[OAuthProvider, list[str]] = {
    OAuthProvider.GOOGLE: [
        OAuthScope.GOOGLE_OPENID.value,
        OAuthScope.GOOGLE_EMAIL.value,
        OAuthScope.GOOGLE_PROFILE.value,
    ],
    OAuthProvider.GITHUB: [
        OAuthScope.GITHUB_READ_USER.value,
        OAuthScope.GITHUB_USER_EMAIL.value,
        OAuthScope.GITHUB_READ_ORG.value,  # Added to fetch user's organizations
    ],
    OAuthProvider.GITLAB: [
        OAuthScope.GITLAB_READ_USER.value,
        OAuthScope.GITLAB_READ_API.value,  # Added to fetch user's groups
    ],
}
