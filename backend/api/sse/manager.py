"""SSE client registry manager.

Manages SSE client subscriptions across all resource types.
Replaces the per-module global _sse_queues pattern with a unified manager.
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Sentinel value to signal shutdown to blocked generators
SHUTDOWN_SENTINEL = {"__sse_shutdown__": True}


class SSEResourceManager:
    """Generic SSE client subscription manager for any resource type.

    This manager maintains a registry of SSE client queues organized by
    resource type and resource ID. It replaces module-level global state
    with a composable, testable class instance.

    Structure: _resources[resource_type][resource_id] = [queue1, queue2, ...]

    Example:
        >>> manager = SSEResourceManager()
        >>> queue = manager.register_client("execution", "exec-123")
        >>> manager.get_queues("execution", "exec-123")
        [<Queue>]
        >>> manager.unregister_client("execution", "exec-123", queue)
    """

    def __init__(self) -> None:
        """Initialize empty resource registry."""
        # Structure: {resource_type: {resource_id: [queues]}}
        self._resources: dict[str, dict[str, list[asyncio.Queue]]] = {}

    def register_client(
        self, resource_type: str, resource_id: str, max_size: int = 100
    ) -> asyncio.Queue:
        """Register a new SSE client for resource updates.

        Args:
            resource_type: Type of resource (e.g., "execution", "pull_request")
            resource_id: Unique identifier for the resource
            max_size: Maximum queue size (prevents memory buildup)

        Returns:
            asyncio.Queue for receiving events
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=max_size)

        # Ensure resource type exists
        if resource_type not in self._resources:
            self._resources[resource_type] = {}

        # Ensure resource ID exists
        if resource_id not in self._resources[resource_type]:
            self._resources[resource_type][resource_id] = []

        # Register queue
        self._resources[resource_type][resource_id].append(queue)

        queue_count = len(self._resources[resource_type][resource_id])
        logger.debug(
            f"Registered SSE client for {resource_type}:{resource_id} (total: {queue_count})"
        )

        return queue

    def unregister_client(self, resource_type: str, resource_id: str, queue: asyncio.Queue) -> None:
        """Unregister an SSE client.

        Args:
            resource_type: Type of resource
            resource_id: Unique identifier for the resource
            queue: Queue to remove
        """
        if resource_type not in self._resources:
            logger.warning(f"Resource type {resource_type} not found")
            return

        if resource_id not in self._resources[resource_type]:
            logger.warning(f"Resource ID {resource_id} not found for {resource_type}")
            return

        try:
            self._resources[resource_type][resource_id].remove(queue)
            remaining = len(self._resources[resource_type][resource_id])
            logger.debug(
                f"Unregistered client for {resource_type}:{resource_id} (remaining: {remaining})"
            )

            # Cleanup empty lists
            if not self._resources[resource_type][resource_id]:
                del self._resources[resource_type][resource_id]

            # Cleanup empty resource types
            if not self._resources[resource_type]:
                del self._resources[resource_type]

        except ValueError:
            logger.warning(f"Queue not found for {resource_type}:{resource_id} during unregister")

    def get_queues(self, resource_type: str, resource_id: str) -> list[asyncio.Queue]:
        """Get all queues for a resource.

        Args:
            resource_type: Type of resource
            resource_id: Unique identifier for the resource

        Returns:
            List of queues (empty if none registered)
        """
        if resource_type not in self._resources:
            return []

        return self._resources[resource_type].get(resource_id, [])

    def get_client_count(
        self, resource_type: str | None = None, resource_id: str | None = None
    ) -> int:
        """Get number of connected SSE clients.

        Args:
            resource_type: Optional resource type filter
            resource_id: Optional resource ID filter

        Returns:
            Number of connected clients

        Examples:
            >>> manager.get_client_count()  # Total across all resources
            42
            >>> manager.get_client_count("execution")  # Total for resource type
            15
            >>> manager.get_client_count("execution", "exec-123")  # Specific resource
            3
        """
        if resource_type is None:
            # Total across all resources
            return sum(
                len(queues)
                for resource_dict in self._resources.values()
                for queues in resource_dict.values()
            )

        if resource_type not in self._resources:
            return 0

        if resource_id is None:
            # Total for resource type
            return sum(len(queues) for queues in self._resources[resource_type].values())

        # Specific resource
        return len(self._resources[resource_type].get(resource_id, []))

    def clear_all_clients(self) -> None:
        """Clear all registered clients (for shutdown/testing)."""
        self._resources.clear()
        logger.info("Cleared all SSE clients")

    async def shutdown_all(self) -> None:
        """Signal all SSE connections to close gracefully.

        Pushes a shutdown sentinel to all registered queues, which will
        wake any blocked generators and signal them to exit.
        """
        total_clients = self.get_client_count()
        if total_clients == 0:
            return

        logger.info(f"Signaling {total_clients} SSE clients to shut down")

        # Push shutdown sentinel to all queues
        for resource_type, resource_dict in self._resources.items():
            for resource_id, queues in resource_dict.items():
                for queue in queues:
                    try:
                        queue.put_nowait(SHUTDOWN_SENTINEL)
                    except asyncio.QueueFull:
                        logger.warning(
                            f"SSE queue full for {resource_type}:{resource_id}, "
                            "shutdown signal may be delayed"
                        )

    async def broadcast_to_resource(
        self, resource_type: str, resource_id: str, event_data: dict[str, Any]
    ) -> None:
        """Broadcast an event to all clients for a resource.

        This is a convenience method for consumers to fan out events.

        Args:
            resource_type: Type of resource
            resource_id: Unique identifier for the resource
            event_data: Event data to broadcast
        """
        queues = self.get_queues(resource_type, resource_id)

        if not queues:
            logger.debug(f"No clients registered for {resource_type}:{resource_id}")
            return

        logger.debug(f"Fanning out to {len(queues)} clients for {resource_type}:{resource_id}")

        for queue in queues:
            try:
                queue.put_nowait(event_data)
            except asyncio.QueueFull:
                logger.warning(f"SSE queue full for {resource_type}:{resource_id}, dropping event")


# Global singleton instance
sse_manager = SSEResourceManager()
