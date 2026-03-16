"""FastStream plugin for asynchronous message processing.

This plugin manages the FastStream broker lifecycle and message routing.
"""

import asyncio
import logging
from typing import TYPE_CHECKING

from api.plugins.faststream.config import FastStreamPluginConfig
from api.plugins.plugin import BasePlugin
from faststream.redis import RedisBroker

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class FastStreamPlugin(BasePlugin[FastStreamPluginConfig]):
    """FastStream message queue plugin.

    Manages the FastStream broker lifecycle for processing review jobs.
    """

    plugin_name = "faststream"
    config_class = FastStreamPluginConfig
    priority = 60

    def __init__(self, plugin_config: FastStreamPluginConfig):
        """Initialize FastStream plugin.

        Args:
            plugin_config: FastStream plugin configuration
        """
        self.config = plugin_config
        self._broker: RedisBroker | None = None
        self._redis: Redis | None = None
        self._additional_routers: list = []
        self._broker_task: asyncio.Task | None = None

    def add_router(self, router) -> None:
        """Add a router to be included when broker is created.

        This must be called before startup().

        Args:
            router: FastStream router to include
        """
        self._additional_routers.append(router)
        logger.debug(f"Added router to FastStream plugin (total: {len(self._additional_routers)})")

    async def startup(self) -> None:
        """Start the FastStream Redis broker."""
        try:
            # Create broker
            redis_url = self.config.get_redis_url()
            self._broker = RedisBroker(
                url=redis_url,
                graceful_timeout=self.config.graceful_timeout,
            )

            # Create standalone Redis client for execution tracking, locking, etc.
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(redis_url)

            # Load consumers from config (dynamically import handlers)
            for consumer_config in self.config.consumers:
                try:
                    # Dynamically import router from module path
                    # e.g., "api.routers.queue.consumer:router"
                    module_path, attr_name = consumer_config.handler.rsplit(":", 1)
                    module = __import__(module_path, fromlist=[attr_name])
                    router = getattr(module, attr_name)

                    # Include router in broker
                    self._broker.include_router(router)

                except Exception as e:
                    logger.error(
                        f"Failed to load consumer {consumer_config.handler}: {e}",
                        exc_info=True,
                    )

            # Include routers added via add_router() (e.g., SSE Events plugin)
            for additional_router in self._additional_routers:
                self._broker.include_router(additional_router)

            # Start broker in background task (non-blocking)
            self._broker_task = asyncio.create_task(self._run_broker())
        except Exception as e:
            # Log error but don't crash - queue is optional
            logger.error(f"Failed to start FastStream broker: {e}")
            logger.warning("Queue functionality will not be available - continuing without queue")
            self._broker = None
            # Don't re-raise - queue is optional

    async def _run_broker(self) -> None:
        """Run the FastStream broker (background task)."""
        if not self._broker:
            return

        try:
            await self._broker.start()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error running FastStream broker: {e}", exc_info=True)

    async def shutdown(self) -> None:
        """Shutdown the FastStream broker."""
        # Cancel broker task first
        if self._broker_task and not self._broker_task.done():
            self._broker_task.cancel()
            try:
                await self._broker_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Error waiting for broker task cancellation: {e}", exc_info=True)

        # Stop broker
        if self._broker:
            try:
                await self._broker.stop()
            except Exception as e:
                logger.error(f"Error stopping FastStream broker: {e}", exc_info=True)
            finally:
                self._broker = None
                self._broker_task = None

        # Close Redis client
        if self._redis:
            try:
                await self._redis.aclose()  # type: ignore[attr-defined]
            except Exception as e:
                logger.error(f"Error closing Redis client: {e}")
            finally:
                self._redis = None

    def publish(self, event_data, channel) -> None:
        broker = self.get_broker()
        return broker.publish(event_data, channel=channel)

    def get_broker(self) -> RedisBroker:
        """Get the broker instance for publishing messages.

        Returns:
            FastStream broker instance

        Raises:
            RuntimeError: If broker is not initialized
        """
        if not self._broker:
            raise RuntimeError("FastStream broker not initialized")
        return self._broker

    def get_redis(self) -> Redis:
        """Get the Redis client for direct operations.

        Used for execution tracking, distributed locking, etc.

        Returns:
            Redis async client

        Raises:
            RuntimeError: If Redis client is not initialized
        """
        if not self._redis:
            raise RuntimeError("Redis client not initialized")
        return self._redis
