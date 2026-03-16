"""GitLab plugin configuration."""

from pydantic import BaseModel, Field


class GitLabOAuthConfig(BaseModel):
    """GitLab OAuth configuration."""

    client_id: str
    client_secret: str
    instance_url: str = "https://gitlab.com"
    api_url: str | None = Field(
        default=None, description="GitLab API URL (defaults to {instance_url}/api/v4)"
    )
    scopes: list[str] = Field(default_factory=lambda: ["read_user", "read_api"])


class GitLabPluginConfig(BaseModel):
    """GitLab plugin configuration."""

    enabled: bool = False
    oauth: GitLabOAuthConfig | None = None
    webhook_secret: str | None = None
