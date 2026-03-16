"""Web server plugin - FastAPI as a plugin.

This wraps FastAPI into a plugin so it can be enabled/disabled via configuration.
"""

import asyncio
import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from api.context import get_current_app
from api.plugins.plugin import BasePlugin
from api.plugins.web.config import WebPluginConfig
from api.routers import (
    auth,
    config,
    linked_repositories,
    organizations,
    pull_requests,
    repositories,
    sources,
    webhooks,
)

logger = logging.getLogger(__name__)


class WebServerPlugin(BasePlugin[WebPluginConfig]):
    """Web server plugin wrapping FastAPI.

    This plugin creates and configures the FastAPI application,
    registers all routers, and manages the web server lifecycle.
    """

    plugin_name = "web"
    config_class = WebPluginConfig
    priority = 50

    def __init__(self, plugin_config: WebPluginConfig):
        """Initialize web server plugin.

        Args:
            plugin_config: Web plugin configuration
        """
        self.config = plugin_config
        self.app: FastAPI | None = None
        self._server_task: asyncio.Task | None = None
        self._server: uvicorn.Server | None = None

    async def startup(self) -> None:
        """Start the FastAPI web server."""
        app = get_current_app()

        # Create FastAPI instance
        self.app = FastAPI(
            title="Reviewate API",
            description="AI-powered code review system API",
            version="1.0.0",
            docs_url="/docs",
            redoc_url="/redoc",
        )

        # Configure CORS
        allowed_origins = [self.config.frontend_url]
        if app._backend_config.is_development:
            allowed_origins.extend(self.config.cors.additional_dev_origins)

        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=self.config.cors.allow_credentials,
            allow_methods=self.config.cors.allow_methods,
            allow_headers=self.config.cors.allow_headers,
        )

        # Add SessionMiddleware - required by Authlib for OAuth state management
        # Note: This is separate from our JWT cookie-based auth
        # SessionMiddleware stores temporary OAuth state, JWT cookies store auth tokens
        max_age = self.config.session.max_age_days * 24 * 60 * 60
        self.app.add_middleware(
            SessionMiddleware,
            secret_key=self.config.session.secret_key,
            max_age=max_age,
            same_site=self.config.session.cookie_samesite,
            https_only=self.config.session.cookie_secure,
        )

        # Handle reverse proxy headers (X-Forwarded-Proto, X-Forwarded-For)
        if self.config.behind_proxy:
            self.app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

        # Register routers
        self.app.include_router(auth.router)
        self.app.include_router(config.router)
        self.app.include_router(linked_repositories.router)
        self.app.include_router(organizations.router)
        self.app.include_router(repositories.router)
        self.app.include_router(pull_requests.router)
        self.app.include_router(sources.router)
        self.app.include_router(webhooks.router)

        # Add health check routes
        @self.app.get("/", tags=["Health"])
        async def root() -> dict[str, str]:
            """Root endpoint - health check."""
            return {
                "status": "ok",
                "message": "Reviewate API is running",
                "environment": app._backend_config.environment,
            }

        @self.app.get("/health", tags=["Health"])
        async def health() -> dict[str, str]:
            """Health check endpoint."""
            return {"status": "healthy"}

        # Start uvicorn server in background task (unless skip_server is True)
        if not self.config.skip_server:
            self._server_task = asyncio.create_task(self._run_server())

    async def _run_server(self) -> None:
        """Run the uvicorn server."""
        config = uvicorn.Config(
            self.app,
            host=self.config.host,
            port=self.config.port,
            reload=self.config.reload,
            log_level="warning",
            access_log=False,
        )
        self._server = uvicorn.Server(config)
        # Disable uvicorn's signal handlers - Application.run() handles signals
        self._server.install_signal_handlers = lambda: None
        try:
            print(f"Starting web server at http://{self.config.host}:{self.config.port}/")
            await self._server.serve()
        except asyncio.CancelledError:
            logger.info("Server task cancelled")
            raise

    async def shutdown(self) -> None:
        """Shutdown the web server."""
        # Signal the uvicorn server to shutdown gracefully
        # Note: SSE connections are closed in Application._shutdown_sse_and_signal()
        # before this method is called
        if self._server:
            self._server.should_exit = True
            self._server.force_exit = True

        # Wait for the server task to complete
        if self._server_task and not self._server_task.done():
            try:
                # Wait up to 2 seconds for graceful shutdown (reduced from 5)
                await asyncio.wait_for(self._server_task, timeout=2.0)
            except TimeoutError:
                logger.warning("Server shutdown timeout, forcing shutdown...")
                self._server_task.cancel()
                import contextlib

                with contextlib.suppress(asyncio.CancelledError):
                    await self._server_task
            except asyncio.CancelledError:
                pass

        # Clear references
        self._server = None
        self._server_task = None

    def get_asgi_app(self) -> FastAPI:
        """Get the ASGI application for running with uvicorn.

        Returns:
            FastAPI application instance

        Raises:
            RuntimeError: If plugin not started
        """
        if not self.app:
            raise RuntimeError("WebServerPlugin not started")
        return self.app
