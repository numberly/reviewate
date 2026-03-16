"""Configuration management for Reviewate.

Priority: env vars > config file > defaults.
Config file lives at ~/.reviewate/config.toml (managed by `reviewate config`).
API keys are read from environment only — never stored in the config file.
"""

from __future__ import annotations

import os
import subprocess
from enum import Enum
from urllib.parse import urlparse

from pydantic import BaseModel

from code_reviewer.config_file import (
    get_config_auth,
    get_config_model,
    get_config_url,
    load_config_file,
)
from code_reviewer.errors import _EXCEPTION_MAP, ErrorType


class Platform(str, Enum):
    """Supported Git platforms"""

    GITHUB = "github"
    GITLAB = "gitlab"


def _strip_provider(model: str) -> str:
    """Strip provider prefix: 'openai/gpt-4' -> 'gpt-4', 'sonnet' -> 'sonnet'."""
    return model.split("/", 1)[1] if "/" in model else model


class ConfigError(Exception):
    """Raised when configuration is invalid."""

    pass


_EXCEPTION_MAP[ConfigError] = ErrorType.AUTHENTICATION_FAILED


class Config(BaseModel):
    """Main configuration — loaded from config file + environment variables."""

    api_key: str | None = None
    oauth_token: str | None = None
    base_url: str | None = None
    auth_mode: str | None = None  # 'api_key', 'oauth', 'custom'
    review_model: str | None = None
    utility_model: str | None = None
    gh_token: str | None = None
    gitlab_token: str | None = None
    gitlab_host: str | None = None
    container_mode: bool = False
    debug: bool = False

    def validate_auth(self) -> None:
        """Validate that required auth credentials are present.

        Raises ConfigError with a user-friendly message if auth is missing.
        """
        # API key or OAuth token present: good to go
        if self.api_key or self.oauth_token:
            return

        # OAuth mode: SDK handles auth (logged-in CLI or CLAUDE_CODE_OAUTH_TOKEN)
        if self.auth_mode == "oauth":
            return

        # Custom endpoint: need both URL and API key
        if self.auth_mode == "custom":
            if not self.base_url:
                raise ConfigError(
                    "Custom endpoint selected but REVIEWATE_BASE_URL is not set.\n"
                    "  Set it with: export REVIEWATE_BASE_URL=http://your-endpoint\n"
                    "  Or run: reviewate config"
                )
            raise ConfigError(
                "ANTHROPIC_API_KEY is not set (required for custom endpoint).\n"
                "  Set it with: export ANTHROPIC_API_KEY=your-key\n"
                "  Or run: reviewate config"
            )

        # API key mode or no config
        raise ConfigError(
            "No API credentials found.\n"
            "  Set one of:\n"
            "    export ANTHROPIC_API_KEY=your-key\n"
            "    export CLAUDE_CODE_OAUTH_TOKEN=your-token\n"
            "  Or run: reviewate config"
        )

    @classmethod
    def from_env(cls) -> Config:
        """Load configuration from config file + environment variables."""
        file_data = load_config_file() or {}

        # Config file stores "provider/model" — strip prefix for SDK
        review_model_raw = get_config_model("review", file_data)
        utility_model_raw = get_config_model("utility", file_data)
        review_model = _strip_provider(review_model_raw) if review_model_raw else None
        utility_model = _strip_provider(utility_model_raw) if utility_model_raw else None

        # Env vars override config file (used by backend containers)
        review_model_env = os.getenv("REVIEWATE_REVIEW_MODEL")
        utility_model_env = os.getenv("REVIEWATE_UTILITY_MODEL")
        if review_model_env:
            review_model = review_model_env
        if utility_model_env:
            utility_model = utility_model_env

        # OAuth mode: ignore API key and base URL from env — SDK uses CLI auth
        auth_mode = get_config_auth(file_data)
        if auth_mode == "oauth":
            api_key = None
            base_url = None
            # Remove from process env so SDK subprocess doesn't inherit them
            os.environ.pop("ANTHROPIC_API_KEY", None)
            os.environ.pop("ANTHROPIC_BASE_URL", None)
        else:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            # Base URL: env var > config file [urls] section
            base_url = os.getenv("REVIEWATE_BASE_URL") or os.getenv("ANTHROPIC_BASE_URL")
            if not base_url:
                for raw in (review_model_raw, utility_model_raw):
                    if raw and "/" in raw:
                        provider = raw.split("/", 1)[0]
                        url = get_config_url(provider, file_data)
                        if url:
                            base_url = url
                            break

        return cls(
            api_key=api_key,
            oauth_token=os.getenv("CLAUDE_CODE_OAUTH_TOKEN"),
            base_url=base_url,
            auth_mode=auth_mode,
            review_model=review_model,
            utility_model=utility_model,
            gh_token=os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN"),
            gitlab_token=os.getenv("GITLAB_TOKEN") or os.getenv("GITLAB_ACCESS_TOKEN"),
            gitlab_host=os.getenv("GITLAB_HOST") or _detect_gitlab_host(),
            container_mode=os.getenv("REVIEWATE_CONTAINER_MODE", "") == "1",
            debug=os.getenv("REVIEWATE_DEBUG", "") == "1",
        )

    def build_agent_env(self) -> dict[str, str]:
        """Build environment dict for Agent SDK.

        Respects auth_mode from config file:
        - oauth: no API key or base URL (SDK uses CLI session/token)
        - api_key: API key only
        - custom: API key + base URL
        """
        env: dict[str, str] = {}
        if self.auth_mode != "oauth":
            if self.api_key:
                env["ANTHROPIC_API_KEY"] = self.api_key
            if self.base_url:
                env["ANTHROPIC_BASE_URL"] = self.base_url
        if self.oauth_token:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = self.oauth_token
        if self.gh_token:
            env["GITHUB_TOKEN"] = self.gh_token
        if self.gitlab_token:
            env["GITLAB_TOKEN"] = self.gitlab_token
        if self.gitlab_host:
            env["GITLAB_HOST"] = _normalize_host(self.gitlab_host)
        return env


def _normalize_host(host: str) -> str:
    """Strip scheme and path from a host string.

    'https://gitlab.example.com/api/v4' -> 'gitlab.example.com'
    'gitlab.example.com' -> 'gitlab.example.com'
    """
    if "://" in host:
        host = urlparse(host).hostname or host
    return host.split("/")[0]


def _detect_gitlab_host() -> str | None:
    """Try to detect the GitLab host from glab CLI auth config."""
    try:
        result = subprocess.run(
            ["glab", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # glab prints the hostname on its own line, e.g. "gitlab.numberly.in"
        for line in (result.stdout + result.stderr).splitlines():
            stripped = line.strip()
            # The hostname line has no prefix characters (✓, !, etc.)
            if stripped and "." in stripped and not stripped.startswith(("✓", "!", "✗", " ")):
                return stripped
    except Exception:
        pass
    return None
