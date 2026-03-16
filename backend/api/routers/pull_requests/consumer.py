"""FastStream consumer for pull request update events.

Subscribes to Redis events and fans them out to connected SSE clients.
Uses the shared SSE manager for client registration.
"""

import asyncio
import logging

from faststream.redis import RedisRouter

from api.routers.pull_requests.schemas import PullRequestEventMessage
from api.sse import sse_manager

logger = logging.getLogger(__name__)

# Resource type for pull request SSE streams
RESOURCE_TYPE = "pull_request"

# FastStream router for SSE events
router = RedisRouter()


@router.subscriber("reviewate.events.pull_requests")
async def handle_pull_request_event(message: PullRequestEventMessage) -> None:
    """Handle PR update events and broadcast to all dashboard SSE clients.

    This subscriber receives events from Redis and broadcasts them to
    all connected users. Organization filtering happens in the handler.

    Args:
        message: Typed pull request event message
    """
    # Broadcast to ALL users - they will filter by org membership in their handler
    # This is O(users) instead of O(connections), much better scaling
    all_user_ids = _get_all_connected_user_ids()
    for user_id in all_user_ids:
        await sse_manager.broadcast_to_resource(RESOURCE_TYPE, user_id, message.model_dump())


def _get_all_connected_user_ids() -> list[str]:
    """Get list of all user IDs with active dashboard connections.

    Returns:
        List of user IDs
    """
    if RESOURCE_TYPE not in sse_manager._resources:
        return []
    return list(sse_manager._resources[RESOURCE_TYPE].keys())


def register_client(user_id: str, max_size: int = 100) -> asyncio.Queue:
    """Register a new dashboard SSE client for a user.

    This deduplicates by user_id - multiple tabs for same user share queues.

    Args:
        user_id: User ID for this dashboard connection
        max_size: Maximum queue size

    Returns:
        asyncio.Queue for receiving events
    """
    return sse_manager.register_client(RESOURCE_TYPE, user_id, max_size)


def unregister_client(user_id: str, queue: asyncio.Queue) -> None:
    """Unregister a dashboard SSE client.

    Args:
        user_id: User ID
        queue: Queue to remove
    """
    sse_manager.unregister_client(RESOURCE_TYPE, user_id, queue)


def get_client_count(user_id: str | None = None) -> int:
    """Get number of connected dashboard SSE clients.

    Args:
        user_id: Optional user ID. If None, returns total for all users.

    Returns:
        Number of connected clients
    """
    return sse_manager.get_client_count(RESOURCE_TYPE, user_id)
