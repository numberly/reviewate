"""Docker backend for container execution and watching."""

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Any

from aiodocker import Docker
from aiodocker.containers import DockerContainer
from faststream.redis import RedisBroker

from api.plugins.container.backend import ContainerBackend
from api.plugins.container.config import DockerConfig
from api.plugins.container.schema import ContainerStatus, DockerEventAction
from api.plugins.container.utils import (
    LABEL_EXECUTION_ID,
    build_cli_args,
    build_container_labels,
    build_env_vars,
    determine_execution_status,
    parse_memory_limit,
    parse_structured_logs,
)
from api.routers.queue.schemas import ReviewJobMessage

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class DockerBackend(ContainerBackend):
    """Docker backend for container execution and watching.

    Features:
    - Event-driven container monitoring
    - Idempotent status updates via Redis
    - Single reconcile function for missed events and orphans
    - Bounded concurrency for event handling
    """

    MAX_CONCURRENT_HANDLERS = 100

    def __init__(self, config: DockerConfig, broker: RedisBroker, redis: Redis):
        """Initialize the Docker backend.

        Args:
            config: Docker configuration
            broker: FastStream Redis broker for publishing
            redis: Redis client for execution tracking
        """
        super().__init__(broker, redis)
        self._config = config
        self._docker: Docker | None = None
        self._watch_task: asyncio.Task | None = None
        self._running = False
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_HANDLERS)
        self._pending_tasks: set[asyncio.Task] = set()

    async def _get_docker(self) -> Docker:
        """Get or create Docker client."""
        if self._docker is None:
            url = self._config.socket
            # Support both unix sockets (path) and TCP URLs
            if url.startswith("/"):
                url = f"unix://{url}"
            self._docker = Docker(url=url)
        return self._docker

    # === Container Execution ===

    async def start_container(
        self,
        execution_id: str,
        job: ReviewJobMessage,
    ) -> str:
        """Start a container for the given job.

        Args:
            execution_id: Unique ID for this execution
            job: Job configuration message

        Returns:
            Container ID
        """
        docker = await self._get_docker()
        container_config = await self._build_container_config(execution_id, job)

        # Pull image if not available locally
        image = self._config.image
        try:
            await docker.images.inspect(image)
        except Exception:
            logger.info(f"Pulling image {image}...")
            await docker.images.pull(image)

        # Create and start container
        container = await docker.containers.create(config=container_config)
        await container.start()

        container_id = container.id

        # Register execution as active in Redis and publish "processing"
        await self.register_execution(execution_id, container_id=container_id)

        logger.info(f"Started container {container_id[:12]} for execution {execution_id}")

        return container_id

    async def _build_container_config(
        self,
        execution_id: str,
        job: ReviewJobMessage,
    ) -> dict[str, Any]:
        """Build Docker container configuration."""
        config: dict[str, Any] = {
            "Image": self._config.image,
            "Cmd": build_cli_args(job),
            "Env": await build_env_vars(job),
            "Labels": build_container_labels(execution_id, job),
            "HostConfig": {
                "Memory": parse_memory_limit(self._config.memory_limit),
                "NanoCPUs": int(self._config.cpu_limit * 1e9),
                "AutoRemove": False,
                "CapDrop": ["ALL"],
                "SecurityOpt": ["no-new-privileges"],
                "ReadonlyRootfs": True,
                "PidsLimit": 256,
                "Tmpfs": {
                    "/tmp": "rw,noexec,nosuid,size=1073741824",
                    "/home/reviewate": "rw,noexec,nosuid,size=536870912",
                },
            },
        }

        if self._config.network:
            config["HostConfig"]["NetworkMode"] = self._config.network

        return config

    async def stop_container(self, container_id: str) -> None:
        """Stop a running container."""
        docker = await self._get_docker()
        try:
            container = await docker.containers.get(container_id)
            await container.stop()
            logger.debug(f"Stopped container {container_id[:12]}")
        except Exception as e:
            logger.warning(f"Failed to stop container {container_id[:12]}: {e}")

    # === Container Watching ===

    async def start_watching(self) -> None:
        """Start watching for container events."""
        docker = await self._get_docker()
        self._running = True
        self._watch_task = asyncio.create_task(self._watch_loop(docker))

    async def stop_watching(self) -> None:
        """Stop watching for container events."""
        self._running = False
        if self._watch_task:
            self._watch_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._watch_task
            self._watch_task = None
        if self._docker:
            await self._docker.close()
            self._docker = None

    async def _watch_loop(self, docker: Docker) -> None:
        """Main watch loop for Docker events."""
        while self._running:
            try:
                subscriber = docker.events.subscribe(
                    filters={
                        "type": ["container"],
                        "label": [LABEL_EXECUTION_ID],
                    }
                )
                while self._running:
                    event = await subscriber.get()
                    if event is None:
                        break
                    task = asyncio.create_task(self._handle_event_with_limit(event))
                    self._pending_tasks.add(task)
                    task.add_done_callback(self._pending_tasks.discard)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Docker event watch loop: {e}")
                if self._running:
                    await asyncio.sleep(5)

        if self._pending_tasks:
            logger.info(f"Waiting for {len(self._pending_tasks)} pending event handlers...")
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)

    async def _handle_event_with_limit(self, event: dict[str, Any]) -> None:
        """Handle container event with concurrency limiting."""
        async with self._semaphore:
            await self._handle_container_event(event)

    async def _handle_container_event(self, event: dict[str, Any]) -> None:
        """Handle a Docker container event."""
        action = event.get("Action", "")
        actor = event.get("Actor", {})
        attributes = actor.get("Attributes", {})
        container_id = actor.get("ID", "")

        execution_id = attributes.get(LABEL_EXECUTION_ID)
        if not execution_id:
            return

        logger.debug(
            f"Container event: {action} for execution {execution_id}",
            extra={
                "action": action,
                "execution_id": execution_id,
                "container_id": container_id[:12] if container_id else "",
            },
        )

        if action == DockerEventAction.DIE:
            await self._handle_container_exit(
                execution_id=execution_id,
                container_id=container_id,
                exit_code=int(attributes.get("exitCode", 1)),
            )

    async def _handle_container_exit(
        self,
        execution_id: str,
        container_id: str,
        exit_code: int,
    ) -> None:
        """Handle container exit event with idempotency.

        Uses publish_status_idempotent to prevent duplicate processing.
        """
        # Parse result from logs
        result, error_info = await self._get_container_logs_result(container_id)

        # Determine final status
        status, final_error_info = determine_execution_status(exit_code, result, error_info)

        # Publish with idempotency check (atomic remove from active set)
        published = await self.publish_status_idempotent(
            execution_id=execution_id,
            status=status,
            container_id=container_id,
            exit_code=exit_code,
            error_type=final_error_info[0] if final_error_info else None,
            error_message=final_error_info[1] if final_error_info else None,
            result=result,
        )

        # Only cleanup if we actually processed this exit
        if published:
            await self._cleanup_container(container_id)

    async def _get_container_logs_result(
        self,
        container_id: str,
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Get and parse container logs for result/error."""
        docker = await self._get_docker()

        try:
            container = await docker.containers.get(container_id)
            logs = await container.log(stdout=True, stderr=True)
            log_text = "".join(logs)
            return parse_structured_logs(log_text)

        except Exception as e:
            logger.error(f"Failed to parse container logs: {e}")
            return None, None

    async def _cleanup_container(self, container_id: str) -> None:
        """Remove a container after processing."""
        if not self._config.cleanup_containers:
            logger.debug(f"Skipping cleanup for container {container_id[:12]} (cleanup disabled)")
            return

        docker = await self._get_docker()
        try:
            container = await docker.containers.get(container_id)
            await container.delete(force=True)
            logger.debug(f"Cleaned up container {container_id[:12]}")
        except Exception as e:
            logger.warning(f"Failed to cleanup container {container_id[:12]}: {e}")

    # === Reconciliation ===

    async def reconcile(self) -> None:
        """Reconcile container state with Redis tracking and database.

        Single-pass reconciliation that handles:
        1. Exited containers whose events were missed (force-publishes,
           bypassing idempotency to recover from lost pub/sub messages)
        2. Orphaned executions (in Redis but container gone)
        3. Stale DB executions (queued/processing in DB but no container running)

        This method is protected by a distributed lock so only one instance
        runs reconciliation at a time.
        """
        docker = await self._get_docker()

        try:
            # Get containers and active executions in parallel
            containers = await docker.containers.list(
                all=True,
                filters={"label": [LABEL_EXECUTION_ID]},
            )
            active_executions = await self.get_active_executions()

            # Build mapping of execution_id -> container info
            container_map: dict[str, tuple[DockerContainer, dict]] = {}
            for container in containers:
                info = await container.show()
                labels = info.get("Config", {}).get("Labels", {})
                exec_id = labels.get(LABEL_EXECUTION_ID)
                if exec_id:
                    container_map[exec_id] = (container, info)

            # 1. Process exited containers — force-publish status regardless
            # of Redis active set. After a backend restart, the execution may
            # have been removed from Redis by the previous instance but the
            # pub/sub message was lost. The idempotent path would skip these
            # forever, so reconciliation bypasses it.
            for exec_id, (_container, info) in container_map.items():
                state = info.get("State", {})
                if state.get("Status") == ContainerStatus.EXITED:
                    container_id = info.get("Id", "")
                    exit_code = state.get("ExitCode", 1)

                    logger.info(
                        "Reconciling exited container %s for execution %s",
                        container_id[:12],
                        exec_id,
                    )

                    await self._reconcile_container_exit(
                        execution_id=exec_id,
                        container_id=container_id,
                        exit_code=exit_code,
                    )

            # 2. Handle orphaned executions (in Redis but no container)
            container_exec_ids = set(container_map.keys())
            orphaned = active_executions - container_exec_ids

            for exec_id in orphaned:
                logger.warning(f"Found orphaned execution {exec_id} - container not found")
                await self.unregister_execution(exec_id)
                await self.publish_status(
                    execution_id=exec_id,
                    status="failed",
                    error_type="container_error",
                    error_message="Container not found - may have been removed unexpectedly",
                )

            # 3. Fail stale DB executions whose container no longer exists.
            # Covers the case where container died/was cleaned up and the
            # status event was lost — the DB stays stuck in queued/processing
            # forever, blocking new triggers via db_has_active_execution.
            running_container_ids = {
                exec_id
                for exec_id, (_c, info) in container_map.items()
                if info.get("State", {}).get("Status")
                in (ContainerStatus.RUNNING, ContainerStatus.CREATED)
            }
            await self.fail_stale_db_executions(running_container_ids)

        except Exception as e:
            logger.error(f"Error during reconciliation: {e}")

    async def _reconcile_container_exit(
        self,
        execution_id: str,
        container_id: str,
        exit_code: int,
    ) -> None:
        """Handle container exit during reconciliation.

        Unlike _handle_container_exit, this bypasses the idempotency check
        and always publishes status. Safe because reconciliation is protected
        by a distributed lock.
        """
        # Parse result from logs
        result, error_info = await self._get_container_logs_result(container_id)

        # Determine final status
        status, final_error_info = determine_execution_status(exit_code, result, error_info)

        # Remove from active set (may already be gone — that's fine)
        await self.unregister_execution(execution_id)

        # Always publish — this is the safety net for lost pub/sub messages
        await self.publish_status(
            execution_id=execution_id,
            status=status,
            container_id=container_id,
            exit_code=exit_code,
            error_type=final_error_info[0] if final_error_info else None,
            error_message=final_error_info[1] if final_error_info else None,
            result=result,
        )

        # Cleanup the container
        await self._cleanup_container(container_id)
