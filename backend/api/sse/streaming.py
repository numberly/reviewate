"""Generic SSE streaming utilities.

Provides reusable functions for implementing Server-Sent Events endpoints
across different resource types.
"""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)


def make_sse_event(event_type: str, data: dict | str) -> dict[str, str]:
    """Create SSE event dictionary with consistent formatting.

    Args:
        event_type: Event type ("status", "error", "done", etc.)
        data: Event payload (dict will be JSON-serialized, str will be used as-is)

    Returns:
        SSE event dict with 'event' and 'data' keys

    Example:
        >>> make_sse_event("status", {"id": "123", "status": "running"})
        {"event": "status", "data": '{"id": "123", "status": "running"}'}

        >>> make_sse_event("error", {"error": "Something went wrong"})
        {"event": "error", "data": '{"error": "Something went wrong"}'}
    """
    if isinstance(data, dict):
        data = json.dumps(data)
    return {"event": event_type, "data": data}


async def stream_resource_events(
    resource_id: str,
    *,
    fetch_initial_status: Callable[[str], Awaitable[dict[str, Any] | None]],
    is_terminal: Callable[[dict[str, Any]], bool],
    format_done_event: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    event_type: str = "status",
    register_client: Callable[[str], asyncio.Queue],
    unregister_client: Callable[[str, asyncio.Queue], None],
) -> AsyncGenerator[dict[str, str]]:
    """Stream SSE events for a resource until terminal state.

    Generic SSE event loop that:
    1. Fetches and yields initial resource status via callback
    2. Detects if resource is already in terminal state (early exit)
    3. Registers with event consumer to receive queue events
    4. Yields events as they arrive from the queue
    5. Detects terminal state and sends "done" event
    6. Handles disconnection and cleanup

    This function handles the complete SSE lifecycle including initial status,
    queue registration, event streaming, and cleanup. Business logic (access
    control, data fetching, terminal conditions) is provided via callbacks.

    SCALABLE PATTERN:
    - 1 global Redis connection (background task)
    - Broadcasts to N in-memory Python queues
    - This endpoint just waits on its queue
    - Supports 10k+ concurrent connections

    Args:
        resource_id: Identifier for the resource (execution_id, deployment_id, etc.)
        fetch_initial_status: Async callback that fetches initial resource state.
            Receives resource_id and returns dict with status data, or None if not found.
        is_terminal: Callback that returns True if event represents terminal state.
            Receives event data dict and checks the status field.
        format_done_event: Optional callback to format the "done" event data.
            Receives event data dict and returns formatted dict. If None, uses event_data as-is.
        event_type: SSE event type for status updates (default: "status")
        register_client: Function to register for events.
            Should call sse_manager.register_client(resource_type, resource_id)
        unregister_client: Function to unregister.
            Should call sse_manager.unregister_client(resource_type, resource_id, queue)

    Yields:
        SSE event dicts with 'event' and 'data' keys

    Example:
        >>> from api.sse import sse_manager
        >>> async def fetch_status(exec_id: str) -> dict | None:
        ...     execution = db.get_execution(exec_id)
        ...     if not execution:
        ...         return None
        ...     return {"execution_id": exec_id, "status": execution.status}
        ...
        >>> def is_done(data: dict) -> bool:
        ...     return data.get("status") in ["completed", "failed"]
        ...
        >>> async for event in stream_resource_events(
        ...     resource_id="exec-123",
        ...     fetch_initial_status=fetch_status,
        ...     is_terminal=is_done,
        ...     format_done_event=lambda d: {"id": d["execution_id"], "status": d["status"]},
        ...     register_client=lambda rid: sse_manager.register_client("execution", rid),
        ...     unregister_client=lambda rid, q: sse_manager.unregister_client("execution", rid, q),
        ... ):
        ...     yield event
    """
    # Fetch and send initial status
    initial_data = await fetch_initial_status(resource_id)

    if initial_data is None:
        # Resource not found
        yield make_sse_event("error", {"error": "Resource not found"})
        return

    # Send initial status event
    yield make_sse_event(event_type, initial_data)

    # Check if already in terminal state
    if is_terminal(initial_data):
        # Format done event
        done_data = format_done_event(initial_data) if format_done_event else initial_data
        yield make_sse_event("done", done_data)
        return

    # Register with consumer module to receive events
    queue = register_client(resource_id)

    try:
        # Wait for events from consumer
        while True:
            event_data = await queue.get()

            # Yield status update
            yield make_sse_event(event_type, event_data)

            # Check terminal state
            if is_terminal(event_data):
                # Format done event
                done_data = format_done_event(event_data) if format_done_event else event_data
                yield make_sse_event("done", done_data)
                break

    except asyncio.CancelledError:
        logger.info(f"SSE client disconnected for resource {resource_id}")
        raise
    except Exception as e:
        logger.error(f"SSE error for resource {resource_id}: {e}", exc_info=True)
        yield make_sse_event("error", {"error": str(e)})
    finally:
        unregister_client(resource_id, queue)
