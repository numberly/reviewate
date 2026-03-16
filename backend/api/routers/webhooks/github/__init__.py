"""GitHub webhooks router."""

from .consumer import router as consumer_router
from .handlers import router

__all__ = ["router", "consumer_router"]
