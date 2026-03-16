"""OAuth plugin configuration."""

from pydantic import BaseModel


class OAuthPluginConfig(BaseModel):
    """OAuth plugin configuration.

    This plugin manages OAuth client registration for authentication providers.
    It works with GitHub, GitLab, and Google plugins to register their OAuth endpoints.
    """

    enabled: bool = False
