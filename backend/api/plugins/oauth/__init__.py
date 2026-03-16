"""OAuth plugin exports."""

from api.plugins.oauth.config import OAuthPluginConfig
from api.plugins.oauth.plugin import OAuthPlugin

__all__ = ["OAuthPlugin", "OAuthPluginConfig"]
