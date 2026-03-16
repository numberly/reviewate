"""Base plugin abstraction.

Plugins are the public API of the application. They implement business logic
and are the only components attached to the Application instance.
"""

from abc import ABC, abstractmethod
from typing import ClassVar, TypeVar

ConfigT = TypeVar("ConfigT")


class BasePlugin[ConfigT](ABC):
    """Base plugin with lifecycle hooks.

    Every feature in the application is implemented as a plugin.
    Plugins can use services internally but must never expose them.
    """

    plugin_name: ClassVar[str]
    config_class: ClassVar[type]
    priority: ClassVar[int] = 100

    config: ConfigT

    @abstractmethod
    async def startup(self) -> None:
        """Initialize the plugin using self.config."""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown the plugin and cleanup resources.

        This method should:
        1. Stop any background tasks
        2. Call on_shutdown() on services
        3. Cleanup any other resources
        """
        pass
