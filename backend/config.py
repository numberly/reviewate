"""Configuration management for Reviewate backend.

This module provides type-safe configuration loading from YAML files.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from options import Options


def env_constructor(loader: yaml.Loader, node: yaml.ScalarNode) -> str:
    """YAML constructor for !ENV tag to expand environment variables.

    Supports:
    - !ENV ${VAR} - Required variable (replaced with empty string if not set)
    - !ENV ${VAR:-default} - Optional with default value

    Args:
        loader: YAML loader instance
        node: YAML scalar node containing the environment variable reference

    Returns:
        Expanded environment variable value

    Example:
        In YAML file:
            database_url: !ENV ${DATABASE_URL:-postgresql://localhost/db}
    """
    value = loader.construct_scalar(node)
    pattern = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(:-([^}]*))?\}")

    def replacer(match: re.Match) -> str:
        var_name = match.group(1)
        default = match.group(3)
        env_value = os.getenv(var_name)
        if env_value is not None:
            return env_value
        if default is not None:
            return default
        return ""

    return pattern.sub(replacer, value)


# Register the !ENV tag constructor
yaml.add_constructor("!ENV", env_constructor, Loader=yaml.SafeLoader)  # type: ignore[arg-type]


class PluginsConfig(BaseModel):
    """Plugins configuration - stores raw dict configs.

    Uses extra="allow" so unknown plugin names (e.g., from private plugins)
    are accepted without crashing.
    """

    model_config = ConfigDict(extra="allow")

    sentry: dict[str, Any] = Field(default_factory=dict)
    web: dict[str, Any] = Field(default_factory=dict)
    github: dict[str, Any] = Field(default_factory=dict)
    gitlab: dict[str, Any] = Field(default_factory=dict)
    google: dict[str, Any] = Field(default_factory=dict)
    faststream: dict[str, Any] = Field(default_factory=dict)
    database: dict[str, Any] = Field(default_factory=dict)
    oauth: dict[str, Any] = Field(default_factory=dict)
    sse_events: dict[str, Any] = Field(default_factory=dict)
    container: dict[str, Any] = Field(default_factory=dict)

    def get_raw_config(self, plugin_name: str) -> dict[str, Any]:
        """Get raw config dict for a plugin by name.

        Looks in declared fields first, then falls back to extra data
        for external plugins.

        Args:
            plugin_name: Plugin name (e.g., "database", "billing")

        Returns:
            Raw config dict (empty dict if not found)
        """
        if plugin_name in self.model_fields:
            return getattr(self, plugin_name)
        return (self.model_extra or {}).get(plugin_name, {})


class BackendConfig(BaseModel):
    """Complete backend configuration.

    This class loads configuration from YAML files and provides type-safe access.
    Minimal core config - everything else is in plugins.
    """

    app: str = "reviewate-backend"
    environment: Literal["development", "staging", "production"]

    # Plugins configuration
    plugins: PluginsConfig = Field(default_factory=PluginsConfig)

    # Application options (optional settings)
    options: Options = Field(default_factory=Options)

    # Internal: Path to the config file (set after loading)
    _config_path: str | None = None

    @property
    def config_path(self) -> str:
        """Get the path to the config file.

        Returns:
            Path to config file, or default if not set
        """
        return self._config_path or "configs/local.yaml"

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    @classmethod
    def from_yaml(cls, config_path: str) -> BackendConfig:
        """Load configuration from YAML file in configs/ directory.

        Args:
            config_name: Name of the config file (without .yaml extension)
                        Can be overridden with REVIEWATE_CONFIG env var

        Returns:
            BackendConfig instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        return cls.from_yaml_file(config_path)

    @classmethod
    def from_yaml_file(cls, config_path: Path | str) -> BackendConfig:
        """Load configuration from a specific YAML file path.

        Args:
            config_path: Full path to the YAML config file

        Returns:
            BackendConfig instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        config_file = Path(config_path)

        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_file}")

        # Load YAML (environment variables are expanded via !ENV tag)
        with Path.open(config_file) as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValueError(f"Empty configuration file: {config_file}")

        # Pydantic handles validation automatically!
        instance = cls(**data)
        # Store the config path for later reference
        instance._config_path = str(config_file.absolute())
        return instance
