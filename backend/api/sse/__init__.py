"""Shared SSE (Server-Sent Events) infrastructure.

This module provides reusable components for implementing SSE endpoints
across different resource types (executions, pull requests, etc.).
"""

from .manager import SHUTDOWN_SENTINEL, SSEResourceManager, sse_manager
from .schemas import EXECUTION_SCHEMA, PULL_REQUEST_SCHEMA, SSEEventSchema
from .streaming import make_sse_event, stream_resource_events

__all__ = [
    "SHUTDOWN_SENTINEL",
    "SSEResourceManager",
    "sse_manager",
    "SSEEventSchema",
    "EXECUTION_SCHEMA",
    "PULL_REQUEST_SCHEMA",
    "make_sse_event",
    "stream_resource_events",
]
