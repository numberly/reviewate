"""FastStream plugin for message queue operations."""

from api.plugins.faststream.config import (
    FastStreamPluginConfig,
    FastStreamRedisConfig,
)
from api.plugins.faststream.dependencies import get_faststream_broker
from api.plugins.faststream.plugin import FastStreamPlugin

__all__ = [
    "FastStreamPluginConfig",
    "FastStreamPlugin",
    "FastStreamRedisConfig",
    "get_faststream_broker",
]
