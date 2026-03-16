"""Auth router package."""

from .dependencies import get_current_user, get_current_user_optional
from .enums import DEFAULT_OAUTH_SCOPES, OAuthProvider, OAuthScope
from .jwt import create_access_token, verify_access_token

__all__ = [
    "DEFAULT_OAUTH_SCOPES",
    "OAuthProvider",
    "OAuthScope",
    "create_access_token",
    "get_current_user",
    "get_current_user_optional",
    "router",
    "verify_access_token",
]


def __getattr__(name: str):
    if name == "router":
        from .handlers import router

        return router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
