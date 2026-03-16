"""OAuth plugin - Multi-provider OAuth client management."""

import logging

from authlib.integrations.starlette_client import OAuth

from api.context import get_current_app
from api.plugins.oauth.config import OAuthPluginConfig
from api.plugins.plugin import BasePlugin
from api.routers.auth.enums import OAuthProvider

logger = logging.getLogger(__name__)


class OAuthPlugin(BasePlugin[OAuthPluginConfig]):
    """OAuth plugin managing OAuth provider registration.

    This plugin initializes the OAuth client and registers enabled providers
    from GitHub, GitLab, and Google plugins.
    """

    plugin_name = "oauth"
    config_class = OAuthPluginConfig
    priority = 30

    def __init__(self, plugin_config: OAuthPluginConfig):
        """Initialize OAuth plugin.

        Args:
            plugin_config: OAuth plugin configuration
        """
        self.config = plugin_config
        self.oauth = OAuth()

    async def startup(self) -> None:
        """Register OAuth providers from enabled plugins."""
        app = get_current_app()

        # Register GitHub OAuth if enabled (using GitHub App user-to-server credentials)
        if hasattr(app, "github") and app.github:
            config = app.github.config.app
            if config:  # Ensure app config exists
                self.oauth.register(
                    name=OAuthProvider.GITHUB.value,
                    client_id=config.client_id,
                    client_secret=config.client_secret,
                    authorize_url=config.authorize_url,
                    access_token_url=config.token_url,
                    api_base_url=config.api_base_url,
                    client_kwargs={"scope": " ".join(config.scopes)},
                )
                logger.debug("Registered GitHub OAuth provider")

        # Register GitLab OAuth if enabled
        if hasattr(app, "gitlab") and app.gitlab:
            config = app.gitlab.config.oauth
            instance_url = config.instance_url
            self.oauth.register(
                name=OAuthProvider.GITLAB.value,
                client_id=config.client_id,
                client_secret=config.client_secret,
                server_metadata_url=f"{instance_url}/.well-known/openid-configuration",
                api_base_url=f"{instance_url}/api/v4",
                client_kwargs={"scope": " ".join(config.scopes)},
            )
            logger.debug(f"Registered GitLab OAuth provider ({instance_url})")

        # Register Google OAuth if enabled
        if hasattr(app, "google") and app.google:
            config = app.google.config.oauth
            self.oauth.register(
                name=OAuthProvider.GOOGLE.value,
                client_id=config.client_id,
                client_secret=config.client_secret,
                server_metadata_url=config.metadata_url,
                client_kwargs={
                    "scope": "openid email profile",
                    "prompt": "select_account",
                },
            )
            logger.debug("Registered Google OAuth provider")

        if not self.oauth._clients:
            logger.warning("No OAuth providers registered - authentication will not work")

        logger.debug(f"OAuth plugin started with {len(self.oauth._clients)} provider(s)")

    async def shutdown(self) -> None:
        """Shutdown OAuth plugin."""
        self.oauth._clients.clear()

    def get_client(self, provider: str):
        """Get OAuth client for a specific provider.

        Args:
            provider: Provider name (github, gitlab, google)

        Returns:
            OAuth client instance

        Raises:
            KeyError: If provider not registered
        """
        return self.oauth.create_client(provider)

    def get_oauth(self) -> OAuth:
        """Get the OAuth instance.

        Returns:
            OAuth instance with all registered providers
        """
        return self.oauth
