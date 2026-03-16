"""FastStream plugin configuration."""

from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field

# Hardcoded max length for Redis Streams (caps memory usage)
STREAM_MAXLEN = 10000


class FastStreamConsumerConfig(BaseModel):
    """Configuration for a single FastStream consumer."""

    topic: str = Field(
        description="Topic/channel to subscribe to (e.g., 'reviewate.review.jobs')",
    )

    group_id: str | None = Field(
        default=None,
        description="Consumer group ID (optional)",
    )

    handler: str = Field(
        description="Module path to handler router (e.g., 'api.routers.queue.handlers:router')",
    )


class FastStreamRedisConfig(BaseModel):
    """FastStream Redis broker configuration."""

    url: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL",
    )

    # Connection settings
    host: str | None = Field(
        default=None,
        description="Redis host (alternative to URL)",
    )

    port: int | None = Field(
        default=None,
        description="Redis port (alternative to URL)",
    )

    db: int = Field(
        default=0,
        description="Redis database number",
    )

    # Stream/List settings for FastStream
    list_cap_size: int = Field(
        default=10000,
        description="Maximum size of Redis lists (for LIST-based queues)",
    )

    # Consumer group settings
    auto_offset_reset: Literal["latest", "earliest"] = Field(
        default="latest",
        description="Where to start consuming if no offset exists",
    )

    # Performance settings
    batch_size: int = Field(
        default=1,
        description="Number of messages to fetch in one batch",
    )

    polling_interval: float = Field(
        default=0.1,
        description="Polling interval in seconds",
    )

    # Retry settings
    max_retries: int = Field(
        default=3,
        description="Maximum retries for message processing",
    )

    retry_delay: float = Field(
        default=1.0,
        description="Delay between retries in seconds",
    )


class FastStreamPluginConfig(BaseModel):
    """FastStream plugin configuration.

    Uses Redis as the message broker backend via FastStream.
    """

    model_config = ConfigDict(frozen=True)

    enabled: bool = Field(
        default=False,
        description="Whether FastStream queue is enabled",
    )

    # Redis broker configuration
    redis: FastStreamRedisConfig = Field(
        default_factory=FastStreamRedisConfig,
        description="Redis broker configuration",
    )

    # Application settings
    app_name: str = Field(
        default="reviewate-queue",
        description="FastStream application name",
    )

    # Graceful shutdown
    graceful_timeout: float = Field(
        default=30.0,
        description="Graceful shutdown timeout in seconds",
    )

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="FastStream logging level",
    )

    # Consumer configuration
    consumers: list[FastStreamConsumerConfig] = Field(
        default_factory=list,
        description="List of consumers to load (module paths to routers)",
    )

    def get_redis_url(self) -> str:
        """Build Redis URL from configuration.

        If a URL is provided but has no path (e.g. redis://host:6379),
        appends the configured db number (e.g. redis://host:6379/5).

        Returns:
            Redis connection URL
        """
        if self.redis.url:
            parsed = urlparse(self.redis.url)
            # Append /db if URL has no path and db is set
            if self.redis.db and parsed.path in ("", "/"):
                return f"{self.redis.url.rstrip('/')}/{self.redis.db}"
            return self.redis.url

        if self.redis.host and self.redis.port:
            return f"redis://{self.redis.host}:{self.redis.port}/{self.redis.db}"

        return "redis://localhost:6379/0"
