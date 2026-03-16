"""Schemas for config API endpoints."""

from pydantic import BaseModel


class ProviderConfig(BaseModel):
    """Configuration for available OAuth/integration providers."""

    github_enabled: bool
    gitlab_enabled: bool
    google_enabled: bool
    gitlab_url: str | None = None


class AppConfig(BaseModel):
    """Application configuration exposed to frontend."""

    providers: ProviderConfig
