"""GitHub plugin configuration."""

from pydantic import BaseModel, Field


class GitHubAppConfig(BaseModel):
    """Unified GitHub App configuration.

    Supports both user-to-server OAuth (for user identity) and installation
    authentication (for repository access).
    """

    # User-to-server OAuth credentials (for user login)
    client_id: str
    client_secret: str
    authorize_url: str = "https://github.com/login/oauth/authorize"
    token_url: str = "https://github.com/login/oauth/access_token"
    api_base_url: str = "https://api.github.com"
    scopes: list[str] = Field(default_factory=lambda: ["read:user", "user:email", "read:org"])

    # Installation authentication credentials (for repository access)
    app_id: str
    private_key_path: str
    webhook_secret: str
    name: str


class GitHubPluginConfig(BaseModel):
    """GitHub plugin configuration."""

    enabled: bool = False
    app: GitHubAppConfig | None = None
