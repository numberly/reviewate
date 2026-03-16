"""Google OAuth plugin configuration."""

from pydantic import BaseModel


class GoogleOAuthConfig(BaseModel):
    """Google OAuth configuration."""

    client_id: str
    client_secret: str
    metadata_url: str = "https://accounts.google.com/.well-known/openid-configuration"
    userinfo_url: str = "https://www.googleapis.com/oauth2/v3/userinfo"


class GooglePluginConfig(BaseModel):
    """Google OAuth plugin configuration."""

    enabled: bool = False
    oauth: GoogleOAuthConfig | None = None
