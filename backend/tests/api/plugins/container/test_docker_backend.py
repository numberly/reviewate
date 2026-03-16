"""Tests for Docker backend container execution and watching."""

import json
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.plugins.container.config import DockerConfig
from api.plugins.container.docker import DockerBackend
from api.plugins.container.utils import (
    ERROR_PATTERN,
    RESULT_PATTERN,
    STATUS_PATTERN,
    build_env_vars,
    parse_memory_limit,
)
from api.routers.queue.schemas import LinkedRepoMessage
from tests.utils.factories import ReviewJobMessageFactory


class TestParseMemoryLimit:
    """Tests for parse_memory_limit function."""

    def test_parse_gigabytes(self):
        """Test parsing gigabyte values."""
        assert parse_memory_limit("2g") == 2 * 1024 * 1024 * 1024
        assert parse_memory_limit("1G") == 1024 * 1024 * 1024

    def test_parse_megabytes(self):
        """Test parsing megabyte values."""
        assert parse_memory_limit("512m") == 512 * 1024 * 1024
        assert parse_memory_limit("256M") == 256 * 1024 * 1024

    def test_parse_kilobytes(self):
        """Test parsing kilobyte values."""
        assert parse_memory_limit("1024k") == 1024 * 1024
        assert parse_memory_limit("512K") == 512 * 1024

    def test_parse_bytes(self):
        """Test parsing raw byte values."""
        assert parse_memory_limit("1073741824") == 1073741824

    def test_parse_with_whitespace(self):
        """Test parsing with leading/trailing whitespace."""
        assert parse_memory_limit("  2g  ") == 2 * 1024 * 1024 * 1024


class TestLogPatterns:
    """Tests for log parsing regex patterns."""

    def test_result_pattern(self):
        """Test RESULT_PATTERN matches correctly."""
        line = '[REVIEWATE:RESULT] {"status": "success", "comments": []}'
        match = RESULT_PATTERN.search(line)
        assert match is not None
        assert match.group(1) == '{"status": "success", "comments": []}'

    def test_error_pattern(self):
        """Test ERROR_PATTERN matches correctly."""
        line = '[REVIEWATE:ERROR] {"error": "timeout", "message": "Took too long"}'
        match = ERROR_PATTERN.search(line)
        assert match is not None
        assert match.group(1) == '{"error": "timeout", "message": "Took too long"}'

    def test_status_pattern(self):
        """Test STATUS_PATTERN matches correctly."""
        line = "[REVIEWATE:STATUS] analyzing"
        match = STATUS_PATTERN.search(line)
        assert match is not None
        assert match.group(1) == "analyzing"


class TestDockerBackend:
    """Tests for DockerBackend class."""

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
    def mock_app(self):
        """Create mock app with options fixture."""
        mock_options = MagicMock()
        mock_options.code_reviewer.oauth_token = None
        mock_options.code_reviewer.anthropic_api_key = "test-anthropic-key"
        mock_options.code_reviewer.anthropic_base_url = None
        mock_options.code_reviewer.review_model = None
        mock_options.code_reviewer.utility_model = None

        mock_app = MagicMock()
        mock_app.options = mock_options

        # Mock GitHub plugin for installation token
        mock_app.github = MagicMock()
        mock_app.github.get_installation_access_token = AsyncMock(return_value="github-token-123")

        # Mock database plugin (None by default, set in specific tests)
        mock_app.database = None

        return mock_app

    @pytest.fixture
    def mock_broker(self):
        """Create mock Redis broker fixture."""
        broker = MagicMock()
        broker.publish = AsyncMock()
        return broker

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client fixture."""
        redis = MagicMock()
        redis.sadd = AsyncMock(return_value=1)
        redis.srem = AsyncMock(return_value=1)
        redis.smembers = AsyncMock(return_value=set())
        redis.sismember = AsyncMock(return_value=False)
        redis.set = AsyncMock(return_value=True)
        redis.delete = AsyncMock(return_value=1)
        return redis

    @pytest.fixture
    def backend(self, docker_config, mock_broker, mock_redis):
        """Create DockerBackend instance with mocked dependencies."""
        return DockerBackend(docker_config, mock_broker, mock_redis)

    @pytest.mark.asyncio
    @patch("api.plugins.container.utils.get_current_app")
    async def test_start_container_success(self, mock_get_app, backend, mock_app):
        """Test successful container start."""
        mock_get_app.return_value = mock_app
        job = ReviewJobMessageFactory.build(
            platform="github",
            organization="test-org",
            repository="test-repo",
        )

        # Mock Docker client
        mock_container = MagicMock()
        mock_container.id = "abc123def456"
        mock_container.start = AsyncMock()

        mock_docker = MagicMock()
        mock_docker.images.inspect = AsyncMock()
        mock_docker.containers.create = AsyncMock(return_value=mock_container)
        backend._get_docker = AsyncMock(return_value=mock_docker)

        container_id = await backend.start_container("exec-123", job)

        assert container_id == "abc123def456"
        mock_docker.containers.create.assert_called_once()
        mock_container.start.assert_called_once()

        # Verify container config
        call_kwargs = mock_docker.containers.create.call_args
        config = call_kwargs.kwargs["config"]
        assert config["Image"] == "reviewate/code-reviewer:latest"
        assert "reviewate.execution_id" in config["Labels"]
        assert config["Labels"]["reviewate.execution_id"] == "exec-123"

    @pytest.mark.asyncio
    @patch("api.plugins.container.utils.db_get_organization_by_id")
    @patch("api.plugins.container.utils.get_current_app")
    async def test_start_container_sets_cli_args_and_env_vars(
        self, mock_get_app, mock_get_org, backend, mock_app
    ):
        """Test that container is started with correct CLI args and env vars."""
        # Set up mock organization with installation_id for GitHub
        mock_org = MagicMock()
        mock_org.installation_id = "github-installation-123"
        mock_get_org.return_value = mock_org

        # Set up database mock with session context manager
        mock_db_session = MagicMock()

        @contextmanager
        def mock_session_cm():
            yield mock_db_session

        mock_app.database = MagicMock()
        mock_app.database.session = mock_session_cm
        mock_get_app.return_value = mock_app

        job = ReviewJobMessageFactory.build(
            platform="github",
            organization="test-org",
            repository="test-repo",
            source_branch="feature/test",
            target_branch="main",
            commit_sha="abc123",
            pull_request_number=42,
            workflow="review",
        )

        mock_container = MagicMock()
        mock_container.id = "container123"
        mock_container.start = AsyncMock()

        mock_docker = MagicMock()
        mock_docker.images.inspect = AsyncMock()
        mock_docker.containers.create = AsyncMock(return_value=mock_container)
        backend._get_docker = AsyncMock(return_value=mock_docker)

        await backend.start_container("exec-123", job)

        call_kwargs = mock_docker.containers.create.call_args
        config = call_kwargs.kwargs["config"]

        # Check CLI args (positional format)
        cmd = config["Cmd"]
        assert cmd[0] == "review"
        assert "test-org/test-repo" in cmd
        assert "-p" in cmd
        assert "42" in cmd
        assert "--platform" in cmd
        assert "github" in cmd

        # Check env vars (only API keys and platform token)
        env_list = config["Env"]
        assert "ANTHROPIC_API_KEY=test-anthropic-key" in env_list
        assert "GITHUB_TOKEN=github-token-123" in env_list

    @pytest.mark.asyncio
    @patch("api.plugins.container.utils.get_current_app")
    async def test_start_container_gitlab_platform(self, mock_get_app, backend, mock_app):
        """Test GitLab container start with CLI args."""
        # Set up mock for GitLab token (need database mock with session context manager)
        mock_org = MagicMock()
        mock_org.gitlab_access_token_encrypted = "encrypted-org-token"

        # Create a proper context manager mock for session()
        mock_db_session = MagicMock()

        @contextmanager
        def mock_session_cm():
            yield mock_db_session

        mock_app.database = MagicMock()
        mock_app.database.session = mock_session_cm
        mock_app.database.decrypt = MagicMock(return_value="gitlab-token-123")
        mock_get_app.return_value = mock_app

        job = ReviewJobMessageFactory.build(
            platform="gitlab",
            organization="test-group",
            repository="test-project",
            pull_request_number=99,
            workflow="summarize",
        )

        mock_container = MagicMock()
        mock_container.id = "container123"
        mock_container.start = AsyncMock()

        mock_docker = MagicMock()
        mock_docker.images.inspect = AsyncMock()
        mock_docker.containers.create = AsyncMock(return_value=mock_container)
        backend._get_docker = AsyncMock(return_value=mock_docker)

        # Mock the db functions at their usage location in utils.py
        with (
            patch("api.plugins.container.utils.db_get_organization_by_id", return_value=mock_org),
            patch("api.plugins.container.utils.db_get_repository_by_id", return_value=None),
        ):
            await backend.start_container("exec-123", job)

        call_kwargs = mock_docker.containers.create.call_args
        config = call_kwargs.kwargs["config"]

        # Check CLI args for GitLab (positional format)
        cmd = config["Cmd"]
        assert cmd[0] == "summary"
        assert "test-group/test-project" in cmd
        assert "--platform" in cmd
        assert "gitlab" in cmd

        # Check GitLab token in env
        env_list = config["Env"]
        assert "GITLAB_TOKEN=gitlab-token-123" in env_list

        # Verify decrypt was called with the encrypted token
        mock_app.database.decrypt.assert_called_once_with("encrypted-org-token")

    @pytest.mark.asyncio
    @patch("api.plugins.container.utils.get_current_app")
    async def test_start_container_gitlab_fallback_to_repo_token(
        self, mock_get_app, backend, mock_app
    ):
        """Test GitLab container start falls back to repo token when org token is empty."""
        # Org has no token, but repo does
        mock_org = MagicMock()
        mock_org.gitlab_access_token_encrypted = None

        mock_repo = MagicMock()
        mock_repo.gitlab_access_token_encrypted = "encrypted-repo-token"

        mock_db_session = MagicMock()

        @contextmanager
        def mock_session_cm():
            yield mock_db_session

        mock_app.database = MagicMock()
        mock_app.database.session = mock_session_cm
        mock_app.database.decrypt = MagicMock(return_value="gitlab-repo-token-123")
        mock_get_app.return_value = mock_app

        job = ReviewJobMessageFactory.build(
            platform="gitlab",
            organization="test-group",
            repository="test-project",
            pull_request_number=99,
            workflow="review",
        )

        mock_container = MagicMock()
        mock_container.id = "container123"
        mock_container.start = AsyncMock()

        mock_docker = MagicMock()
        mock_docker.images.inspect = AsyncMock()
        mock_docker.containers.create = AsyncMock(return_value=mock_container)
        backend._get_docker = AsyncMock(return_value=mock_docker)

        # Mock the db functions - org has no token, repo has token
        with (
            patch("api.plugins.container.utils.db_get_organization_by_id", return_value=mock_org),
            patch("api.plugins.container.utils.db_get_repository_by_id", return_value=mock_repo),
        ):
            await backend.start_container("exec-123", job)

        call_kwargs = mock_docker.containers.create.call_args
        config = call_kwargs.kwargs["config"]

        # Check GitLab token in env (should be repo token)
        env_list = config["Env"]
        assert "GITLAB_TOKEN=gitlab-repo-token-123" in env_list

        # Verify decrypt was called with the repo's encrypted token
        mock_app.database.decrypt.assert_called_once_with("encrypted-repo-token")

    @pytest.mark.asyncio
    async def test_stop_container_success(self, backend):
        """Test successful container stop."""
        mock_container = MagicMock()
        mock_container.stop = AsyncMock()

        mock_docker = MagicMock()
        mock_docker.containers.get = AsyncMock(return_value=mock_container)
        backend._get_docker = AsyncMock(return_value=mock_docker)

        await backend.stop_container("container123")

        mock_docker.containers.get.assert_called_once_with("container123")
        mock_container.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_container_handles_error(self, backend):
        """Test stop_container handles errors gracefully."""
        mock_docker = MagicMock()
        mock_docker.containers.get = AsyncMock(side_effect=Exception("Container not found"))
        backend._get_docker = AsyncMock(return_value=mock_docker)

        # Should not raise
        await backend.stop_container("nonexistent")

    @pytest.mark.asyncio
    async def test_publish_status(self, backend, mock_broker):
        """Test publishing status updates to Redis."""
        await backend.publish_status(
            execution_id="exec-123",
            status="processing",
            container_id="container456",
        )

        mock_broker.publish.assert_called_once()
        call_args = mock_broker.publish.call_args
        message = call_args.args[0]

        assert call_args.kwargs["stream"] == "reviewate.execution.status"
        assert call_args.kwargs["maxlen"] == 10000
        assert message["execution_id"] == "exec-123"
        assert message["status"] == "processing"
        assert message["container_id"] == "container456"

    @pytest.mark.asyncio
    async def test_get_container_logs_result_success(self, backend):
        """Test parsing successful result from container logs."""
        result_data = {"status": "success", "comments": [{"line": 10, "message": "Good code!"}]}
        log_output = f"Starting review...\n[REVIEWATE:RESULT] {json.dumps(result_data)}\nDone."

        mock_container = MagicMock()
        mock_container.log = AsyncMock(return_value=[log_output])

        mock_docker = MagicMock()
        mock_docker.containers.get = AsyncMock(return_value=mock_container)
        backend._get_docker = AsyncMock(return_value=mock_docker)

        result, error = await backend._get_container_logs_result("container123")

        assert result == result_data
        assert error is None

    @pytest.mark.asyncio
    async def test_get_container_logs_result_with_error(self, backend):
        """Test parsing error from container logs."""
        error_data = {"type": "timeout", "message": "Review took too long"}
        log_output = f"Starting review...\n[REVIEWATE:ERROR] {json.dumps(error_data)}\nFailed."

        mock_container = MagicMock()
        mock_container.log = AsyncMock(return_value=[log_output])

        mock_docker = MagicMock()
        mock_docker.containers.get = AsyncMock(return_value=mock_container)
        backend._get_docker = AsyncMock(return_value=mock_docker)

        result, error_info = await backend._get_container_logs_result("container123")

        assert result is None
        assert error_info == ("timeout", "Review took too long")

    @pytest.mark.asyncio
    async def test_get_container_logs_result_plain_error(self, backend):
        """Test parsing plain text error from container logs."""
        log_output = "Starting review...\n[REVIEWATE:ERROR] Something went wrong\nFailed."

        mock_container = MagicMock()
        mock_container.log = AsyncMock(return_value=[log_output])

        mock_docker = MagicMock()
        mock_docker.containers.get = AsyncMock(return_value=mock_container)
        backend._get_docker = AsyncMock(return_value=mock_docker)

        result, error_info = await backend._get_container_logs_result("container123")

        assert result is None
        assert error_info == ("internal_error", "Something went wrong")

    @pytest.mark.asyncio
    async def test_handle_container_event_start(self, backend, mock_broker):
        """Test that START events are ignored (processing is published at registration)."""
        event = {
            "Action": "start",
            "Actor": {
                "ID": "container123",
                "Attributes": {
                    "reviewate.execution_id": "exec-456",
                },
            },
        }

        await backend._handle_container_event(event)

        # START events no longer publish — processing is gated by SADD in register_execution
        mock_broker.publish.assert_not_called()

    @pytest.mark.asyncio
    @patch.object(DockerBackend, "_cleanup_container", new_callable=AsyncMock)
    @patch.object(DockerBackend, "_get_container_logs_result", new_callable=AsyncMock)
    async def test_handle_container_event_die_success(
        self, mock_parse, mock_cleanup, backend, mock_broker
    ):
        """Test handling container die event with successful exit."""
        result_data = {"status": "success", "comments": []}
        mock_parse.return_value = (result_data, None)

        event = {
            "Action": "die",
            "Actor": {
                "ID": "container123",
                "Attributes": {
                    "reviewate.execution_id": "exec-456",
                    "exitCode": "0",
                },
            },
        }

        await backend._handle_container_event(event)

        mock_broker.publish.assert_called_once()
        message = mock_broker.publish.call_args.args[0]
        assert message["execution_id"] == "exec-456"
        assert message["status"] == "completed"
        assert message["exit_code"] == 0
        assert message["result"] == result_data

    @pytest.mark.asyncio
    @patch.object(DockerBackend, "_cleanup_container", new_callable=AsyncMock)
    @patch.object(DockerBackend, "_get_container_logs_result", new_callable=AsyncMock)
    async def test_handle_container_event_die_failure(
        self, mock_parse, mock_cleanup, backend, mock_broker
    ):
        """Test handling container die event with failed exit."""
        mock_parse.return_value = (None, ("internal_error", "Process crashed"))

        event = {
            "Action": "die",
            "Actor": {
                "ID": "container123",
                "Attributes": {
                    "reviewate.execution_id": "exec-456",
                    "exitCode": "1",
                },
            },
        }

        await backend._handle_container_event(event)

        mock_broker.publish.assert_called_once()
        message = mock_broker.publish.call_args.args[0]
        assert message["execution_id"] == "exec-456"
        assert message["status"] == "failed"
        assert message["exit_code"] == 1
        assert message["error_type"] == "internal_error"
        assert message["error_message"] == "Process crashed"

    @pytest.mark.asyncio
    async def test_handle_container_event_ignores_non_reviewate(self, backend, mock_broker):
        """Test that non-reviewate containers are ignored."""
        event = {
            "Action": "start",
            "Actor": {
                "ID": "container123",
                "Attributes": {},  # No reviewate.execution_id
            },
        }

        await backend._handle_container_event(event)

        mock_broker.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_container_success(self, backend):
        """Test successful container cleanup."""
        mock_container = MagicMock()
        mock_container.delete = AsyncMock()

        mock_docker = MagicMock()
        mock_docker.containers.get = AsyncMock(return_value=mock_container)
        backend._get_docker = AsyncMock(return_value=mock_docker)

        await backend._cleanup_container("container123")

        mock_container.delete.assert_called_once_with(force=True)

    @pytest.mark.asyncio
    async def test_cleanup_container_handles_error(self, backend):
        """Test cleanup handles errors gracefully."""
        mock_docker = MagicMock()
        mock_docker.containers.get = AsyncMock(side_effect=Exception("Container gone"))
        backend._get_docker = AsyncMock(return_value=mock_docker)

        # Should not raise
        await backend._cleanup_container("nonexistent")

    @pytest.mark.asyncio
    @patch.object(DockerBackend, "fail_stale_db_executions", new_callable=AsyncMock)
    @patch.object(DockerBackend, "_cleanup_container", new_callable=AsyncMock)
    @patch.object(DockerBackend, "_get_container_logs_result", new_callable=AsyncMock)
    async def test_reconcile_processes_exited_containers(
        self, mock_parse, mock_cleanup, mock_fail_stale, backend, mock_broker
    ):
        """Test reconciliation processes exited containers."""
        result_data = {"status": "success", "comments": []}
        mock_parse.return_value = (result_data, None)

        # Mock container info
        mock_container = MagicMock()
        mock_container.show = AsyncMock(
            return_value={
                "Id": "container123",
                "Config": {
                    "Labels": {
                        "reviewate.execution_id": "exec-456",
                    }
                },
                "State": {
                    "Status": "exited",
                    "ExitCode": 0,
                },
            }
        )

        mock_docker = MagicMock()
        mock_docker.containers.list = AsyncMock(return_value=[mock_container])
        backend._get_docker = AsyncMock(return_value=mock_docker)

        await backend.reconcile()

        mock_broker.publish.assert_called_once()
        message = mock_broker.publish.call_args.args[0]
        assert message["execution_id"] == "exec-456"
        assert message["status"] == "completed"

        # Stale DB check should be called with empty set (no running containers)
        mock_fail_stale.assert_called_once_with(set())

    @pytest.mark.asyncio
    async def test_start_watching(self, backend):
        """Test start watching creates task."""
        mock_docker = MagicMock()
        backend._get_docker = AsyncMock(return_value=mock_docker)

        await backend.start_watching()

        assert backend._running is True
        assert backend._watch_task is not None

        # Cleanup
        backend._running = False
        backend._watch_task.cancel()

    @pytest.mark.asyncio
    async def test_stop_watching(self, backend):
        """Test stop watching cleans up resources."""
        mock_docker = MagicMock()
        mock_docker.close = AsyncMock()
        backend._docker = mock_docker
        backend._running = True
        backend._watch_task = None

        await backend.stop_watching()

        assert backend._running is False
        mock_docker.close.assert_called_once()
        assert backend._docker is None


class TestFailStaleDbExecutions:
    """Tests for ContainerBackend.fail_stale_db_executions."""

    @pytest.fixture
    def docker_config(self):
        return DockerConfig(
            socket="/var/run/docker.sock",
            image="reviewate/code-reviewer:latest",
            memory_limit="2g",
            cpu_limit=2.0,
            timeout=600,
        )

    @pytest.fixture
    def mock_broker(self):
        broker = MagicMock()
        broker.publish = AsyncMock()
        return broker

    @pytest.fixture
    def mock_redis(self):
        redis = MagicMock()
        redis.sadd = AsyncMock(return_value=1)
        redis.srem = AsyncMock(return_value=1)
        redis.smembers = AsyncMock(return_value=set())
        redis.sismember = AsyncMock(return_value=False)
        redis.set = AsyncMock(return_value=True)
        redis.delete = AsyncMock(return_value=1)
        return redis

    @pytest.fixture
    def backend(self, docker_config, mock_broker, mock_redis):
        return DockerBackend(docker_config, mock_broker, mock_redis)

    def _make_execution(self, exec_id, status="processing", age_seconds=120):
        """Create a mock execution with given age."""
        from datetime import UTC, datetime, timedelta
        from uuid import UUID

        execution = MagicMock()
        execution.id = UUID(exec_id)
        execution.status = status
        execution.pull_request_id = UUID("00000000-0000-0000-0000-000000000001")
        execution.organization_id = UUID("00000000-0000-0000-0000-000000000002")
        execution.repository_id = UUID("00000000-0000-0000-0000-000000000003")
        execution.created_at = datetime.now(UTC) - timedelta(seconds=age_seconds)
        execution.updated_at = datetime.now(UTC)
        return execution

    @pytest.mark.asyncio
    @patch("api.plugins.container.backend.publish_pull_request_event", new_callable=AsyncMock)
    @patch("api.plugins.container.backend.db_update_execution_status")
    @patch("api.plugins.container.backend.db_get_running_executions")
    @patch("api.plugins.container.backend.get_current_app")
    async def test_fails_stale_execution(
        self, mock_get_app, mock_get_running, mock_update_status, mock_publish_event, backend
    ):
        """Test that old executions without running containers are failed."""
        stale_exec = self._make_execution("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", age_seconds=120)
        mock_get_running.return_value = [stale_exec]

        mock_db = MagicMock()
        mock_app = MagicMock()
        mock_app.database.session.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_app.database.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_app.return_value = mock_app

        await backend.fail_stale_db_executions(set())

        mock_get_running.assert_called_once_with(mock_db, exclude_ids=set())
        mock_update_status.assert_called_once_with(
            mock_db,
            stale_exec.id,
            "failed",
            error_type="container_error",
            error_detail="Container no longer running — cleaned up or crashed",
        )
        mock_publish_event.assert_called_once()

    @pytest.mark.asyncio
    @patch("api.plugins.container.backend.publish_pull_request_event", new_callable=AsyncMock)
    @patch("api.plugins.container.backend.db_update_execution_status")
    @patch("api.plugins.container.backend.db_get_running_executions")
    @patch("api.plugins.container.backend.get_current_app")
    async def test_skips_recent_execution_within_grace_period(
        self, mock_get_app, mock_get_running, mock_update_status, mock_publish_event, backend
    ):
        """Test that executions younger than 60s are not failed (grace period)."""
        recent_exec = self._make_execution("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", age_seconds=10)
        mock_get_running.return_value = [recent_exec]

        mock_db = MagicMock()
        mock_app = MagicMock()
        mock_app.database.session.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_app.database.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_app.return_value = mock_app

        await backend.fail_stale_db_executions(set())

        mock_update_status.assert_not_called()
        mock_publish_event.assert_not_called()

    @pytest.mark.asyncio
    @patch("api.plugins.container.backend.publish_pull_request_event", new_callable=AsyncMock)
    @patch("api.plugins.container.backend.db_update_execution_status")
    @patch("api.plugins.container.backend.db_get_running_executions")
    @patch("api.plugins.container.backend.get_current_app")
    async def test_excludes_running_container_ids(
        self, mock_get_app, mock_get_running, mock_update_status, mock_publish_event, backend
    ):
        """Test that running_exec_ids are passed to SQL exclude."""
        mock_get_running.return_value = []

        mock_db = MagicMock()
        mock_app = MagicMock()
        mock_app.database.session.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_app.database.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_app.return_value = mock_app

        running_ids = {"exec-running-1", "exec-running-2"}
        await backend.fail_stale_db_executions(running_ids)

        mock_get_running.assert_called_once_with(mock_db, exclude_ids=running_ids)

    @pytest.mark.asyncio
    @patch("api.plugins.container.backend.publish_pull_request_event", new_callable=AsyncMock)
    @patch("api.plugins.container.backend.db_update_execution_status")
    @patch("api.plugins.container.backend.db_get_running_executions")
    @patch("api.plugins.container.backend.get_current_app")
    async def test_mixed_stale_and_recent(
        self, mock_get_app, mock_get_running, mock_update_status, mock_publish_event, backend
    ):
        """Test with both stale and recent executions — only stale is failed."""
        stale = self._make_execution("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", age_seconds=120)
        recent = self._make_execution("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", age_seconds=10)
        mock_get_running.return_value = [stale, recent]

        mock_db = MagicMock()
        mock_app = MagicMock()
        mock_app.database.session.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_app.database.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_app.return_value = mock_app

        await backend.fail_stale_db_executions(set())

        # Only the stale execution should be failed
        mock_update_status.assert_called_once()
        assert mock_update_status.call_args[0][1] == stale.id
        mock_publish_event.assert_called_once()

    @pytest.mark.asyncio
    @patch("api.plugins.container.backend.get_current_app")
    async def test_handles_exception_gracefully(self, mock_get_app, backend):
        """Test that exceptions are caught and logged, not raised."""
        mock_get_app.side_effect = RuntimeError("App not initialized")

        # Should not raise
        await backend.fail_stale_db_executions(set())


class TestBuildEnvVars:
    """Tests for build_env_vars linked_repos and team_guidelines serialization."""

    @pytest.mark.asyncio
    @patch(
        "api.plugins.container.utils.get_platform_token", new_callable=AsyncMock, return_value=None
    )
    @patch("api.plugins.container.utils.get_current_app")
    async def test_linked_repos_serialized_to_env(self, mock_get_app, _mock_token):
        """Test that linked_repos are JSON-serialized into LINKED_REPOS env var."""
        mock_options = MagicMock()
        mock_options.code_reviewer.oauth_token = None
        mock_options.code_reviewer.anthropic_api_key = None
        mock_options.code_reviewer.anthropic_base_url = None
        mock_options.code_reviewer.review_model = None
        mock_options.code_reviewer.utility_model = None
        mock_app = MagicMock()
        mock_app.options = mock_options
        mock_get_app.return_value = mock_app

        linked = [
            LinkedRepoMessage(
                provider="github",
                provider_url="https://github.com",
                repo_path="org/shared-lib",
                branch="main",
                display_name="Shared Library",
                name="shared-lib",
            ),
        ]
        job = ReviewJobMessageFactory.build(platform="github", linked_repos=linked)

        env = await build_env_vars(job)

        linked_env = [e for e in env if e.startswith("LINKED_REPOS=")]
        assert len(linked_env) == 1
        parsed = json.loads(linked_env[0].removeprefix("LINKED_REPOS="))
        assert len(parsed) == 1
        assert parsed[0]["name"] == "shared-lib"
        assert parsed[0]["repo_path"] == "org/shared-lib"

    @pytest.mark.asyncio
    @patch(
        "api.plugins.container.utils.get_platform_token", new_callable=AsyncMock, return_value=None
    )
    @patch("api.plugins.container.utils.get_current_app")
    async def test_team_guidelines_serialized_to_env(self, mock_get_app, _mock_token):
        """Test that team_guidelines is passed as TEAM_GUIDELINES env var."""
        mock_options = MagicMock()
        mock_options.code_reviewer.oauth_token = None
        mock_options.code_reviewer.anthropic_api_key = None
        mock_options.code_reviewer.anthropic_base_url = None
        mock_options.code_reviewer.review_model = None
        mock_options.code_reviewer.utility_model = None
        mock_app = MagicMock()
        mock_app.options = mock_options
        mock_get_app.return_value = mock_app

        job = ReviewJobMessageFactory.build(
            platform="github",
            team_guidelines="Always use type hints. Prefer dataclasses over dicts.",
        )

        env = await build_env_vars(job)

        guidelines_env = [e for e in env if e.startswith("TEAM_GUIDELINES=")]
        assert len(guidelines_env) == 1
        assert (
            guidelines_env[0]
            == "TEAM_GUIDELINES=Always use type hints. Prefer dataclasses over dicts."
        )

    @pytest.mark.asyncio
    @patch(
        "api.plugins.container.utils.get_platform_token", new_callable=AsyncMock, return_value=None
    )
    @patch("api.plugins.container.utils.get_current_app")
    async def test_empty_linked_repos_not_in_env(self, mock_get_app, _mock_token):
        """Test that empty linked_repos does not add LINKED_REPOS env var."""
        mock_options = MagicMock()
        mock_options.code_reviewer.oauth_token = None
        mock_options.code_reviewer.anthropic_api_key = None
        mock_options.code_reviewer.anthropic_base_url = None
        mock_options.code_reviewer.review_model = None
        mock_options.code_reviewer.utility_model = None
        mock_app = MagicMock()
        mock_app.options = mock_options
        mock_get_app.return_value = mock_app

        job = ReviewJobMessageFactory.build(
            platform="github", linked_repos=[], team_guidelines=None
        )

        env = await build_env_vars(job)

        assert not any(e.startswith("LINKED_REPOS=") for e in env)
        assert not any(e.startswith("TEAM_GUIDELINES=") for e in env)
