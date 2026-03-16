"""Base HTTP plugin for integrations that use HTTP clients.

IMPORTANT: This is a BASE CLASS, not a standalone plugin.
It provides shared HTTP client functionality for GitHub, GitLab, and Google plugins.

Do not register BaseHttpPlugin in the PLUGINS dict in app.py.
Instead, enable specific plugins (github, gitlab, google) that inherit from this class.
"""

from abc import abstractmethod
from typing import TypeVar

from api.plugins.httpx.service import HttpService
from api.plugins.plugin import BasePlugin

ConfigT = TypeVar("ConfigT")


class BaseHttpPlugin(BasePlugin[ConfigT]):
    """Base plugin for HTTP-based integrations.

    Provides shared HTTP client functionality via HttpService.
    Subclasses must implement _get_base_url() and _get_default_headers().
    """

    def __init__(self, plugin_config: ConfigT):
        """Initialize HTTP plugin.

        Args:
            plugin_config: Plugin-specific configuration (e.g., GitHubPluginConfig)
        """
        self.config: ConfigT = plugin_config
        # Create HTTP service immediately - no need for async startup
        self._http = HttpService(
            base_url=self._get_base_url(),
            headers=self._get_default_headers(),
        )

    @abstractmethod
    def _get_base_url(self) -> str:
        """Get the base URL for API requests.

        Returns:
            Base URL string

        Example:
            return "https://api.github.com"
        """
        pass

    @abstractmethod
    def _get_default_headers(self) -> dict[str, str]:
        """Get default headers for API requests.

        Returns:
            Dictionary of headers

        Example:
            return {"Authorization": f"token {self.token}"}
        """
        pass

    async def startup(self) -> None:
        """Start HTTP service."""
        await self._http.on_start()

    async def shutdown(self) -> None:
        """Shutdown the HTTP service."""
        await self._http.on_shutdown()

    @property
    def http(self) -> HttpService:
        """Get HTTP service.

        Returns:
            HttpService instance
        """
        return self._http
