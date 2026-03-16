"""Abstract base class for container backends."""

import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from faststream.redis import RedisBroker

from api.context import get_current_app
from api.database.execution import db_get_running_executions, db_update_execution_status
from api.models.executions import ExecutionStatus
from api.plugins.faststream.config import STREAM_MAXLEN
from api.sse.publishers import publish_pull_request_event

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from api.routers.queue.schemas import ReviewJobMessage

logger = logging.getLogger(__name__)

# Redis keys for execution tracking
ACTIVE_EXECUTIONS_KEY = "reviewate:executions:active"
RECONCILE_LOCK_KEY = "reviewate:reconcile:lock"
RECONCILE_LOCK_TTL = 60  # seconds


class ContainerBackend(ABC):
    """Abstract base for container backends (Docker, K8s).

    Each backend handles BOTH execution and watching for its platform.

    Features:
    - Redis-based tracking of active executions (no DB polling)
    - Idempotent status updates (checks before publishing)
    - Single reconcile function for simplicity
    """

    def __init__(self, broker: RedisBroker, redis: Redis):
        """Initialize the backend.

        Args:
            broker: FastStream Redis broker for publishing status updates
            redis: Redis client for execution tracking and locking
        """
        self._broker = broker
        self._redis = redis

    # === Execution Tracking (Redis-based) ===

    async def register_execution(self, execution_id: str, container_id: str | None = None) -> bool:
        """Register an execution as active and publish processing status.

        Uses SADD as an atomic gate — returns True only for the first caller.

        Args:
            execution_id: Execution ID to track
            container_id: Optional container/job ID

        Returns:
            True if this was the first registration (status published)
        """
        added = await self._redis.sadd(ACTIVE_EXECUTIONS_KEY, execution_id)
        if added:
            await self.publish_status(
                execution_id=execution_id,
                status=ExecutionStatus.PROCESSING,
                container_id=container_id,
            )
        logger.debug(f"Registered execution {execution_id} as active (new={bool(added)})")
        return bool(added)

    async def unregister_execution(self, execution_id: str) -> None:
        """Remove an execution from active set in Redis.

        Called when a container exits (success or failure).

        Args:
            execution_id: Execution ID to remove
        """
        await self._redis.srem(ACTIVE_EXECUTIONS_KEY, execution_id)
        logger.debug(f"Unregistered execution {execution_id}")

    async def get_active_executions(self) -> set[str]:
        """Get all active execution IDs from Redis.

        Returns:
            Set of execution IDs
        """
        members = await self._redis.smembers(ACTIVE_EXECUTIONS_KEY)
        return {m.decode() if isinstance(m, bytes) else m for m in members}

    async def is_execution_active(self, execution_id: str) -> bool:
        """Check if an execution is still active.

        Args:
            execution_id: Execution ID to check

        Returns:
            True if execution is in active set
        """
        return await self._redis.sismember(ACTIVE_EXECUTIONS_KEY, execution_id)

    # === Distributed Locking ===

    async def acquire_reconcile_lock(self) -> bool:
        """Try to acquire the reconcile lock.

        Only one instance should reconcile at a time.

        Returns:
            True if lock acquired, False if already held by another instance
        """
        acquired = await self._redis.set(
            RECONCILE_LOCK_KEY,
            "1",
            nx=True,
            ex=RECONCILE_LOCK_TTL,
        )
        return bool(acquired)

    async def release_reconcile_lock(self) -> None:
        """Release the reconcile lock."""
        await self._redis.delete(RECONCILE_LOCK_KEY)

    # === Container Execution ===

    @abstractmethod
    async def start_container(
        self,
        execution_id: str,
        job: ReviewJobMessage,
    ) -> str:
        """Start a container for the given job.

        Implementations should call register_execution() after starting.

        Args:
            execution_id: Unique ID for this execution
            job: Job configuration message

        Returns:
            Container ID
        """
        pass

    @abstractmethod
    async def stop_container(self, container_id: str) -> None:
        """Stop a running container.

        Args:
            container_id: ID of the container to stop
        """
        pass

    # === Container Watching ===

    @abstractmethod
    async def start_watching(self) -> None:
        """Start watching for container events.

        This should start a background loop that monitors all containers
        with reviewate labels and publishes status updates.
        """
        pass

    @abstractmethod
    async def stop_watching(self) -> None:
        """Stop watching for container events."""
        pass

    @abstractmethod
    async def reconcile(self) -> None:
        """Reconcile container state with Redis tracking.

        This single function handles both:
        1. Containers that exited but weren't processed (event missed)
        2. Executions tracked in Redis but container is gone (orphaned)

        Should be called periodically by the plugin's reconcile loop.
        Must acquire reconcile lock before running.
        """
        pass

    # === Stale Execution Cleanup ===

    async def fail_stale_db_executions(self, running_exec_ids: set[str]) -> None:
        """Fail DB executions in queued/processing whose container is gone.

        Only considers executions older than 60s to give freshly queued jobs
        time to start their container.

        Args:
            running_exec_ids: Set of execution IDs that have a running container
        """
        try:
            app = get_current_app()
            grace_cutoff = datetime.now(UTC) - timedelta(seconds=60)

            with app.database.session() as db:
                db_executions = db_get_running_executions(db, exclude_ids=running_exec_ids)
                failed_count = 0

                for execution in db_executions:
                    exec_id = str(execution.id)

                    # Skip recently created executions — container may still be starting
                    created_at = (
                        execution.created_at.replace(tzinfo=UTC)
                        if execution.created_at.tzinfo is None
                        else execution.created_at
                    )
                    if created_at > grace_cutoff:
                        continue

                    logger.warning(
                        f"Failing orphaned DB execution {exec_id} "
                        f"(status={execution.status}, no running container)"
                    )
                    db_update_execution_status(
                        db,
                        execution.id,
                        "failed",
                        error_type="container_error",
                        error_detail="Container no longer running — cleaned up or crashed",
                    )
                    await publish_pull_request_event(
                        pull_request_id=str(execution.pull_request_id),
                        action="execution_status_changed",
                        organization_id=str(execution.organization_id),
                        repository_id=str(execution.repository_id),
                        latest_execution_id=exec_id,
                        latest_execution_status="failed",
                        updated_at=execution.updated_at.isoformat(),
                        error_type="container_error",
                        error_detail="Container no longer running — cleaned up or crashed",
                    )
                    failed_count += 1

                if failed_count:
                    logger.info(f"Failed {failed_count} orphaned DB execution(s)")

        except Exception as e:
            logger.error(f"Error failing stale DB executions: {e}")

    # === Status Publishing ===

    async def publish_status(
        self,
        execution_id: str,
        status: str,
        container_id: str | None = None,
        exit_code: int | None = None,
        error_message: str | None = None,
        error_type: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> None:
        """Publish a status update to Redis.

        Args:
            execution_id: ID of the execution
            status: New status (processing, completed, failed)
            container_id: Optional container ID
            exit_code: Optional exit code
            error_message: Optional error message
            error_type: Optional standardized error type
            result: Optional parsed result from container logs
        """
        message = {
            "execution_id": execution_id,
            "status": status,
            "container_id": container_id,
            "exit_code": exit_code,
            "error_message": error_message,
            "error_type": error_type,
            "result": result,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        await self._broker.publish(
            message, stream="reviewate.execution.status", maxlen=STREAM_MAXLEN
        )

    async def publish_status_idempotent(
        self,
        execution_id: str,
        status: str,
        container_id: str | None = None,
        exit_code: int | None = None,
        error_message: str | None = None,
        error_type: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> bool:
        """Publish status update only if execution is still active.

        This prevents duplicate processing when both event and reconcile
        try to process the same container exit.

        Args:
            execution_id: ID of the execution
            status: New status (processing, completed, failed)
            container_id: Optional container ID
            exit_code: Optional exit code
            error_message: Optional error message
            error_type: Optional standardized error type
            result: Optional parsed result from container logs

        Returns:
            True if status was published, False if skipped (not active)
        """
        # For terminal states, check and remove atomically
        if status in ("completed", "failed"):
            # Only process if still in active set (atomic check-and-remove)
            removed = await self._redis.srem(ACTIVE_EXECUTIONS_KEY, execution_id)
            if not removed:
                logger.debug(f"Skipping status update for {execution_id} - already processed")
                return False

        await self.publish_status(
            execution_id=execution_id,
            status=status,
            container_id=container_id,
            exit_code=exit_code,
            error_message=error_message,
            error_type=error_type,
            result=result,
        )
        return True
