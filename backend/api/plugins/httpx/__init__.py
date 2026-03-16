"""HTTPX base plugin for HTTP client functionality.

This module provides BaseHttpPlugin, a base class for HTTP-based plugins
(GitHub, GitLab, Google). It is not a standalone plugin.
"""

from api.plugins.httpx.service import HttpService

__all__ = ["HttpService"]
