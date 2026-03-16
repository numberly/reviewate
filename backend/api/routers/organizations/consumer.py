"""FastStream consumer for organization update events."""

import asyncio
import logging

from faststream.redis import RedisRouter

from api.routers.organizations.schemas import OrganizationEventMessage
from api.sse import sse_manager

logger = logging.getLogger(__name__)

RESOURCE_TYPE = "organization"

router = RedisRouter()


@router.subscriber("reviewate.events.organizations")
async def handle_organization_event(message: OrganizationEventMessage) -> None:
    """Handle organization update events and fan out to SSE clients."""
    await sse_manager.broadcast_to_resource(RESOURCE_TYPE, message.user_id, message.model_dump())


def register_client(user_id: str, max_size: int = 100) -> asyncio.Queue:
    """Register a new SSE client for organization updates."""
    return sse_manager.register_client(RESOURCE_TYPE, user_id, max_size)


def unregister_client(user_id: str, queue: asyncio.Queue) -> None:
    """Unregister an SSE client."""
    sse_manager.unregister_client(RESOURCE_TYPE, user_id, queue)


def get_client_count(user_id: str | None = None) -> int:
    """Get number of connected SSE clients."""
    return sse_manager.get_client_count(RESOURCE_TYPE, user_id)
