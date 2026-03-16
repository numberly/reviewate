"""Shared OAuth schemas for all providers."""

from pydantic import BaseModel


class OAuthToken(BaseModel):
    """Generic OAuth token response from any provider."""

    access_token: str
    token_type: str
    scope: str | None = None


class OAuthUserData(BaseModel):
    """Normalized user data from any OAuth provider."""

    provider_external_id: str
    email: str
    username: str
