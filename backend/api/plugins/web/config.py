"""Web server plugin configuration."""

from pydantic import BaseModel, Field


class CORSConfig(BaseModel):
    """CORS configuration for the web server."""

    allow_credentials: bool = True
    allow_methods: list[str] = Field(
        default_factory=lambda: ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]
    )
    allow_headers: list[str] = Field(
        default_factory=lambda: ["content-type", "authorization", "x-requested-with"]
    )
    additional_dev_origins: list[str] = Field(default_factory=list)


class JWTConfig(BaseModel):
    """JWT authentication configuration."""

    secret_key: str
    algorithm: str = "HS256"
    token_expire_days: int = 30


class SessionConfig(BaseModel):
    """Session middleware configuration."""

    secret_key: str
    cookie_name: str = "reviewate_session"
    cookie_domain: str | None = None  # None means cookie is valid for current domain only
    cookie_httponly: bool = True
    cookie_samesite: str = "lax"  # "lax", "strict", or "none"
    cookie_secure: bool = True
    max_age_days: int = Field(default=30, ge=1)


class WebPluginConfig(BaseModel):
    """Web server plugin configuration."""

    enabled: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    workers: int = 1

    # Skip starting uvicorn server (useful for tests with TestClient)
    skip_server: bool = False

    # Frontend URL for CORS and OAuth redirects
    frontend_url: str = "http://localhost:3000"

    # Enable when running behind a reverse proxy (nginx, traefik, etc.)
    # Reads X-Forwarded-Proto and X-Forwarded-For headers
    behind_proxy: bool = False

    # CORS configuration
    cors: CORSConfig = Field(default_factory=CORSConfig)

    # JWT configuration
    jwt: JWTConfig

    # Session configuration
    session: SessionConfig
