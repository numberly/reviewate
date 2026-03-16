"""Global application context for runtime state management.

This module provides a centralized way to access the current application instance
and its configuration from anywhere in the codebase.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api.app import Application

# Global context storage
_app_context: dict[str, Application] = {}


def set_current_app(app: Application) -> None:
    """Register the application instance in global context.

    This should be called during application startup.

    Args:
        app: ReviewateBackend application instance
    """
    _app_context["current_app"] = app


def get_current_app() -> Application:
    """Get the current application instance from global context.

    First tries to get from the global context (set during startup).
    This works for both regular runtime and tests since TestClient
    runs synchronously in the same thread.

    Returns:
        ReviewateBackend application instance with config

    Raises:
        RuntimeError: If app has not been registered in context
    """
    app = _app_context.get("current_app")
    if app is None:
        raise RuntimeError(
            "Application not initialized. Make sure ReviewateBackend has been created and started."
        )
    return app


def clear_current_app() -> None:
    """Clear the application from global context.

    Useful for testing to reset state between tests.
    """
    _app_context.clear()
