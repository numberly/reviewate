"""Tests for Container Plugin lifecycle."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.plugins.container.config import (
    ContainerPluginConfig,
    DockerConfig,
    WatcherConfig,
)
from api.plugins.container.plugin import ContainerPlugin


class TestContainerPlugin:
    """Tests for ContainerPlugin class."""

    @pytest.fixture
    def docker_config(self):
        """Create Docker config fixture."""
        return DockerConfig(
            socket="/var/run/docker.sock",
            image="reviewate/code-reviewer:latest",
            memory_limit="2g",
            cpu_limit=2.0,
            timeout=600,
        )

    @pytest.fixture
    def watcher_config(self):
        """Create watcher config fixture."""
        return WatcherConfig(
            enabled=True,
            reconcile_interval=60,
        )

    @pytest.fixture
    def plugin_config(self, docker_config, watcher_config):
        """Create plugin config fixture."""
        return ContainerPluginConfig(
            enabled=True,
            backend="docker",
            docker=docker_config,
            watcher=watcher_config,
        )

    @pytest.fixture
    def plugin_config_watcher_disabled(self, docker_config):
        """Create plugin config with watcher disabled."""
        return ContainerPluginConfig(
            enabled=True,
            backend="docker",
            docker=docker_config,
            watcher=WatcherConfig(enabled=False, reconcile_interval=60),
        )

    @pytest.fixture
    def mock_app(self):
        """Create mock app fixture."""
        mock_broker = MagicMock()
        mock_app = MagicMock()
        mock_app.faststream.get_broker.return_value = mock_broker
        return mock_app

    @pytest.fixture
    def mock_backend(self):
        """Create mock backend fixture."""
        mock_backend = MagicMock()
        mock_backend.start_watching = AsyncMock()
        mock_backend.stop_watching = AsyncMock()
        return mock_backend

    def test_plugin_initialization(self, plugin_config):
        """Test plugin initializes with config."""
        plugin = ContainerPlugin(plugin_config)

        assert plugin.config == plugin_config
        assert plugin._backend is None
        assert plugin._reconcile_task is None

    @pytest.mark.asyncio
    @patch("api.plugins.container.plugin.DockerBackend")
    @patch("api.plugins.container.plugin.get_current_app")
    async def test_startup_initializes_docker_backend(
        self, mock_get_app, mock_docker_class, plugin_config, mock_app, mock_backend
    ):
        """Test startup initializes Docker backend."""
        mock_get_app.return_value = mock_app
        mock_docker_class.return_value = mock_backend
        mock_broker = mock_app.faststream.get_broker.return_value

        plugin = ContainerPlugin(plugin_config)
        await plugin.startup()

        mock_redis = mock_app.faststream.get_redis.return_value
        mock_docker_class.assert_called_once_with(plugin_config.docker, mock_broker, mock_redis)
        mock_backend.start_watching.assert_called_once()
        assert plugin._backend == mock_backend
        assert plugin._reconcile_task is not None

        # Cleanup
        if plugin._reconcile_task:
            plugin._reconcile_task.cancel()

    @pytest.mark.asyncio
    @patch("api.plugins.container.plugin.DockerBackend")
    @patch("api.plugins.container.plugin.get_current_app")
    async def test_startup_without_watcher(
        self,
        mock_get_app,
        mock_docker_class,
        plugin_config_watcher_disabled,
        mock_app,
        mock_backend,
    ):
        """Test startup with watcher disabled."""
        mock_get_app.return_value = mock_app
        mock_docker_class.return_value = mock_backend

        plugin = ContainerPlugin(plugin_config_watcher_disabled)
        await plugin.startup()

        # Watcher should not be started
        mock_backend.start_watching.assert_not_called()
        assert plugin._reconcile_task is None

    @pytest.mark.asyncio
    @patch("api.plugins.container.plugin.get_current_app")
    async def test_startup_requires_docker_config(self, mock_get_app, mock_app):
        """Test startup fails without docker config when backend is docker."""
        mock_get_app.return_value = mock_app

        config = ContainerPluginConfig(
            enabled=True,
            backend="docker",
            docker=None,  # Missing!
            watcher=WatcherConfig(enabled=False, reconcile_interval=60),
        )
        plugin = ContainerPlugin(config)

        with pytest.raises(ValueError, match="Docker config required"):
            await plugin.startup()

    @pytest.mark.asyncio
    async def test_shutdown_stops_watcher(self, plugin_config):
        """Test shutdown stops watcher and cleanup."""
        plugin = ContainerPlugin(plugin_config)

        mock_backend = MagicMock()
        mock_backend.stop_watching = AsyncMock()
        plugin._backend = mock_backend

        # Create a dummy task
        async def dummy_task():
            pass

        plugin._reconcile_task = asyncio.create_task(asyncio.sleep(100))

        await plugin.shutdown()

        mock_backend.stop_watching.assert_called_once()
        assert plugin._reconcile_task is None
        assert plugin._backend is None

    @pytest.mark.asyncio
    async def test_shutdown_without_watcher(self, plugin_config_watcher_disabled):
        """Test shutdown when watcher was not enabled."""
        plugin = ContainerPlugin(plugin_config_watcher_disabled)

        mock_backend = MagicMock()
        mock_backend.stop_watching = AsyncMock()
        plugin._backend = mock_backend

        await plugin.shutdown()

        # stop_watching should not be called since watcher was disabled
        mock_backend.stop_watching.assert_not_called()

    def test_backend_property_raises_when_not_started(self, plugin_config):
        """Test backend property raises when plugin not started."""
        plugin = ContainerPlugin(plugin_config)

        with pytest.raises(RuntimeError, match="ContainerPlugin not started"):
            _ = plugin.backend

    def test_backend_property_returns_backend(self, plugin_config):
        """Test backend property returns backend when started."""
        plugin = ContainerPlugin(plugin_config)
        mock_backend = MagicMock()
        plugin._backend = mock_backend

        assert plugin.backend == mock_backend


class TestContainerPluginConfig:
    """Tests for ContainerPluginConfig validation."""

    def test_default_config(self):
        """Test default config values."""
        config = ContainerPluginConfig()

        assert config.enabled is False
        assert config.backend == "docker"
        assert config.watcher.enabled is True
        assert config.watcher.reconcile_interval == 60

    def test_docker_config(self):
        """Test Docker config validation."""
        docker = DockerConfig(
            socket="/var/run/docker.sock",
            image="test:latest",
            memory_limit="1g",
            cpu_limit=1.0,
            timeout=300,
        )
        config = ContainerPluginConfig(
            enabled=True,
            backend="docker",
            docker=docker,
        )

        assert config.docker == docker
        assert config.docker.image == "test:latest"

    def test_watcher_config(self):
        """Test watcher config validation."""
        watcher = WatcherConfig(
            enabled=False,
            reconcile_interval=120,
        )
        config = ContainerPluginConfig(
            enabled=True,
            watcher=watcher,
        )

        assert config.watcher.enabled is False
        assert config.watcher.reconcile_interval == 120
