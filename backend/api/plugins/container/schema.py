"""Container backend schema definitions and enums."""

from enum import StrEnum

# === Kubernetes Enums ===


class JobConditionType(StrEnum):
    """Kubernetes Job condition types."""

    COMPLETE = "Complete"
    FAILED = "Failed"


class ConditionStatus(StrEnum):
    """Kubernetes condition status values."""

    TRUE = "True"
    FALSE = "False"
    UNKNOWN = "Unknown"


class WatchEventType(StrEnum):
    """Kubernetes watch event types."""

    ADDED = "ADDED"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"


# === Docker Enums ===


class DockerEventAction(StrEnum):
    """Docker container event actions."""

    START = "start"
    DIE = "die"
    STOP = "stop"
    KILL = "kill"
    CREATE = "create"


class ContainerStatus(StrEnum):
    """Docker container status values."""

    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    RESTARTING = "restarting"
    EXITED = "exited"
    DEAD = "dead"


# Container name constant
CONTAINER_NAME = "reviewer"
