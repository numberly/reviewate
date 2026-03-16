"""Sentry plugin - error tracking and performance monitoring."""

import logging

import sentry_sdk

from api.plugins.plugin import BasePlugin
from api.plugins.sentry.config import SentryPluginConfig

logger = logging.getLogger(__name__)


class SentryPlugin(BasePlugin[SentryPluginConfig]):
    """Sentry plugin for error tracking and performance monitoring.

    Framework-agnostic: works with FastAPI, workers, CLI tools, etc.
    The Sentry SDK auto-detects and enables integrations for whatever
    frameworks are installed (FastAPI, SQLAlchemy, Redis, etc.).
    """

    plugin_name = "sentry"
    config_class = SentryPluginConfig
    priority = 5  # Start before all other plugins to capture their errors

    def __init__(self, plugin_config: SentryPluginConfig):
        """Initialize Sentry plugin.

        Args:
            plugin_config: Sentry plugin configuration
        """
        self.config = plugin_config

    async def startup(self) -> None:
        """Initialize the Sentry SDK."""
        init_kwargs: dict = {
            "dsn": self.config.dsn,
            "traces_sample_rate": self.config.traces_sample_rate,
            "profiles_sample_rate": self.config.profiles_sample_rate,
            "send_default_pii": self.config.send_default_pii,
        }

        if self.config.environment:
            init_kwargs["environment"] = self.config.environment

        sentry_sdk.init(**init_kwargs)

    async def shutdown(self) -> None:
        """Flush pending Sentry events."""
        sentry_sdk.flush(timeout=5)
