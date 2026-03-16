"""FastAPI dependencies for FastStream plugin."""

from fastapi import HTTPException

from api.context import get_current_app
from faststream.redis import RedisBroker


def get_faststream_broker() -> RedisBroker:
    """Get FastStream broker instance (FastAPI dependency).

    This dependency injects the FastStream broker into REST handlers,
    allowing them to publish messages without using global context.

    Returns:
        RedisBroker instance

    Raises:
        HTTPException: 503 if FastStream plugin not enabled or broker not initialized

    Example:
        @router.post("/review")
        async def trigger_review(
            broker: RedisBroker = Depends(get_faststream_broker),
        ):
            await broker.publish(message, channel="jobs")
    """
    app = get_current_app()

    if not app.faststream:
        raise HTTPException(
            status_code=503,
            detail="Review queue service is not configured. Please enable FastStream plugin.",
        )

    try:
        return app.faststream.get_broker()
    except RuntimeError as e:
        raise HTTPException(
            status_code=503,
            detail="Review queue service is not available. Please try again later.",
        ) from e
