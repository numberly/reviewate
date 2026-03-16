"""Tests for Kubernetes backend container execution and watching."""

import json
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.plugins.container.config import KubernetesConfig
from api.plugins.container.kubernetes import KubernetesBackend
from tests.utils.factories import ReviewJobMessageFactory


def _mock_async_gen(items):
    """Create a mock that behaves like an async generator returning items."""

    async def _gen(*args, **kwargs):
        for item in items:
            yield item

    return _gen


async def _async_iter_from_str(text):
    """Create an async iterator that yields the entire text as one chunk."""
    yield text


@pytest.fixture
def kube_config():
    """Create Kubernetes config fixture."""
    return KubernetesConfig(
        namespace="reviewate",
        image="reviewate/code-reviewer:latest",
        service_account="reviewate",
        timeout=600,
        memory_limit="2Gi",
        memory_request="512Mi",
        cpu_limit="2",
        cpu_request="500m",
        image_pull_policy="IfNotPresent",
    )


@pytest.fixture
def backend(kube_config, mock_broker, mock_redis):
    """Create KubernetesBackend instance with mocked dependencies."""
    return KubernetesBackend(kube_config, mock_broker, mock_redis)


# === Container Lifecycle ===


@pytest.mark.asyncio
@patch("api.plugins.container.utils.get_current_app")
@patch("api.plugins.container.kubernetes.kr8s")
async def test_start_container_success(mock_kr8s, mock_get_app, backend, mock_app):
    """Test successful Job creation."""
    mock_get_app.return_value = mock_app
    job = ReviewJobMessageFactory.build(
        platform="github",
        organization="test-org",
        repository="test-repo",
    )

    # Mock kr8s Job object (constructor is sync)
    mock_job_obj = MagicMock()
    mock_job_obj.name = "reviewate-exec-123"
    mock_job_obj.metadata.uid = "fake-uid"
    mock_job_obj.create = AsyncMock()

    mock_kr8s.asyncio.objects.Job = MagicMock(return_value=mock_job_obj)

    # Mock Secret creation
    mock_secret_obj = MagicMock()
    mock_secret_obj.create = AsyncMock()
    mock_kr8s.asyncio.objects.Secret = MagicMock(return_value=mock_secret_obj)
    mock_secret_get = MagicMock()
    mock_secret_get.patch = AsyncMock()
    mock_kr8s.asyncio.objects.Secret.get = AsyncMock(return_value=mock_secret_get)

    # Mock API
    mock_api = MagicMock()
    backend._get_api = AsyncMock(return_value=mock_api)

    job_name = await backend.start_container("exec-12345678", job)

    assert job_name == "reviewate-exec-123"
    mock_job_obj.create.assert_called_once()


@pytest.mark.asyncio
@patch("api.plugins.container.utils.db_get_organization_by_id")
@patch("api.plugins.container.utils.get_current_app")
@patch("api.plugins.container.kubernetes.kr8s")
async def test_start_container_sets_cli_args_and_env_vars(
    mock_kr8s, mock_get_app, mock_get_org, backend, mock_app
):
    """Test that Job manifest contains correct CLI args and env vars."""
    mock_org = MagicMock()
    mock_org.installation_id = "github-installation-123"
    mock_get_org.return_value = mock_org

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
        pull_request_number=42,
        workflow="review",
    )

    # Capture manifests passed to Job and Secret constructors
    captured_job_manifest = {}
    captured_secret_manifest = {}

    def capture_job(manifest, api=None):
        captured_job_manifest.update(manifest)
        mock_obj = MagicMock()
        mock_obj.name = manifest["metadata"]["name"]
        mock_obj.metadata.uid = "fake-uid"
        mock_obj.create = AsyncMock()
        return mock_obj

    def capture_secret(manifest, api=None):
        captured_secret_manifest.update(manifest)
        mock_obj = MagicMock()
        mock_obj.create = AsyncMock()
        return mock_obj

    mock_kr8s.asyncio.objects.Job = MagicMock(side_effect=capture_job)
    mock_kr8s.asyncio.objects.Secret = MagicMock(side_effect=capture_secret)
    mock_secret_get = MagicMock()
    mock_secret_get.patch = AsyncMock()
    mock_kr8s.asyncio.objects.Secret.get = AsyncMock(return_value=mock_secret_get)

    mock_api = MagicMock()
    backend._get_api = AsyncMock(return_value=mock_api)

    await backend.start_container("exec-12345678", job)

    # Check CLI args (positional format)
    container_spec = captured_job_manifest["spec"]["template"]["spec"]["containers"][0]
    args = container_spec["args"]
    assert args[0] == "review"
    assert "test-org/test-repo" in args
    assert "-p" in args
    assert "42" in args
    assert "--platform" in args
    assert "github" in args

    # Check env vars are in the Secret (not directly in container spec)
    secret_data = captured_secret_manifest["stringData"]
    assert secret_data["ANTHROPIC_API_KEY"] == "test-anthropic-key"
    assert secret_data["GITHUB_TOKEN"] == "github-token-123"

    # Check container references the Secret via envFrom
    assert container_spec["envFrom"] == [{"secretRef": {"name": "reviewate-exec-123-secrets"}}]


@pytest.mark.asyncio
@patch("api.plugins.container.kubernetes.kr8s")
async def test_stop_container_success(mock_kr8s, backend):
    """Test successful Job stop."""
    mock_job_obj = MagicMock()
    mock_job_obj.delete = AsyncMock()

    mock_kr8s.asyncio.objects.Job.get = AsyncMock(return_value=mock_job_obj)

    mock_api = MagicMock()
    backend._get_api = AsyncMock(return_value=mock_api)

    await backend.stop_container("reviewate-exec1234")

    mock_kr8s.asyncio.objects.Job.get.assert_called_once_with(
        "reviewate-exec1234", namespace="reviewate", api=mock_api
    )
    mock_job_obj.delete.assert_called_once_with(propagation_policy="Background")


@pytest.mark.asyncio
@patch("api.plugins.container.kubernetes.kr8s")
async def test_stop_container_handles_error(mock_kr8s, backend):
    """Test stop_container handles errors gracefully."""
    mock_kr8s.asyncio.objects.Job.get = AsyncMock(side_effect=Exception("Job not found"))

    mock_api = MagicMock()
    backend._get_api = AsyncMock(return_value=mock_api)

    # Should not raise
    await backend.stop_container("nonexistent")


# === Job Manifest ===


@pytest.mark.asyncio
@patch("api.plugins.container.utils.get_current_app")
async def test_build_job_manifest_labels(mock_get_app, backend, mock_app):
    """Test that Job manifest has correct labels."""
    mock_get_app.return_value = mock_app
    job = ReviewJobMessageFactory.build(
        platform="github",
        organization="test-org",
        repository="test-repo",
    )

    manifest = await backend._build_job_manifest(
        "exec-12345678", "reviewate-exec-123", "reviewate-exec-123-secrets", job
    )

    labels = manifest["metadata"]["labels"]
    assert labels["reviewate.execution_id"] == "exec-12345678"
    assert "reviewate.organization_id" in labels
    assert "reviewate.repository_id" in labels

    # Template labels should match
    template_labels = manifest["spec"]["template"]["metadata"]["labels"]
    assert template_labels == labels


@pytest.mark.asyncio
@patch("api.plugins.container.utils.get_current_app")
async def test_build_job_manifest_resources(mock_get_app, backend, mock_app):
    """Test that Job manifest has correct resource limits and requests."""
    mock_get_app.return_value = mock_app
    job = ReviewJobMessageFactory.build(platform="github")

    manifest = await backend._build_job_manifest(
        "exec-12345678", "reviewate-exec-123", "reviewate-exec-123-secrets", job
    )

    container_spec = manifest["spec"]["template"]["spec"]["containers"][0]
    resources = container_spec["resources"]

    assert resources["limits"]["memory"] == "2Gi"
    assert resources["limits"]["cpu"] == "2"
    assert resources["requests"]["memory"] == "512Mi"
    assert resources["requests"]["cpu"] == "500m"


@pytest.mark.asyncio
@patch("api.plugins.container.utils.get_current_app")
async def test_build_job_manifest_security_context(mock_get_app, backend, mock_app):
    """Test that Job manifest has correct security context."""
    mock_get_app.return_value = mock_app
    job = ReviewJobMessageFactory.build(platform="github")

    manifest = await backend._build_job_manifest(
        "exec-12345678", "reviewate-exec-123", "reviewate-exec-123-secrets", job
    )

    pod_spec = manifest["spec"]["template"]["spec"]
    pod_security = pod_spec["securityContext"]
    assert pod_security["runAsNonRoot"] is True
    assert pod_security["runAsUser"] == 1000
    assert pod_security["runAsGroup"] == 1000

    container_security = pod_spec["containers"][0]["securityContext"]
    assert container_security["readOnlyRootFilesystem"] is True
    assert container_security["allowPrivilegeEscalation"] is False


@pytest.mark.asyncio
@patch("api.plugins.container.utils.get_current_app")
async def test_build_job_manifest_image_pull_secrets(mock_get_app, backend, mock_app, kube_config):
    """Test that image pull secrets are included when configured."""
    mock_get_app.return_value = mock_app
    kube_config.image_pull_secrets = ["my-registry-secret", "other-secret"]
    backend._config = kube_config
    job = ReviewJobMessageFactory.build(platform="github")

    manifest = await backend._build_job_manifest(
        "exec-12345678", "reviewate-exec-123", "reviewate-exec-123-secrets", job
    )

    pod_spec = manifest["spec"]["template"]["spec"]
    assert pod_spec["imagePullSecrets"] == [
        {"name": "my-registry-secret"},
        {"name": "other-secret"},
    ]


@pytest.mark.asyncio
@patch("api.plugins.container.utils.get_current_app")
async def test_build_job_manifest_no_image_pull_secrets_by_default(mock_get_app, backend, mock_app):
    """Test that imagePullSecrets is omitted when not configured."""
    mock_get_app.return_value = mock_app
    job = ReviewJobMessageFactory.build(platform="github")

    manifest = await backend._build_job_manifest(
        "exec-12345678", "reviewate-exec-123", "reviewate-exec-123-secrets", job
    )

    pod_spec = manifest["spec"]["template"]["spec"]
    assert "imagePullSecrets" not in pod_spec


@pytest.mark.asyncio
@patch("api.plugins.container.utils.get_current_app")
async def test_build_job_manifest_node_selector(mock_get_app, backend, mock_app, kube_config):
    """Test that node selector is included when configured."""
    mock_get_app.return_value = mock_app
    kube_config.node_selector = {"workload": "review"}
    backend._config = kube_config
    job = ReviewJobMessageFactory.build(platform="github")

    manifest = await backend._build_job_manifest(
        "exec-12345678", "reviewate-exec-123", "reviewate-exec-123-secrets", job
    )

    pod_spec = manifest["spec"]["template"]["spec"]
    assert pod_spec["nodeSelector"] == {"workload": "review"}


@pytest.mark.asyncio
@patch("api.plugins.container.utils.get_current_app")
async def test_build_job_manifest_tolerations(mock_get_app, backend, mock_app, kube_config):
    """Test that tolerations are included when configured."""
    mock_get_app.return_value = mock_app
    kube_config.tolerations = [
        {"key": "dedicated", "operator": "Equal", "value": "review", "effect": "NoSchedule"}
    ]
    backend._config = kube_config
    job = ReviewJobMessageFactory.build(platform="github")

    manifest = await backend._build_job_manifest(
        "exec-12345678", "reviewate-exec-123", "reviewate-exec-123-secrets", job
    )

    pod_spec = manifest["spec"]["template"]["spec"]
    assert pod_spec["tolerations"] == [
        {"key": "dedicated", "operator": "Equal", "value": "review", "effect": "NoSchedule"}
    ]


@pytest.mark.asyncio
@patch("api.plugins.container.utils.get_current_app")
async def test_build_job_manifest_annotations(mock_get_app, backend, mock_app, kube_config):
    """Test that annotations are included when configured."""
    mock_get_app.return_value = mock_app
    kube_config.annotations = {"sidecar.istio.io/inject": "false"}
    backend._config = kube_config
    job = ReviewJobMessageFactory.build(platform="github")

    manifest = await backend._build_job_manifest(
        "exec-12345678", "reviewate-exec-123", "reviewate-exec-123-secrets", job
    )

    template_metadata = manifest["spec"]["template"]["metadata"]
    assert template_metadata["annotations"] == {"sidecar.istio.io/inject": "false"}


@pytest.mark.asyncio
@patch("api.plugins.container.utils.get_current_app")
async def test_build_job_manifest_core_structure(mock_get_app, backend, mock_app):
    """Test Job manifest core structure (apiVersion, kind, backoff, timeout)."""
    mock_get_app.return_value = mock_app
    job = ReviewJobMessageFactory.build(platform="github")

    manifest = await backend._build_job_manifest(
        "exec-12345678", "reviewate-exec-123", "reviewate-exec-123-secrets", job
    )

    assert manifest["apiVersion"] == "batch/v1"
    assert manifest["kind"] == "Job"
    assert manifest["metadata"]["name"] == "reviewate-exec-123"
    assert manifest["metadata"]["namespace"] == "reviewate"
    assert manifest["spec"]["backoffLimit"] == 0
    assert manifest["spec"]["activeDeadlineSeconds"] == 600

    pod_spec = manifest["spec"]["template"]["spec"]
    assert pod_spec["restartPolicy"] == "Never"
    assert pod_spec["serviceAccountName"] == "reviewate"

    container_spec = pod_spec["containers"][0]
    assert container_spec["name"] == "reviewer"
    assert container_spec["image"] == "reviewate/code-reviewer:latest"
    assert container_spec["imagePullPolicy"] == "IfNotPresent"


# === Event Handling ===


@pytest.mark.asyncio
async def test_handle_job_event_completed(backend, mock_broker):
    """Test handling Job completed event."""
    mock_job_obj = MagicMock()
    mock_job_obj.labels = {"reviewate.execution_id": "exec-456"}
    mock_job_obj.name = "reviewate-exec4567"
    mock_job_obj.status = {
        "conditions": [{"type": "Complete", "status": "True"}],
    }

    backend._handle_job_exit = AsyncMock()

    await backend._handle_job_event("MODIFIED", mock_job_obj)

    backend._handle_job_exit.assert_called_once_with(
        execution_id="exec-456",
        job_name="reviewate-exec4567",
        exit_code=0,
    )


@pytest.mark.asyncio
async def test_handle_job_event_failed(backend, mock_broker):
    """Test handling Job failed event."""
    mock_job_obj = MagicMock()
    mock_job_obj.labels = {"reviewate.execution_id": "exec-456"}
    mock_job_obj.name = "reviewate-exec4567"
    mock_job_obj.status = {
        "conditions": [{"type": "Failed", "status": "True"}],
    }

    backend._handle_job_exit = AsyncMock()

    await backend._handle_job_event("MODIFIED", mock_job_obj)

    backend._handle_job_exit.assert_called_once_with(
        execution_id="exec-456",
        job_name="reviewate-exec4567",
        exit_code=1,
    )


@pytest.mark.asyncio
async def test_handle_job_event_processing(backend, mock_broker):
    """Test that ADDED event with active pods is a no-op (processing published at registration)."""
    mock_job_obj = MagicMock()
    mock_job_obj.labels = {"reviewate.execution_id": "exec-456"}
    mock_job_obj.name = "reviewate-exec4567"
    mock_job_obj.status = {"active": 1}

    await backend._handle_job_event("ADDED", mock_job_obj)

    # Processing is no longer published from the watcher — it's gated by SADD in register_execution
    mock_broker.publish.assert_not_called()


@pytest.mark.asyncio
async def test_handle_job_event_ignores_non_reviewate(backend, mock_broker):
    """Test that Jobs without reviewate labels are ignored."""
    mock_job_obj = MagicMock()
    mock_job_obj.labels = {}
    mock_job_obj.status = {}

    await backend._handle_job_event("MODIFIED", mock_job_obj)

    mock_broker.publish.assert_not_called()


# === Log Parsing ===


@pytest.mark.asyncio
@patch("api.plugins.container.kubernetes.kr8s")
async def test_get_pod_logs_result_success(mock_kr8s, backend):
    """Test parsing successful result from pod logs."""
    result_data = {"status": "success", "comments": [{"line": 10, "message": "Good code!"}]}
    log_output = f"Starting review...\n[REVIEWATE:RESULT] {json.dumps(result_data)}\nDone."

    mock_pod = MagicMock()
    # pod.logs() returns an async generator
    mock_pod.logs = MagicMock(return_value=_async_iter_from_str(log_output))

    # Pod.list() returns an async generator
    mock_kr8s.asyncio.objects.Pod.list = _mock_async_gen([mock_pod])

    mock_api = MagicMock()
    backend._get_api = AsyncMock(return_value=mock_api)

    result, error = await backend._get_pod_logs_result("reviewate-exec1234")

    assert result == result_data
    assert error is None


@pytest.mark.asyncio
@patch("api.plugins.container.kubernetes.kr8s")
async def test_get_pod_logs_result_with_error(mock_kr8s, backend):
    """Test parsing error from pod logs."""
    error_data = {"type": "timeout", "message": "Review took too long"}
    log_output = f"Starting review...\n[REVIEWATE:ERROR] {json.dumps(error_data)}\nFailed."

    mock_pod = MagicMock()
    mock_pod.logs = MagicMock(return_value=_async_iter_from_str(log_output))

    mock_kr8s.asyncio.objects.Pod.list = _mock_async_gen([mock_pod])

    mock_api = MagicMock()
    backend._get_api = AsyncMock(return_value=mock_api)

    result, error_info = await backend._get_pod_logs_result("reviewate-exec1234")

    assert result is None
    assert error_info == ("timeout", "Review took too long")


@pytest.mark.asyncio
@patch("api.plugins.container.kubernetes.kr8s")
async def test_get_pod_logs_result_no_pods(mock_kr8s, backend):
    """Test handling when no pods found for Job."""
    mock_kr8s.asyncio.objects.Pod.list = _mock_async_gen([])

    mock_api = MagicMock()
    backend._get_api = AsyncMock(return_value=mock_api)

    result, error = await backend._get_pod_logs_result("reviewate-exec1234")

    assert result is None
    assert error is None


# === Reconciliation ===


@pytest.mark.asyncio
@patch("api.plugins.container.kubernetes.kr8s")
async def test_reconcile_processes_completed_jobs(mock_kr8s, backend, mock_broker):
    """Test reconciliation processes completed Jobs via force-publish path."""
    mock_job_obj = MagicMock()
    mock_job_obj.labels = {"reviewate.execution_id": "exec-456"}
    mock_job_obj.name = "reviewate-exec4567"
    mock_job_obj.status = {
        "conditions": [{"type": "Complete", "status": "True"}],
    }

    # Job.list() returns an async generator
    mock_kr8s.asyncio.objects.Job.list = _mock_async_gen([mock_job_obj])

    mock_api = MagicMock()
    backend._get_api = AsyncMock(return_value=mock_api)
    backend._reconcile_job_exit = AsyncMock()
    backend.fail_stale_db_executions = AsyncMock()

    await backend.reconcile()

    backend._reconcile_job_exit.assert_called_once_with(
        execution_id="exec-456",
        job_name="reviewate-exec4567",
        exit_code=0,
    )
    # Completed job is terminal — not in running set
    backend.fail_stale_db_executions.assert_called_once_with(set())


@pytest.mark.asyncio
@patch("api.plugins.container.kubernetes.kr8s")
async def test_reconcile_handles_orphaned_executions(mock_kr8s, backend, mock_redis, mock_broker):
    """Test reconciliation handles orphaned executions."""
    # No Jobs exist
    mock_kr8s.asyncio.objects.Job.list = _mock_async_gen([])

    # But Redis thinks exec-orphan is active
    mock_redis.smembers = AsyncMock(return_value={"exec-orphan"})

    mock_api = MagicMock()
    backend._get_api = AsyncMock(return_value=mock_api)
    backend.fail_stale_db_executions = AsyncMock()

    await backend.reconcile()

    # Should unregister the orphaned execution from Redis
    mock_redis.srem.assert_called_with("reviewate:executions:active", "exec-orphan")

    # Should publish failed status directly (not via idempotent path)
    mock_broker.publish.assert_called_once()
    message = mock_broker.publish.call_args.args[0]
    assert message["execution_id"] == "exec-orphan"
    assert message["status"] == "failed"


@pytest.mark.asyncio
@patch("api.plugins.container.kubernetes.kr8s")
async def test_reconcile_job_exit_bypasses_idempotency(mock_kr8s, backend, mock_broker, mock_redis):
    """Test _reconcile_job_exit publishes status even when execution is NOT in Redis active set.

    This is the dead-zone scenario: execution was removed from Redis by a previous
    instance, but the pub/sub message was lost. The reconciliation must still publish.
    """
    # Simulate the dead zone: srem returns 0 (execution NOT in active set)
    mock_redis.srem = AsyncMock(return_value=0)

    # Mock pod logs with a successful result
    result_data = {"status": "success", "comments": []}
    log_output = f"[REVIEWATE:RESULT] {json.dumps(result_data)}"
    mock_pod = MagicMock()
    mock_pod.logs = MagicMock(return_value=_async_iter_from_str(log_output))
    mock_kr8s.asyncio.objects.Pod.list = _mock_async_gen([mock_pod])

    # Mock cleanup
    mock_job_obj = MagicMock()
    mock_job_obj.delete = AsyncMock()
    mock_kr8s.asyncio.objects.Job.get = AsyncMock(return_value=mock_job_obj)

    mock_api = MagicMock()
    backend._get_api = AsyncMock(return_value=mock_api)

    await backend._reconcile_job_exit(
        execution_id="exec-dead-zone",
        job_name="reviewate-exec-dead",
        exit_code=0,
    )

    # Must publish status despite execution not being in active set
    mock_broker.publish.assert_called_once()
    message = mock_broker.publish.call_args.args[0]
    assert message["execution_id"] == "exec-dead-zone"
    assert message["status"] == "completed"
    assert message["result"] == result_data

    # Must still clean up the Job
    mock_job_obj.delete.assert_called_once()


# === Watcher Lifecycle ===


@pytest.mark.asyncio
async def test_start_watching(backend):
    """Test start_watching creates task."""
    await backend.start_watching()

    assert backend._running is True
    assert backend._watch_task is not None

    # Cleanup
    backend._running = False
    backend._watch_task.cancel()


@pytest.mark.asyncio
async def test_stop_watching(backend):
    """Test stop_watching cleans up resources."""
    backend._api = MagicMock()
    backend._running = True
    backend._watch_task = None

    await backend.stop_watching()

    assert backend._running is False
    assert backend._api is None


# === Cleanup ===


@pytest.mark.asyncio
@patch("api.plugins.container.kubernetes.kr8s")
async def test_cleanup_job_success(mock_kr8s, backend):
    """Test successful Job cleanup."""
    mock_job_obj = MagicMock()
    mock_job_obj.delete = AsyncMock()

    mock_kr8s.asyncio.objects.Job.get = AsyncMock(return_value=mock_job_obj)

    mock_api = MagicMock()
    backend._get_api = AsyncMock(return_value=mock_api)

    await backend._cleanup_job("reviewate-exec1234")

    mock_job_obj.delete.assert_called_once_with(propagation_policy="Background")


@pytest.mark.asyncio
async def test_cleanup_job_disabled(backend, kube_config):
    """Test cleanup skipped when disabled."""
    kube_config.cleanup_jobs = False
    backend._config = kube_config

    # Should not raise or attempt to delete
    await backend._cleanup_job("reviewate-exec1234")


@pytest.mark.asyncio
@patch("api.plugins.container.kubernetes.kr8s")
async def test_cleanup_job_handles_error(mock_kr8s, backend):
    """Test cleanup handles errors gracefully."""
    mock_kr8s.asyncio.objects.Job.get = AsyncMock(side_effect=Exception("Job gone"))

    mock_api = MagicMock()
    backend._get_api = AsyncMock(return_value=mock_api)

    # Should not raise
    await backend._cleanup_job("nonexistent")
