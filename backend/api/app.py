"""Application class - the core container for plugins.

The Application instance is the central point of the system. It:
- Holds references to enabled plugins (and ONLY plugins)
- Manages plugin lifecycle (startup/shutdown)
- Loads plugins based on configuration
"""

# Runtime imports moved to module level to avoid function-level imports
import asyncio
import importlib.metadata
import logging
import signal
from typing import Self

from api.context import set_current_app
from api.plugins.container.plugin import ContainerPlugin
from api.plugins.database.plugin import DatabasePlugin
from api.plugins.faststream.plugin import FastStreamPlugin
from api.plugins.github.plugin import GitHubPlugin
from api.plugins.gitlab.plugin import GitLabPlugin
from api.plugins.google.plugin import GooglePlugin
from api.plugins.oauth.plugin import OAuthPlugin
from api.plugins.plugin import BasePlugin
from api.plugins.sentry.plugin import SentryPlugin
from api.plugins.web.plugin import WebServerPlugin
from api.sse import sse_manager
from config import BackendConfig
from options import Options

logger = logging.getLogger(__name__)

# Built-in plugins. External plugins are discovered via entry points.
# Startup order is determined by each plugin's `priority` class var.
BUILTIN_PLUGINS: list[type[BasePlugin]] = [
    SentryPlugin,
    DatabasePlugin,
    GitHubPlugin,
    GitLabPlugin,
    GooglePlugin,
    OAuthPlugin,
    WebServerPlugin,
    FastStreamPlugin,
    ContainerPlugin,
]


class Application:
    """Main application container.

    The Application instance contains only plugins as public attributes.
    Services are private to their respective plugins.
    """

    def __init__(self, config: BackendConfig):
        """Initialize application with configuration.

        Args:
            config: Backend configuration
        """
        self._backend_config = config
        self._plugins: list[BasePlugin] = []
        self._background_tasks: list[asyncio.Task] = []  # Keep references to background tasks

    @property
    def sentry(self) -> SentryPlugin | None:
        """Get Sentry plugin if enabled."""
        return next((p for p in self._plugins if isinstance(p, SentryPlugin)), None)

    @property
    def database(self) -> DatabasePlugin | None:
        """Get database plugin if enabled."""
        return next((p for p in self._plugins if isinstance(p, DatabasePlugin)), None)

    @property
    def oauth(self) -> OAuthPlugin | None:
        """Get OAuth plugin if enabled."""
        return next((p for p in self._plugins if isinstance(p, OAuthPlugin)), None)

    @property
    def github(self) -> GitHubPlugin | None:
        """Get GitHub plugin if enabled."""
        return next((p for p in self._plugins if isinstance(p, GitHubPlugin)), None)

    @property
    def gitlab(self) -> GitLabPlugin | None:
        """Get GitLab plugin if enabled."""
        return next((p for p in self._plugins if isinstance(p, GitLabPlugin)), None)

    @property
    def google(self) -> GooglePlugin | None:
        """Get Google plugin if enabled."""
        return next((p for p in self._plugins if isinstance(p, GooglePlugin)), None)

    @property
    def web(self) -> WebServerPlugin | None:
        """Get web server plugin if enabled."""
        return next((p for p in self._plugins if isinstance(p, WebServerPlugin)), None)

    @property
    def faststream(self) -> FastStreamPlugin | None:
        """Get FastStream plugin if enabled."""
        return next((p for p in self._plugins if isinstance(p, FastStreamPlugin)), None)

    @property
    def container(self) -> ContainerPlugin | None:
        """Get container plugin if enabled."""
        return next((p for p in self._plugins if isinstance(p, ContainerPlugin)), None)

    @property
    def options(self) -> Options:
        """Get application options."""
        return self._backend_config.options

    def get_plugin(self, name: str) -> BasePlugin | None:
        """Get a plugin by name.

        Useful for accessing external plugins that don't have
        typed properties on Application.

        Args:
            name: Plugin name (e.g., "billing")

        Returns:
            Plugin instance, or None if not found
        """
        return next((p for p in self._plugins if p.plugin_name == name), None)

    async def startup(self, plugins: list[BasePlugin]) -> None:
        """Start all plugins.

        Args:
            plugins: List of plugin instances to start
        """
        # Register app in global context
        set_current_app(self)

        self._plugins = plugins

        # Add consumer routers to FastStream BEFORE starting plugins
        faststream_plugin = next((p for p in plugins if isinstance(p, FastStreamPlugin)), None)

        if faststream_plugin:
            # Import here to avoid test import conflicts with FastStream mocking
            from api.routers.pull_requests import (
                consumer_router as pr_consumer,
            )
            from api.routers.webhooks.github import (
                consumer_router as github_webhook_consumer,
            )

            faststream_plugin.add_router(pr_consumer)
            faststream_plugin.add_router(github_webhook_consumer)

        # Start all plugins
        for plugin in self._plugins:
            plugin_name = plugin.__class__.__name__
            try:
                await plugin.startup()
                logger.info(f"✓ Plugin started: {plugin_name}")
            except Exception as e:
                logger.error(f"Failed to start plugin {plugin_name}: {e}", exc_info=True)
                raise

    async def shutdown(self) -> None:
        """Shutdown all plugins in reverse order."""
        logger.info("Shutting down application...")

        # Shutdown plugins (each plugin handles its own cleanup)
        for plugin in reversed(self._plugins):
            plugin_name = plugin.__class__.__name__
            try:
                await plugin.shutdown()
            except Exception as e:
                logger.error(f"Error stopping plugin {plugin_name}: {e}", exc_info=True)

        logger.info("Application shutdown complete")

    async def run(self) -> None:
        """Run the application.

        Plugins handle their own runtime (e.g., web server starts in startup()).
        This method just waits for shutdown signals.
        """
        logger.info("Application running...")

        # Setup signal handlers for graceful shutdown using asyncio
        # This MUST use loop.add_signal_handler to override uvicorn's handlers
        shutdown_event = asyncio.Event()
        loop = asyncio.get_running_loop()

        def signal_handler():
            # Close SSE connections before uvicorn can block waiting for them
            # Import here to avoid test import conflicts

            asyncio.create_task(  # noqa: RUF006
                self._shutdown_sse_and_signal(sse_manager, shutdown_event)
            )

        # Use loop.add_signal_handler - this takes precedence over signal.signal()
        # and will override any handlers uvicorn installs
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)

        try:
            # Wait for shutdown signal
            await shutdown_event.wait()
        finally:
            # Remove our signal handlers
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.remove_signal_handler(sig)
            await self.shutdown()

    async def _shutdown_sse_and_signal(self, sse_manager, shutdown_event: asyncio.Event) -> None:
        """Close SSE connections and then signal main shutdown."""
        await sse_manager.shutdown_all()
        await asyncio.sleep(0.2)  # Give generators time to exit
        shutdown_event.set()

    async def register_plugins(self) -> None:
        """Register and start all enabled plugins from config.

        Discovers plugins from BUILTIN_PLUGINS and entry points,
        sorts by priority, then instantiates enabled plugins.
        """
        # Merge built-in and external plugins
        all_plugin_classes: list[type[BasePlugin]] = list(BUILTIN_PLUGINS)

        # Discover external plugins via entry points
        for ep in importlib.metadata.entry_points(group="reviewate.plugins"):
            try:
                plugin_class = ep.load()
                all_plugin_classes.append(plugin_class)
                logger.info(f"Discovered external plugin: {ep.name} ({plugin_class.__name__})")
            except Exception as e:
                logger.error(f"Failed to load external plugin '{ep.name}': {e}")

        # Sort by priority (lower = earlier)
        all_plugin_classes.sort(key=lambda cls: cls.priority)

        plugins = []
        for plugin_class in all_plugin_classes:
            plugin_name = plugin_class.plugin_name

            # Get raw config dict from YAML
            config_data = self._backend_config.plugins.get_raw_config(plugin_name)

            # Instantiate typed config
            plugin_config = plugin_class.config_class(**config_data)

            # Skip if disabled
            if not plugin_config.enabled:
                logger.debug(f"Plugin '{plugin_name}' is disabled, skipping")
                continue

            # Instantiate plugin with its config
            plugin = plugin_class(plugin_config)
            plugins.append(plugin)

        if not plugins:
            logger.warning("No plugins enabled! Check your configuration.")

        # Start all registered plugins
        await self.startup(plugins)

    @classmethod
    async def from_config(cls, config_path: str) -> Self:
        """Create application and register plugins from config.

        Args:
            config_path: Path to YAML configuration file

        Returns:
            Application instance with all plugins started
        """
        # Load configuration
        config = BackendConfig.from_yaml(config_path)
        app = cls(config)

        # Register and start all enabled plugins
        await app.register_plugins()

        return app
