"""Sentry plugin configuration."""

from pydantic import BaseModel, Field


class SentryPluginConfig(BaseModel):
    """Sentry plugin configuration."""

    enabled: bool = False
    dsn: str = ""
    environment: str = ""
    traces_sample_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    profiles_sample_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    send_default_pii: bool = False
