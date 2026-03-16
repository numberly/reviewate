"""FastStream consumer for repository update events.

Subscribes to Redis events and fans them out to connected SSE clients.
Uses the shared SSE manager for client registration.
"""

import asyncio
import logging

from faststream.redis import RedisRouter

from api.routers.repositories.schemas import RepositoryEventMessage
from api.sse import sse_manager

logger = logging.getLogger(__name__)

# Resource type for repository SSE streams
RESOURCE_TYPE = "repository"

# FastStream router for SSE events
router = RedisRouter()


@router.subscriber("reviewate.events.repositories")
async def handle_repository_event(message: RepositoryEventMessage) -> None:
    """Handle repository update events and fan out to SSE clients.

    This subscriber receives events from Redis and broadcasts them
    to all registered SSE client queues for repositories.

    Events are broadcast to clients listening for the organization_id.

    Args:
        message: Typed repository event message
    """
    # Fan out using shared SSE manager - keyed by organization_id
    await sse_manager.broadcast_to_resource(
        RESOURCE_TYPE, message.organization_id, message.model_dump()
    )


def register_client(organization_id: str, max_size: int = 100) -> asyncio.Queue:
    """Register a new SSE client for repository updates.

    Args:
        organization_id: Organization ID to listen for repository updates
        max_size: Maximum queue size

    Returns:
        asyncio.Queue for receiving events
    """
    return sse_manager.register_client(RESOURCE_TYPE, organization_id, max_size)


def unregister_client(organization_id: str, queue: asyncio.Queue) -> None:
    """Unregister an SSE client.

    Args:
        organization_id: Organization ID
        queue: Queue to remove
    """
    sse_manager.unregister_client(RESOURCE_TYPE, organization_id, queue)


def get_client_count(organization_id: str | None = None) -> int:
    """Get number of connected SSE clients.

    Args:
        organization_id: Optional organization ID. If None, returns total for repository type.

    Returns:
        Number of connected clients
    """
    return sse_manager.get_client_count(RESOURCE_TYPE, organization_id)
