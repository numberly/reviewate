"""Kubernetes backend for container execution and watching."""

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Any

import kr8s
from faststream.redis import RedisBroker
from kr8s.asyncio import Api

from api.models.executions import ExecutionStatus
from api.plugins.container.backend import ContainerBackend
from api.plugins.container.config import KubernetesConfig
from api.plugins.container.schema import (
    CONTAINER_NAME,
    ConditionStatus,
    JobConditionType,
    WatchEventType,
)
from api.plugins.container.utils import (
    LABEL_EXECUTION_ID,
    build_cli_args,
    build_container_labels,
    build_env_vars,
    determine_execution_status,
    parse_structured_logs,
)
from api.routers.queue.schemas import ReviewJobMessage

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class KubernetesBackend(ContainerBackend):
    """Kubernetes backend for container execution and watching.

    Features:
    - Event-driven Job monitoring via Kubernetes Watch API
    - Idempotent status updates via Redis
    - Single reconcile function for missed events and orphans
    - Bounded concurrency for event handling
    """

    MAX_CONCURRENT_HANDLERS = 100

    def __init__(self, config: KubernetesConfig, broker: RedisBroker, redis: Redis):
        """Initialize the Kubernetes backend.

        Args:
            config: Kubernetes configuration
            broker: FastStream Redis broker for publishing
            redis: Redis client for execution tracking
        """
        super().__init__(broker, redis)
        self._config = config
        self._api: Api | None = None
        self._watch_task: asyncio.Task | None = None
        self._running = False
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_HANDLERS)
        self._pending_tasks: set[asyncio.Task] = set()

    async def _get_api(self) -> Api:
        """Get or create kr8s API client.

        kr8s auto-discovers credentials (in-cluster ServiceAccount, kubeconfig).
        """
        if self._api is None:
            self._api = await kr8s.asyncio.api()
        return self._api

    # === Container Execution ===

    async def start_container(
        self,
        execution_id: str,
        job: ReviewJobMessage,
    ) -> str:
        """Start a Kubernetes Job for the given review job.

        Args:
            execution_id: Unique ID for this execution
            job: Job configuration message

        Returns:
            Job name (used as container_id)
        """
        api = await self._get_api()

        # DNS-safe names
        job_name = f"reviewate-{execution_id[:8]}"
        secret_name = f"{job_name}-secrets"

        # Create ephemeral Secret with env vars
        await self._create_job_secret(secret_name, job, api)

        # Build and create Job
        manifest = await self._build_job_manifest(execution_id, job_name, secret_name, job)

        # Create Job via kr8s API (constructor is synchronous)
        k8s_job = kr8s.asyncio.objects.Job(manifest, api=api)
        await k8s_job.create()

        # Set ownerReference on Secret so it auto-deletes with Job
        await self._set_secret_owner_reference(secret_name, k8s_job, api)

        # Register execution as active in Redis and publish "processing"
        await self.register_execution(execution_id, container_id=job_name)

        logger.info("Started Kubernetes Job %s for execution %s", job_name, execution_id)

        return job_name

    async def _create_job_secret(
        self,
        secret_name: str,
        job: ReviewJobMessage,
        api: Api,
    ) -> None:
        """Create an ephemeral Secret containing job environment variables.

        Args:
            secret_name: Name for the Secret
            job: Job configuration message
            api: kr8s API client
        """
        env_vars = await build_env_vars(job)

        # Convert env vars from "KEY=value" format to Secret data
        secret_data = {}
        for env_str in env_vars:
            key, _, value = env_str.partition("=")
            secret_data[key] = value

        secret_manifest = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": secret_name,
                "namespace": self._config.namespace,
            },
            "type": "Opaque",
            "stringData": secret_data,
        }

        k8s_secret = kr8s.asyncio.objects.Secret(secret_manifest, api=api)
        await k8s_secret.create()

        logger.debug("Created Secret %s for job", secret_name)

    async def _set_secret_owner_reference(
        self,
        secret_name: str,
        job_obj: Any,
        api: Api,
    ) -> None:
        """Set ownerReference on Secret so it auto-deletes with Job.

        Args:
            secret_name: Name of the Secret
            job_obj: kr8s Job object (owner)
            api: kr8s API client
        """
        secret = await kr8s.asyncio.objects.Secret.get(
            secret_name, namespace=self._config.namespace, api=api
        )

        owner_reference = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "name": job_obj.name,
            "uid": job_obj.metadata.uid,
            "blockOwnerDeletion": True,
        }

        await secret.patch({"metadata": {"ownerReferences": [owner_reference]}})

    async def _build_job_manifest(
        self,
        execution_id: str,
        job_name: str,
        secret_name: str,
        job: ReviewJobMessage,
    ) -> dict[str, Any]:
        """Build a complete Kubernetes Job manifest.

        Args:
            execution_id: Unique execution identifier
            job_name: DNS-safe job name
            secret_name: Name of the Secret containing env vars
            job: Job configuration message

        Returns:
            Kubernetes Job manifest dict
        """
        labels = build_container_labels(execution_id, job)
        cli_args = build_cli_args(job)

        # Build container spec - env vars come from Secret
        container: dict[str, Any] = {
            "name": CONTAINER_NAME,
            "image": self._config.image,
            "imagePullPolicy": self._config.image_pull_policy,
            "args": cli_args,
            "envFrom": [{"secretRef": {"name": secret_name}}],
            "resources": {
                "limits": {
                    "memory": self._config.memory_limit,
                    "cpu": self._config.cpu_limit,
                },
                "requests": {
                    "memory": self._config.memory_request,
                    "cpu": self._config.cpu_request,
                },
            },
            "securityContext": {
                "readOnlyRootFilesystem": True,
                "allowPrivilegeEscalation": False,
            },
            "volumeMounts": [
                {"name": "tmp", "mountPath": "/tmp"},
            ],
        }

        # Build pod spec
        pod_spec: dict[str, Any] = {
            "serviceAccountName": self._config.service_account,
            "restartPolicy": "Never",
            "securityContext": {
                "runAsNonRoot": True,
                "runAsUser": self._config.run_as_user,
                "runAsGroup": self._config.run_as_group,
            },
            "containers": [container],
            "volumes": [
                {"name": "tmp", "emptyDir": {"sizeLimit": self._config.tmp_size_limit}},
            ],
        }

        # Optional scheduling fields
        if self._config.image_pull_secrets:
            pod_spec["imagePullSecrets"] = [{"name": s} for s in self._config.image_pull_secrets]
        if self._config.node_selector:
            pod_spec["nodeSelector"] = self._config.node_selector
        if self._config.tolerations:
            pod_spec["tolerations"] = self._config.tolerations

        # Build template metadata
        template_metadata: dict[str, Any] = {"labels": labels}
        if self._config.annotations:
            template_metadata["annotations"] = self._config.annotations

        manifest: dict[str, Any] = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": job_name,
                "namespace": self._config.namespace,
                "labels": labels,
            },
            "spec": {
                "backoffLimit": 0,
                "activeDeadlineSeconds": self._config.timeout,
                "template": {
                    "metadata": template_metadata,
                    "spec": pod_spec,
                },
            },
        }

        return manifest

    async def stop_container(self, container_id: str) -> None:
        """Stop a running Kubernetes Job.

        Args:
            container_id: Job name
        """
        try:
            api = await self._get_api()
            job_obj = await kr8s.asyncio.objects.Job.get(
                container_id, namespace=self._config.namespace, api=api
            )
            await job_obj.delete(propagation_policy="Background")
            logger.debug("Stopped Kubernetes Job %s", container_id)
        except Exception as e:
            logger.warning("Failed to stop Kubernetes Job %s: %s", container_id, e)

    # === Job Watching ===

    async def start_watching(self) -> None:
        """Start watching for Kubernetes Job events."""
        self._running = True
        self._watch_task = asyncio.create_task(self._watch_loop())

    async def stop_watching(self) -> None:
        """Stop watching for Kubernetes Job events."""
        self._running = False
        if self._watch_task:
            self._watch_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._watch_task
            self._watch_task = None
        self._api = None

    async def _watch_loop(self) -> None:
        """Main watch loop for Kubernetes Job events."""
        while self._running:
            try:
                api = await self._get_api()
                label_selector = LABEL_EXECUTION_ID
                async for event_type, job_obj in kr8s.asyncio.watch(
                    "jobs",
                    namespace=self._config.namespace,
                    label_selector=label_selector,
                    api=api,
                ):
                    if not self._running:
                        break
                    task = asyncio.create_task(self._handle_event_with_limit(event_type, job_obj))
                    self._pending_tasks.add(task)
                    task.add_done_callback(self._pending_tasks.discard)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in Kubernetes Job watch loop: %s", e)
                if self._running:
                    await asyncio.sleep(5)

        if self._pending_tasks:
            logger.info("Waiting for %d pending event handlers...", len(self._pending_tasks))
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._pending_tasks, return_exceptions=True),
                    timeout=120.0,
                )
            except TimeoutError:
                logger.warning(
                    "Timed out waiting for %d pending handlers, some events may not have been processed",
                    len(self._pending_tasks),
                )

    async def _handle_event_with_limit(self, event_type: str, job_obj: Any) -> None:
        """Handle Job event with concurrency limiting."""
        async with self._semaphore:
            await self._handle_job_event(event_type, job_obj)

    def _get_job_terminal_state(self, job_obj: Any) -> int | None:
        """Check if Job is in terminal state.

        Returns:
            Exit code (0=success, 1=failed) or None if still running.
        """
        conditions = job_obj.status.get("conditions", []) if job_obj.status else []
        for condition in conditions:
            if condition.get("status") != ConditionStatus.TRUE:
                continue
            if condition.get("type") == JobConditionType.COMPLETE:
                return 0
            if condition.get("type") == JobConditionType.FAILED:
                return 1
        return None

    async def _handle_job_event(self, event_type: str, job_obj: Any) -> None:
        """Handle a Kubernetes Job event.

        Args:
            event_type: Watch event type (ADDED, MODIFIED, DELETED)
            job_obj: kr8s Job object
        """
        labels = job_obj.labels or {}
        execution_id = labels.get(LABEL_EXECUTION_ID)
        if not execution_id:
            return

        job_name = job_obj.name

        logger.debug(
            "Job event: %s for execution %s",
            event_type,
            execution_id,
            extra={
                "event_type": event_type,
                "execution_id": execution_id,
                "job_name": job_name,
            },
        )

        match event_type:
            case WatchEventType.DELETED:
                await self._handle_job_deleted(execution_id, job_name)
            case WatchEventType.ADDED | WatchEventType.MODIFIED:
                await self._handle_job_update(execution_id, job_name, job_obj)

    async def _handle_job_deleted(self, execution_id: str, job_name: str) -> None:
        """Handle Job deletion event.

        Marks the execution as failed if it was still being tracked.
        Uses idempotent publishing to avoid overwriting completed status
        when cleanup deletes a successfully finished Job.

        Args:
            execution_id: Execution identifier
            job_name: Kubernetes Job name
        """
        await self.publish_status_idempotent(
            execution_id=execution_id,
            status=ExecutionStatus.FAILED,
            container_id=job_name,
            error_type="container_error",
            error_message="Job was deleted before completion",
        )

    async def _handle_job_update(
        self,
        execution_id: str,
        job_name: str,
        job_obj: Any,
    ) -> None:
        """Handle Job addition or modification event.

        Checks for terminal states first, then publishes processing status
        if pods are active.

        Args:
            execution_id: Execution identifier
            job_name: Kubernetes Job name
            job_obj: kr8s Job object
        """
        # Check for terminal states (Complete/Failed conditions)
        exit_code = self._get_job_terminal_state(job_obj)
        if exit_code is not None:
            await self._handle_job_exit(
                execution_id=execution_id,
                job_name=job_name,
                exit_code=exit_code,
            )

    async def _handle_job_exit(
        self,
        execution_id: str,
        job_name: str,
        exit_code: int,
    ) -> None:
        """Handle Job exit event with idempotency.

        Uses publish_status_idempotent to prevent duplicate processing.
        """
        # Parse result from pod logs
        result, error_info = await self._get_pod_logs_result(job_name)

        # Determine final status
        status, final_error_info = determine_execution_status(exit_code, result, error_info)

        # Publish with idempotency check (atomic remove from active set)
        published = await self.publish_status_idempotent(
            execution_id=execution_id,
            status=status,
            container_id=job_name,
            exit_code=exit_code,
            error_type=final_error_info[0] if final_error_info else None,
            error_message=final_error_info[1] if final_error_info else None,
            result=result,
        )

        # Only cleanup if we actually processed this exit
        if published:
            await self._cleanup_job(job_name)

    async def _get_pod_logs_result(
        self,
        job_name: str,
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Get and parse pod logs for result/error.

        Args:
            job_name: Kubernetes Job name

        Returns:
            Tuple of (result dict or None, error message or None)
        """
        try:
            api = await self._get_api()
            # List pods belonging to this Job
            pods = [
                pod
                async for pod in kr8s.asyncio.objects.Pod.list(
                    namespace=self._config.namespace,
                    label_selector=f"job-name={job_name}",
                    api=api,
                )
            ]

            if not pods:
                logger.warning("No pods found for Job %s", job_name)
                return None, None

            # Get logs from first pod (logs() is an async generator)
            pod = pods[0]
            log_lines: list[str] = []
            async for line in pod.logs(container=CONTAINER_NAME):
                log_lines.append(line)
            log_text = "\n".join(log_lines)
            return parse_structured_logs(log_text)

        except Exception as e:
            logger.error("Failed to parse pod logs for Job %s: %s", job_name, e)
            return None, None

    async def _cleanup_job(self, job_name: str) -> None:
        """Remove a Job after processing.

        Args:
            job_name: Kubernetes Job name
        """
        if not self._config.cleanup_jobs:
            logger.debug("Skipping cleanup for Job %s (cleanup disabled)", job_name)
            return

        try:
            api = await self._get_api()
            job_obj = await kr8s.asyncio.objects.Job.get(
                job_name, namespace=self._config.namespace, api=api
            )
            await job_obj.delete(propagation_policy="Background")
            logger.debug("Cleaned up Job %s", job_name)
        except Exception as e:
            logger.warning("Failed to cleanup Job %s: %s", job_name, e)

    # === Reconciliation ===

    async def reconcile(self) -> None:
        """Reconcile Job state with Redis tracking.

        Single-pass reconciliation that handles:
        1. Completed/Failed Jobs whose events were missed (force-publishes,
           bypassing idempotency to recover from lost pub/sub messages)
        2. Orphaned executions (in Redis but Job gone)

        This method is protected by a distributed lock so only one instance
        runs reconciliation at a time.
        """
        try:
            api = await self._get_api()

            # Get Jobs and active executions
            active_executions = await self.get_active_executions()

            # Build mapping of execution_id -> Job
            job_map: dict[str, Any] = {}
            async for job_obj in kr8s.asyncio.objects.Job.list(
                namespace=self._config.namespace,
                label_selector=LABEL_EXECUTION_ID,
                api=api,
            ):
                exec_id = (job_obj.labels or {}).get(LABEL_EXECUTION_ID)
                if exec_id:
                    job_map[exec_id] = job_obj

            # Process completed/failed Jobs — force-publish status regardless
            # of Redis active set. After a backend restart, the execution may
            # have been removed from Redis by the previous instance but the
            # pub/sub message was lost. The idempotent path would skip these
            # forever, so reconciliation bypasses it.
            for exec_id, job_obj in job_map.items():
                exit_code = self._get_job_terminal_state(job_obj)
                if exit_code is not None:
                    status_label = "completed" if exit_code == 0 else "failed"
                    logger.info(
                        "Reconciling %s Job %s for execution %s",
                        status_label,
                        job_obj.name,
                        exec_id,
                    )
                    await self._reconcile_job_exit(
                        execution_id=exec_id,
                        job_name=job_obj.name,
                        exit_code=exit_code,
                    )

            # Handle orphaned executions (in Redis but no Job)
            job_exec_ids = set(job_map.keys())
            orphaned = active_executions - job_exec_ids

            for exec_id in orphaned:
                logger.warning("Found orphaned execution %s - Job not found", exec_id)
                await self.unregister_execution(exec_id)
                await self.publish_status(
                    execution_id=exec_id,
                    status=ExecutionStatus.FAILED,
                    error_type="container_error",
                    error_message="Job not found - may have been removed unexpectedly",
                )

            # 3. Fail stale DB executions whose Job no longer exists
            running_job_ids = {
                exec_id
                for exec_id, job_obj in job_map.items()
                if self._get_job_terminal_state(job_obj) is None
            }
            await self.fail_stale_db_executions(running_job_ids)

        except Exception as e:
            logger.error("Error during reconciliation: %s", e)

    async def _reconcile_job_exit(
        self,
        execution_id: str,
        job_name: str,
        exit_code: int,
    ) -> None:
        """Handle Job exit during reconciliation.

        Unlike _handle_job_exit, this bypasses the idempotency check and
        always publishes status. Safe because reconciliation is protected
        by a distributed lock.
        """
        # Parse result from pod logs
        result, error_info = await self._get_pod_logs_result(job_name)

        # Determine final status
        status, final_error_info = determine_execution_status(exit_code, result, error_info)

        # Remove from active set (may already be gone — that's fine)
        await self.unregister_execution(execution_id)

        # Always publish — this is the safety net for lost pub/sub messages
        await self.publish_status(
            execution_id=execution_id,
            status=status,
            container_id=job_name,
            exit_code=exit_code,
            error_type=final_error_info[0] if final_error_info else None,
            error_message=final_error_info[1] if final_error_info else None,
            result=result,
        )

        # Cleanup the Job
        await self._cleanup_job(job_name)
