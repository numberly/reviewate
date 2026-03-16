"""Database plugin configuration."""

from pydantic import BaseModel, Field


class DatabasePluginConfig(BaseModel):
    """Database plugin configuration."""

    enabled: bool = False
    url: str
    echo: bool = False
    pool_size: int = Field(default=5, ge=1)
    max_overflow: int = Field(default=10, ge=0)

    # Encryption key for sensitive data (AES-256-GCM)
    encryption_key: str | None = None
