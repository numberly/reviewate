"""OAuth configuration for multi-provider authentication."""

from authlib.integrations.starlette_client import OAuth, StarletteOAuth2App

from api.context import get_current_app
from api.routers.auth.enums import OAuthProvider
from api.schemas import OAuthToken

# Re-export for convenience
__all__ = ["OAuthToken", "get_oauth_client", "oauth"]


def oauth() -> OAuth:
    """Get the OAuth instance from the OAuth plugin.

    Returns:
        OAuth instance with all registered providers

    Raises:
        RuntimeError: If OAuth plugin not enabled
    """
    app = get_current_app()
    if not app.oauth:
        raise RuntimeError("OAuth plugin not enabled")
    return app.oauth.get_oauth()


def get_oauth_client(provider: OAuthProvider) -> StarletteOAuth2App:
    """Get the configured OAuth client for a specific provider.

    Args:
        provider: OAuth provider enum

    Returns:
        Configured OAuth client for the provider

    Raises:
        AttributeError: If provider is not registered
    """
    oauth_instance = oauth()
    return getattr(oauth_instance, provider.value)  # type: ignore[no-any-return]
