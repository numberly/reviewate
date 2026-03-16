"""Container plugin for executing code reviews in Docker/Kubernetes."""

import asyncio
import contextlib
import logging

from api.context import get_current_app
from api.plugins.container.backend import ContainerBackend
from api.plugins.container.config import ContainerPluginConfig
from api.plugins.container.docker import DockerBackend
from api.plugins.container.kubernetes import KubernetesBackend
from api.plugins.plugin import BasePlugin

logger = logging.getLogger(__name__)


class ContainerPlugin(BasePlugin[ContainerPluginConfig]):
    """Plugin for executing code reviews in containers.

    This plugin provides:
    - Container execution (starting review containers)
    - Container watching (monitoring container status and publishing updates)
    - Reconciliation with distributed locking (only one instance reconciles)

    The watcher can be enabled/disabled via config. When enabled, it monitors
    all containers with reviewate labels and publishes status updates to Redis.
    """

    plugin_name = "container"
    config_class = ContainerPluginConfig
    priority = 70

    def __init__(self, config: ContainerPluginConfig):
        """Initialize the container plugin.

        Args:
            config: Plugin configuration
        """
        self.config = config
        self._backend: ContainerBackend | None = None
        self._reconcile_task: asyncio.Task | None = None

    async def startup(self) -> None:
        """Start the container plugin."""
        app = get_current_app()

        # Get broker and Redis from FastStream plugin
        broker = app.faststream.get_broker()
        redis = app.faststream.get_redis()

        # Initialize backend based on config
        if self.config.backend == "docker":
            if self.config.docker is None:
                raise ValueError("Docker config required when backend is 'docker'")
            self._backend = DockerBackend(self.config.docker, broker, redis)
        else:
            if self.config.kubernetes is None:
                raise ValueError("Kubernetes config required when backend is 'kubernetes'")
            self._backend = KubernetesBackend(self.config.kubernetes, broker, redis)

        # Start watcher if enabled
        if self.config.watcher.enabled:
            await self._backend.start_watching()
            self._reconcile_task = asyncio.create_task(self._reconcile_loop())

    async def _reconcile_loop(self) -> None:
        """Periodically reconcile container state with distributed locking.

        Only one instance will perform reconciliation at a time, preventing
        duplicate work in multi-instance deployments.
        """
        while True:
            try:
                await asyncio.sleep(self.config.watcher.reconcile_interval)

                if not self._backend:
                    continue

                # Try to acquire distributed lock
                if not await self._backend.acquire_reconcile_lock():
                    logger.debug("Skipping reconciliation - lock held by another instance")
                    continue

                try:
                    await self._backend.reconcile()
                finally:
                    await self._backend.release_reconcile_lock()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in reconciliation loop: {e}")

    async def shutdown(self) -> None:
        """Stop the container plugin."""
        # Cancel reconciliation task
        if self._reconcile_task:
            self._reconcile_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reconcile_task
            self._reconcile_task = None

        # Stop watcher if it was running
        if self._backend and self.config.watcher.enabled:
            await self._backend.stop_watching()

        self._backend = None

    @property
    def backend(self) -> ContainerBackend:
        """Get the container backend.

        Returns:
            Container backend instance

        Raises:
            RuntimeError: If plugin not started
        """
        if not self._backend:
            raise RuntimeError("ContainerPlugin not started")
        return self._backend
