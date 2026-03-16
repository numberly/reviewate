"""Pull requests router - HTTP endpoints and FastStream consumer."""

from .consumer import router as consumer_router
from .handlers import router as http_router

# Alias for web plugin compatibility
router = http_router

__all__ = ["consumer_router", "http_router", "router"]
