"""Queue message router - handles async job processing."""

from api.routers.queue.schemas import ReviewJobMessage

# Note: Don't import consumer here to avoid circular imports
# Import from api.routers.queue.consumer directly where needed

__all__ = [
    "ReviewJobMessage",
]
